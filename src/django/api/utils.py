import re
import math
import requests
import logging
import holidays
import api.exceptions as err

from datetime import timedelta, datetime, time
from typing import List, Tuple, Optional, Union
from urllib.parse import urlencode
from django.db.models import Q
from django.utils import timezone
from django.core.cache import cache
from django.contrib.sessions.models import Session
from django.utils.timezone import make_aware, is_naive
from auth_app.models import User, Store, Activity, Shift, ShiftException
from clock_in_system.settings import (
    COUNTRY_CODE,
    COUNTRY_SUBDIV_CODE,
    UTC_OFFSET,
    SHIFT_ROUNDING_MINS,
    VALID_NAME_LIST_PATTERN,
    MAX_DATABASE_DUMP_LIMIT,
    MINIMUM_SHIFT_LENGTH_ASSIGNMENT_MINS,
)

logger = logging.getLogger("api")


def flush_user_sessions(user_id: int):
    """
    Helper function to flush all sessions that are for the given user_id
    """
    count = 0
    for session in Session.objects.all():
        data = session.get_decoded()
        if data.get("user_id") == int(user_id):
            session.delete()
            count += 1

    logger.debug(
        f"[FLUSH: SESSIONS] [PASSWORD-CHANGE] USER ID: {user_id} -- Num Sessions flushed: {count}"
    )


# Function to check if a given date is a public holiday
def is_public_holiday(
    time, country=COUNTRY_CODE, subdiv=COUNTRY_SUBDIV_CODE, utc_offset=UTC_OFFSET
):
    # Ensure 'time' is timezone-aware
    if time.tzinfo is None:
        # If naive datetime, convert it to a timezone-aware datetime based on the default timezone
        time = timezone.make_aware(time, timezone.get_current_timezone())

    time = timezone.localtime(
        time
    )  # Ensure time is in the local timezone of django settings
    date = time.date()

    # Check cache if public holiday status has already been checked (saves computing)
    cache_key = f"public_holiday_{date.isoformat()}"

    status = cache.get(cache_key)
    if status is not None:
        # If the status is already cached, return the status
        return status

    # Check using offline library
    try:
        country_holidays = holidays.country_holidays(country=country, subdiv=subdiv)
        if date in country_holidays:
            # Set the cache before returning
            cache.set(cache_key, True, timeout=86400)  # Cache it for 24 hours
            return True

    except Exception as e:
        logger.error(f"Error checking local holidays for date `{date}`: {str(e)}")

    # Else, double check API to ensure its up to date with current affairs.
    url = f"https://date.nager.at/api/v3/IsTodayPublicHoliday/{country}"

    # Create query parameters
    query_params = {}
    if subdiv:  # If there is a further country subdivision code
        query_params["countyCode"] = f"{country}-{subdiv}"
    if utc_offset:
        query_params["offset"] = utc_offset

    # Append query params if any exist
    if query_params:
        url += "?" + urlencode(query_params)

    # Check API
    try:
        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            # Set the cache before returning
            cache.set(cache_key, True, timeout=86400)
            return True

        elif response.status_code == 204:
            cache.set(cache_key, False, timeout=86400)
            return False

        elif response.status_code == 503:
            logger.error(
                f"Error checking public holiday via API gave code `{response.status_code}`: Server is currently down."
            )

        else:
            logger.error(
                f"Error checking public holiday via API gave code `{response.status_code}`: {response.json().get('error', 'Unknown error.')}"
            )

    except requests.exceptions.Timeout:
        logger.error(
            "Error checking public holiday via API as request timed out. Is the API up?"
        )
    except requests.exceptions.ConnectionError:
        logger.error(
            "Error checking public holiday via API as it failed to connect to API."
        )
    except requests.RequestException as e:
        logger.error(f"Unexpected error when checking public holiday via API: {str(e)}")

    # Ensure something returns (DONT SET CACHE AS API CALL FAILED)
    return False


