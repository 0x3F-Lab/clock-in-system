import math
import api.exceptions as err
import api.controllers as controllers
from datetime import datetime, timedelta
from django.utils.timezone import now
from auth_app.models import User


# Function to check if a given date is a public holiday
def is_public_holiday(time):
    date = time.date()

    ### USE API CALLS TO CHECK FOR PUBLIC HOLIDAYS!!!

    public_holidays = [
        datetime(2024, 12, 25).date(),  # Example: Christmas Day
        datetime(2024, 1, 1).date(),  # Example: New Year's Day
    ]

    return date in public_holidays


# Function to round the time to the nearest specified minute
def round_datetime_minute(dt, rounding_mins=15):
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


def check_location_data(location_lat, location_long) -> bool:
    """
    Check the location data given is close enough to the store

    Args:
        lat: Latitude of the user.
        lon: Longitude of the user.

    Returns:
        bool: True if the user is close enough to the store, False otherwise.
    """
    # Check to see they exist
    if (location_lat is None) or (location_long is None):
        raise err.MissingLocationDataError

    # Convert to location floats
    try:
        location_lat = float(location_lat)
        location_long = float(location_long)
    except ValueError:
        raise err.BadLocationDataError

    # Get store location and allowable distance
    (store_lat, store_long) = controllers.get_store_location()
    allowable_dist = controllers.get_clocking_range_limit()

    # Obtain distance of user from store
    dist = get_distance_from_lat_lon_in_m(
        lat1=location_lat, lon1=location_long, lat2=store_lat, lon2=store_long
    )

    if dist > allowable_dist:
        return False

    # Return True on successful location data check
    return True


def check_pin_hash(employee_id: bool, hashed_pin) -> bool:
    # Check if pin was given
    if hashed_pin is None:
        raise err.MissingPinError

    # Get employee
    employee = User.objects.get(id=employee_id)

    # Check that they aren't inactive
    if not employee.is_active:
        raise err.InactiveUserError

    # Check if pin is valid
    if not employee.check_pin(raw_pin=hashed_pin):
        return False

    # Return True on successful pin check
    return True
