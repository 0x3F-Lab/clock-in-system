import math
import requests
import logging
import holidays
import api.exceptions as err

from datetime import timedelta
from urllib.parse import urlencode
from django.utils import timezone
from django.core.cache import cache
from django.contrib.sessions.models import Session
from django.utils.timezone import make_aware, is_naive
from auth_app.models import User, Store, Activity
from clock_in_system.settings import (
    COUNTRY_CODE,
    COUNTRY_SUBDIV_CODE,
    UTC_OFFSET,
    SHIFT_ROUNDING_MINS,
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
def round_datetime_minute(dt, rounding_mins=SHIFT_ROUNDING_MINS):
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


def str_to_bool(val):
    # Ensure the value is a boolean by converting properly
    return str(val).strip().lower() in ["true", "1", "yes"]


def clean_param_str(value):
    """
    Returns the value as a stripped string or None if the value is None or the empty string.
    Useful for using to get request params/data values.
    """
    if (value is None) or (value is ""):
        return None
    else:
        return str(value).strip()