def api_get_user_object_from_session(request):
    # Get user's id
    employee_id = request.session.get("user_id")

    # Get employee data to check state
    try:
        employee = User.objects.get(id=employee_id)

        if not employee.is_active:
            request.session.flush()
            raise err.InactiveUserError

    except User.DoesNotExist as e:
        request.session.flush()
        logger.error(
            f"User object could not be obtained from user id in the session info. Session infomration: {request.session}"
        )
        raise e

    # Return employee object
    return employee


# Function to round the time to the nearest specified minute
def round_datetime_minute(
    dt: datetime, rounding_mins: int = SHIFT_ROUNDING_MINS
) -> datetime:
    """
    Rounds a datetime object to the nearest interval defined by rounding_mins.

    Args:
        dt (datetime): The datetime to round.
        rounding_mins (int, optional): The number of minutes to round to. Defaults to SHIFT_ROUNDING_MINS.

    Returns:
        datetime: The rounded datetime.
    """
    # Calculate the total number of minutes since midnight
    total_minutes = dt.hour * 60 + dt.minute

    # Find the remainder when dividing total minutes by rounding_mins
    remainder = total_minutes % rounding_mins

    # If remainder is greater than or equal to half of rounding_mins, round up
    if remainder >= rounding_mins / 2:
        # Round up
        rounded_minutes = total_minutes + (rounding_mins - remainder)
    else:
        # Round down
        rounded_minutes = total_minutes - remainder

    # Calculate the new rounded time
    rounded_dt = dt.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
        minutes=rounded_minutes
    )

    # Return the rounded datetime
    return rounded_dt


# Function to calculate the total time in a shift (in minutes)
def calculate_shift_length_mins(start, end):
    # Calculate difference between events
    time_diff = end - start

    # Calculate the total shift time in minutes
    total_minutes = time_diff.total_seconds() / 60

    return total_minutes


