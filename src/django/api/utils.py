import re
import math
import requests
import logging
import holidays
import api.exceptions as err

from datetime import timedelta, datetime, time, date
from typing import List, Tuple, Optional, Union, Pattern
from urllib.parse import urlencode
from django.db.models import Q
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
from django.contrib.sessions.models import Session
from django.utils.timezone import make_aware, is_naive, localtime
from auth_app.models import User, Store, Activity, Shift, ShiftException

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
    time,
    country=settings.COUNTRY_CODE,
    subdiv=settings.COUNTRY_SUBDIV_CODE,
    utc_offset=settings.UTC_OFFSET,
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
        employee = User.objects.get(pk=employee_id)

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
    dt: datetime, rounding_mins: int = settings.SHIFT_ROUNDING_MINS
) -> datetime:
    """
    Rounds a datetime object to the nearest interval defined by rounding_mins.

    Args:
        dt (datetime): The datetime to round.
        rounding_mins (int, optional): The number of minutes to round to. Defaults to settings.SHIFT_ROUNDING_MINS.

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
    store = Store.objects.get(pk=store_id)

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


def employee_has_conflicting_activities(
    employee_id: int,
    store_id: int,
    login: datetime,
    logout: datetime = None,
    exclude_activity_id: int = None,
    gap_period_mins: int = settings.START_NEW_SHIFT_TIME_DELTA_THRESHOLD_MINS,
) -> bool:
    """
    Checks to see if an activity collides with another activity (i.e. A: 9am-5pm and B: 3pm-7pm).
    This also checks to make sure activities have a `gap_period_mins` between each activity for the user for a store for a day.
    THIS WILL ALLOW ACTIVITIES ENDING AT MIDNIGHT AND STARTING NEXT DAY AT MIDNIGHT.

    Args:
        employee_id (int): The ID of the employee.
        store_id (int): The ID of the store.
        login (datetime): The proposed activity login time.
        logout (datetime, optional): The proposed activity logout time. Defaults to None.
        exclude_activity_id (int, optional): ID of an existing activity to exclude (e.g., when updating). Defaults to None.
        gap_period_mins (int): Minimum gap (in minutes) required between activities. Defaults to settings.START_NEW_SHIFT_TIME_DELTA_THRESHOLD_MINS.


    Returns:
        bool: Whether there is a conflict or not.
    """
    # Get activities for the employee on the given day for the given store
    activities = Activity.objects.filter(
        employee_id=employee_id, store_id=store_id, login_time__date=login.date()
    )

    # Exclude an acitivity if given (i.e. updating an existing activity)
    if exclude_activity_id:
        activities = activities.exclude(pk=exclude_activity_id)

    for act in activities:
        # Determine actual range of the compared activity
        other_start = act.login_time
        # Extend open-ended activity to end of the day (23:59:59)
        other_end = act.logout_time or datetime.combine(other_start.date(), time.max)

        # Apply buffer to both sides
        login_start_buffer = login - timedelta(minutes=gap_period_mins)
        logout_end_buffer = (
            logout + timedelta(minutes=gap_period_mins)
            if logout
            else datetime.combine(login.date(), time.max)
        )

        # Check overlap (inclusive of buffer zone)
        if login_start_buffer < other_end and logout_end_buffer > other_start:
            return True

    return False


def employee_has_conflicting_shifts(
    employee_id: int,
    store_id: int,
    date: datetime.date,
    login: datetime.time,
    logout: datetime.time,
    exclude_shift_id: int = None,
    gap_period_mins: int = settings.START_NEW_SHIFT_TIME_DELTA_THRESHOLD_MINS,
) -> bool:
    """
    Checks to see if a scheduled shift collides with another shift (i.e. A: 9am-5pm and B: 3pm-7pm).
    This also checks to make sure shifts have a `gap_period_mins` between each activity for the user for a store for a day.
    THIS WILL ALLOW SCHEDULED SHIFTS ENDING AT MIDNIGHT AND STARTING NEXT DAY AT MIDNIGHT.

    Args:
        employee_id (int): The ID of the employee.
        store_id (int): The ID of the store.
        date (datetime.date): The propposed shift date.
        login (datetime.time): The proposed shift login time.
        logout (datetime, optional): The proposedshift logout time. Defaults to None.
        exclude_shift_id (int, optional): ID of an existing shift to exclude (e.g., when updating). Defaults to None.
        gap_period_mins (int): Minimum gap (in minutes) required between shifts. Defaults to settings.START_NEW_SHIFT_TIME_DELTA_THRESHOLD_MINS.


    Returns:
        bool: Whether there is a conflict or not.
    """
    # Get activities for the employee on the given day for the given store
    shifts = Shift.objects.filter(employee_id=employee_id, store_id=store_id, date=date)

    # Exclude an acitivity if given (i.e. updating an existing activity)
    if exclude_shift_id:
        shifts = shifts.exclude(pk=exclude_shift_id)

    for shift in shifts:
        # Use datetime variables by using date to combine them with time
        other_start = datetime.combine(date, shift.start_time)
        other_end = datetime.combine(date, shift.end_time)
        this_start = datetime.combine(date, login)
        this_end = datetime.combine(date, logout)

        # Add/subtract buffer
        this_start_buffer = this_start - timedelta(minutes=gap_period_mins)
        this_end_buffer = this_end + timedelta(minutes=gap_period_mins)

        # Check for overlap
        if this_start_buffer < other_end and this_end_buffer > other_start:
            return True

    return False


def get_filter_list_from_string(
    list_str: str,
    regex_filter: Union[str, Pattern[str]] = settings.VALID_NAME_LIST_PATTERN,
) -> Optional[List[str]]:
    """
    Parse a comma-separated string of names from query parameters, validate
    against a regex pattern, and return a list of cleaned names.

    Args:
      list_str: A comma-separated string of names (e.g., "Alice,Bob,Charlie").
                If None or empty, the function returns None.
      regex_filter: A regex pattern (string or compiled Pattern) used to validate
                    the entire input string before splitting. MUST INCLUDE `,` IN THE PATTERN.
                    Defaults to settings.VALID_NAME_LIST_PATTERN.

    Returns:
      Optional[List]: A list of stripped name strings if input is non-empty, or None otherwise.

    Raises:
      ValueError: If the input string contains invalid characters (fails regex match).
    """
    if list_str:
        # Validate input string against the regex
        if not re.match(regex_filter, list_str):
            raise ValueError(f"Invalid characters in filter list: '{list_str}'")

        # Split on commas and strip whitespace from each entry
        return [item.strip() for item in list_str.split(",") if item.strip()]

    return None


def get_pagination_values_from_request(
    request, default_limit: int = 25
) -> Tuple[int, int]:
    """
    Get the pagination values (offset & limit) from the request and handle limits.
    Args:
      request: The request object.
      default_limit (int): The default limit if none is provided.

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
            max(int(request.query_params.get("limit", default_limit)), 1),
            settings.MAX_DATABASE_DUMP_LIMIT,
        )
    except ValueError:
        limit = 25  # Revert to 25 if any errors

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


