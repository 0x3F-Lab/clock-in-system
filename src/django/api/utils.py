import math
import requests
import logging
import holidays
import api.exceptions as err
import api.controllers as controllers
from urllib.parse import urlencode
from datetime import datetime, timedelta
from django.utils.timezone import now
from auth_app.models import User
from clock_in_system.settings import COUNTRY_CODE, COUNTRY_SUBDIV_CODE, UTC_OFFSET

logger = logging.getLogger("api")


# Function to check if a given date is a public holiday
def is_public_holiday(
    time, country=COUNTRY_CODE, subdiv=COUNTRY_SUBDIV_CODE, utc_offset=UTC_OFFSET
):
    date = time.date()

    # Check using offline library
    try:
        country_holidays = holidays.country_holidays(country=country, subdiv=subdiv)
        if date in country_holidays:
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
            return True
        elif response.status_code == 204:
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

    # Ensure something returns
    return False


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


def check_pin_hash(employee_id: bool, pin) -> bool:
    # Check if pin was given
    if pin is None:
        raise err.MissingPinError

    # Get employee
    employee = User.objects.get(id=employee_id)

    # Check that they aren't inactive
    if not employee.is_active:
        raise err.InactiveUserError

    # Check if pin is valid
    if employee.check_pin(raw_pin=pin):
        return True

    # Return False by default on failing check
    return False