def get_distance_from_lat_lon_in_m(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """
    Calculate the distance between two latitude/longitude points in meters
    using the Haversine formula.

    Args:
        lat1 (float): Latitude of the user.
        lon1 (float): Longitude of the user.
        lat2 (float): Latitude of the store.
        lon2 (float): Longitude of the store.

    Returns:
        float: Distance in meters that the user is from the store.
    """
    # Earth's radius in meters
    R = 6371000.0

    # Convert degrees to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    # Differences in coordinates
    d_lat = lat2_rad - lat1_rad
    d_lon = lon2_rad - lon1_rad

    # Haversine formula
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(d_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # Return the distance
    return R * c


def check_location_data(location_lat, location_long, store_id) -> bool:
    """
    Check the location data given is close enough to the store

    Args:
        location_lat: Latitude of the user.
        location_lon: Longitude of the user.
        store_id: The ID of the Store to check the location against

    Returns:
        bool: True if the user is close enough to the store, False otherwise.
    """
    # Check to see they exist
    if (location_lat is None) or (location_long is None):
        raise err.MissingLocationDataError

    if store_id is None:
        raise err.MissingStoreObjectOrIDError

    # Convert to location floats
    try:
        location_lat = float(location_lat)
        location_long = float(location_long)
    except ValueError:
        raise err.BadLocationDataError

    # Get Store Object
    store = Store.objects.get(id=store_id)

    # Obtain distance of user from store
    dist = get_distance_from_lat_lon_in_m(
        lat1=location_lat,
        lon1=location_long,
        lat2=store.location_latitude,
        lon2=store.location_longitude,
    )

    if int(dist) <= int(store.allowable_clocking_dist_m):
        return True

    # Return fefault False on unsuccessful location data check
    return False


def is_activity_modified(activity: Activity):
    """
    Determine if an activity has been modified after clocking,
    allowing a 15-second tolerance window.
    """
    clock_time = activity.logout_timestamp or activity.login_timestamp
    last_updated = activity.last_updated_at

    # Ensure both times are timezone-aware
    if clock_time and is_naive(clock_time):
        clock_time = make_aware(clock_time)
    if is_naive(last_updated):
        last_updated = make_aware(last_updated)

    # Add a 15-second buffer to the clock time
    if clock_time:
        return last_updated > (clock_time + timedelta(seconds=15))
    return False


def get_filter_list_from_string(list: str) -> List[str]:
    """
    Function to get the filter names from the pure string passed from query params.
    Checks names against RE filter provided in settings.py

    Returns `None` if no list is provided.
    Raises `ValueError` if invalid characters are provided in the list.
    """
    if list and not re.match(VALID_NAME_LIST_PATTERN, list):
        raise ValueError

    if list:
        return [name.strip() for name in list.split(",") if name.strip()]

    return None


def get_pagination_values_from_request(request) -> Tuple[int, int]:
    """
    Get the pagination values (offset & limit) from the request and handle limits.
    Args:
      request: The request object.

    Returns:
      Tuple[int, int]: Returned in the order (offset, limit)
    """
    try:
        # enforce min offset = 0
        offset = max(int(request.query_params.get("offset", "0")), 0)
    except ValueError:
        offset = 0

    try:
        # Enforce min limit = 1 and max limit = 150 (settings controlled)
        limit = min(
            max(int(request.query_params.get("limit", "25")), 1),
            MAX_DATABASE_DUMP_LIMIT,
        )
    except ValueError:
        limit = 25

    return offset, limit


def str_to_bool(val):
    # Ensure the value is a boolean by converting properly
    return str(val).strip().lower() in ["true", "1", "yes"]


def clean_param_str(value):
    """
    Returns the value as a stripped string or None if the value is None or the empty string.
    Useful for using to get request params/data values.
    """
    if (value is None) or (value == ""):
        return None
    else:
        return str(value).strip()


def employee_has_conflicting_shift(
    employee: User,
    store: Store,
    date: datetime.date,
    exclude_shift_id: Optional[int] = None,
) -> bool:
    """
    Check if an employee has any other shift on a given date for the given store, excluding a specific shift by ID.

    Args:
        employee (User): The employee to check shifts for.
        store (Store): The store to check shifts against.
        date (datetime.date): The date to check for existing shifts.
        exclude_shift_id (int, optional): The ID of the shift to exclude from the check (usually the current shift being updated).

    Returns:
        bool: True if there is a conflicting shift on that date (other than the one excluded), False otherwise.
    """
    qs = Shift.objects.filter(
        employee=employee, store=store, date=date, is_deleted=False
    )
    if exclude_shift_id:
        qs = qs.exclude(id=exclude_shift_id)
    return qs.exists()


def is_shift_duration_valid(
    start_time: time,
    end_time: time,
    min_duration_mins: int = MINIMUM_SHIFT_LENGTH_ASSIGNMENT_MINS,
) -> bool:
    """
    Check if the time duration between start_time and end_time is greater than or equal
    to a minimum required duration. Assumes both times are on the same day and end_time is after start_time.

    Args:
        start_time (time): Shift start time.
        end_time (time): Shift end time.
        minimum_duration_minutes (int): Minimum duration in minutes the shift must span. Defaults to settings value.

    Returns:
        bool: True if the duration is valid, False otherwise.
    """
    # Assume both times are on the same (arbitrary) day
    dt_start = datetime.combine(datetime.min, start_time)
    dt_end = datetime.combine(datetime.min, end_time)

    # Reject invalid case where end is before or equal to start
    if dt_end <= dt_start:
        return False

    duration = dt_end - dt_start
    return duration >= timedelta(minutes=min_duration_mins)


def check_store_exceptions_in_period(
    store_id: Union[int, str], start_dt: datetime, end_dt: datetime
) -> bool:
    """
    Check if a store has any unapproved exceptions within the datetime period.
    """
    return ShiftException.objects.filter(
        Q(is_approved=False)
        & (
            Q(
                shift__store_id=store_id,
                shift__date__range=(start_dt.date(), end_dt.date()),
            )
            | Q(
                activity__store_id=store_id,
                activity__login_timestamp__range=(start_dt, end_dt),
            )
        )
    ).exists()