def is_shift_duration_valid(
    start_time: time,
    end_time: time,
    min_duration_mins: int = settings.MINIMUM_SHIFT_LENGTH_ASSIGNMENT_MINS,
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


def get_week_start(d: date) -> date:
    """
    Ensure date is on the monday of the given week (roll back if need be)
    """
    return d - timedelta(days=d.weekday())  # Monday is weekday 0


def check_perfect_shift_activity_timings(activity: Activity, shift: Shift) -> bool:
    """
    Check if the provided activity and shift are perfectly matched in terms of timings of clocking in/out. (Rounded of course)

    Args:
        activity (Activity): The activity object to compare.
        shift (Shift): The shift object to compare.

    Returns:
        bool: If there exists a perfect link between the two. If either is slightly off then it returns False.
    """
    # If activity is not finished -> IGNORE
    if not activity.logout_time:
        return True

    # Check start time matches (use rounded login_time)
    if shift.start_time != localtime(activity.login_time).time():
        return False

    # Check end time matches (use rounded logout_time)
    elif shift.end_time != localtime(activity.logout_time).time():
        return False

    return True


def is_valid_linking_activity_candidate(
    possible_activity: Activity,
    existing_exception: Optional[ShiftException] = None,
    other_shifts: Optional[List[Shift]] = None,
) -> bool:
    """
    Check whether the given activity is a valid candidate for linking to a shift.

    Args:
        possible_activity (Activity): The activity to validate.
        existing_exception (ShiftException, optional): Existing exception, if any.
        other_shifts (List[Shift], optional): Preloaded list of other shifts for performance. Used to check if perfect match already exists for possible activity.

    Returns:
        bool: True if this activity is valid for linking, else False.
    """
    if not possible_activity.logout_time:
        return False

    # Check if the given activity has a related exception
    related_exception = getattr(possible_activity, "activity_shiftexception", None)

    if related_exception:
        # Linked to current shift's exception
        if existing_exception and possible_activity == existing_exception.activity:
            return True
        # Linked exception has no shift
        elif not related_exception.shift:
            return True
        # Otherwise it's already a full exception — not valid
        return False

    # Skip if it's already has a perfect match (with another shift)
    if other_shifts:
        for s in other_shifts:
            if check_perfect_shift_activity_timings(
                activity=possible_activity, shift=s
            ):
                return False

    return True


def is_valid_linking_shift_candidate(
    possible_shift: Shift,
    existing_exception: Optional[ShiftException] = None,
    other_activities: Optional[List[Activity]] = None,
) -> bool:
    """
    Check whether the given shift is a valid candidate for linking to an activity.

    Args:
        possible_shift (Shift): The shift to validate.
        existing_exception (ShiftException, optional): Existing exception, if any.
        other_activities (List[Activity], optional): Preloaded list of other activities for performance. Used to check if perfect match already exists for possible shift.

    Returns:
        bool: True if this shift is valid for linking, else False.
    """
    related_exception = getattr(possible_shift, "shift_shiftexception", None)

    if related_exception:
        # Allow if already linked to the activity's exception
        if existing_exception and possible_shift == existing_exception.shift:
            return True
        # Allow if the shift exception exists but has no linked activity
        elif not related_exception.activity:
            return True
        # Otherwise it's already a full exception — not valid
        return False

    # Skip if it's already has a perfect match (with another shift)
    if other_activities:
        for a in other_activities:
            if check_perfect_shift_activity_timings(shift=possible_shift, activity=a):
                return False

    return True


def ensure_aware_datetime(dt: datetime) -> datetime:
    """
    Return timezone aware datetime if given niave dt.
    """
    return make_aware(dt) if is_naive(dt) else dt


def schedule_copy_do_shifts_collide(
    shift1_start,
    shift1_end,
    shift2_start,
    shift2_end,
    gap=settings.START_NEW_SHIFT_TIME_DELTA_THRESHOLD_MINS,
):
    """Return True if shift1 and shift2 overlap or are too close."""
    gap_delta = timedelta(minutes=gap)
    return not (
        shift1_end + gap_delta <= shift2_start or shift2_end + gap_delta <= shift1_start
    )
