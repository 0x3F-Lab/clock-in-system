import logging
import api.exceptions as err
import api.utils as util
from typing import List, Tuple
from django.utils.timezone import now
from django.db import transaction
from auth_app.models import User, Activity, KeyValueStore


logger = logging.getLogger("api")


def get_users_name(
    only_active: bool = True,
    ignore_managers: bool = False,
    order: bool = True,
    order_by_first_name: bool = True,
    ignore_clocked_in: bool = False,
) -> List[Tuple[int, str]]:
    """
    Fetches a list of users with their IDs and full names.

    Args:
        only_active (bool): Include only active users if True.
        ignore_managers (bool): Exclude managers if True.
        ignore_clocked_in (bool): Wether to ignore users who are clocked in.
        order (bool): Whether to order by the user's names, otherwise order by their id.
        order_by_first_name (bool): Order by first name if True, otherwise by last name.

    Returns:
        List[Tuple[int, str]]: A list of tuples where each tuple contains user ID and full name.
    """
    # Filter base query
    filters = {"is_active": only_active}
    if ignore_managers:
        filters["is_manager"] = False
    if ignore_clocked_in:
        filters["clocked_in"] = False

    # Fetch filtered users
    users = User.objects.filter(**filters)

    if not users:
        raise User.DoesNotExist("No active clock-in activity found.")

    # Determine ordering
    if order:
        if order_by_first_name:
            # First order by first_name, then by last_name
            users = users.order_by("first_name", "last_name")
        else:
            # First order by last_name, then by first_name
            users = users.order_by("last_name", "first_name")

    # Convert users to compact list
    users_list = list()
    for user in users:
        users_list.append((user.id, f"{user.first_name} {user.last_name}"))

    return users_list


def handle_clock_in(employee_id: int) -> Activity:
    """
    Handles clocking in an employee by ID.

    Args:
        employee_id (int): The employee's ID.

    Returns:
        Activity: An activity object containing the information about the clock in.
    """
    try:
        # Start a database transaction (rolls back on error)
        with transaction.atomic():
            # Fetch the employee (errors if they dont exist)
            employee = User.objects.get(id=employee_id)

            # Check if already clocked in
            if employee.clocked_in:
                raise err.AlreadyClockedInError

            # Update employee clocked-in status
            employee.clocked_in = True
            employee.save()

            time = now()  # Consistent timestamp

            # Create Activity record
            activity = Activity.objects.create(
                employee_id=employee,
                login_timestamp=time,
                login_time=util.round_datetime_minute(
                    time
                ),  # Default to round to nearest 15m
                is_public_holiday=util.is_public_holiday(time),
                deliveries=0,
            )

            return activity

    except err.AlreadyClockedInError:
        # If the user is already clocked in
        raise
    except User.DoesNotExist:
        # If the user is not found
        raise
    except Exception as e:
        # Catch-all exception
        logger.error(
            f"Failed to clock in employee with ID {employee_id}, resulting in the error: {str(e)}"
        )
        raise


def handle_clock_out(employee_id: int, deliveries: int) -> Activity:
    """
    Handles clocking out an employee by ID.

    Args:
        employee_id (int): The employee's ID.
        deliveries (int): Number of deliveries made during the shift.

    Returns:
        Activity: An activity object containing the information about the clock out.
    """
    try:
        # Start a database transaction (rolls back on error)
        with transaction.atomic():
            # Fetch the employee (errors if they dont exist)
            employee = User.objects.get(id=employee_id)

            # Check if not clocked in
            if not employee.clocked_in:
                raise err.AlreadyClockedOutError

            # Fetch the last active clock-in record
            activity = Activity.objects.filter(
                employee_id=employee, logout_time__isnull=True
            ).last()

            if not activity:
                raise err.NoActiveClockingRecordError

            # Update employee clocked-out status and Activity record
            employee.clocked_in = False
            employee.save()

            time = now()
            activity.logout_timestamp = time
            activity.logout_time = util.round_datetime_minute(
                time
            )  # Default to round to nearest 15m
            activity.deliveries = deliveries
            activity.shift_length_mins = util.calculate_shift_length_mins(
                start=activity.login_time, end=activity.logout_time
            )
            activity.save()

            return activity

    except err.AlreadyClockedOutError:
        # If the user is already clocked out.
        raise
    except err.NoActiveClockingRecordError:
        # If the user has no active clocking record (their clock-in activity is missing)
        logger.error(
            f"Failed to clock out employee with ID {employee_id} due to a missing active clocking record (activity)."
        )
        raise
    except User.DoesNotExist:
        # If the user is not found, return 404
        raise
    except Exception as e:
        logger.error(
            f"Failed to clock out employee with ID {employee_id}, resulting in the error: {str(e)}"
        )
        raise


def get_employee_clocked_info(employee_id: int) -> dict:
    """
    Get detailed clocked information for an employee.

    Args:
        employee_id (int): The ID of the employee.

    Returns:
        dict: A dictionary containing employee info and clocked-in details if applicable.
    """
    try:
        employee = User.objects.get(id=employee_id)

        # Form the basic info
        full_name = f"{employee.first_name} {employee.last_name}"
        info = {
            "employee_id": employee_id,
            "name": full_name,
            "clocked_in": employee.clocked_in,
        }

        # If the employee is logged in, add the activity info
        if employee.clocked_in:
            # Fetch the last active clock-in record for the employee
            activity = Activity.objects.filter(
                employee_id=employee, logout_time__isnull=True
            ).last()

            if not activity:
                raise Activity.DoesNotExist("No active clock-in activity found.")

            # Add the clock-in time to the info
            info["login_time"] = activity.login_time
            info["login_timestamp"] = activity.login_timestamp

        return info

    except User.DoesNotExist or Activity.DoesNotExist:
        # Handle user not existing
        raise  # Re-raise error to be caught in view
    except Exception as e:
        # Catch-all exception
        logger.error(
            f"Failed to get clocked information of employee with ID {employee_id}, resulting in the error: {str(e)}"
        )
        raise e  # Re-raise error to be caught in view


def get_store_location() -> tuple[float, float]:
    """
    Gets the store's latitude and longitude from the database to be used to check
    the employee's distance from the store before clocking them in/out.

    Returns:
        (float, float): The latitude and longitude of the store.
    """
    try:
        # Query the values for the specific keys
        store_lat = KeyValueStore.objects.get(key="store_latitude").value
        store_long = KeyValueStore.objects.get(key="store_longitude").value

        # Convert the values to floats (if stored as strings)
        latitude = float(store_lat)
        longitude = float(store_long)

        return latitude, longitude

    except KeyValueStore.DoesNotExist:
        # If the lat or long keys dont exist in the database
        logger.critical(
            "Store latitude or longitude does not exist within database. Please run the setup script."
        )
        raise
    except ValueError as e:
        # If the value stored in the database for the location is not valid
        logger.critical(
            "Store latitude or longitude values in the database are not valid. Please run the setup script to correct."
        )
        raise ValueError(f"Invalid value for store location: {e}")


def get_clocking_range_limit() -> float:
    """
    Gets the maximum allowable distance a user can be from the store's location
    for them to be able to clock in/out.

    Returns:
        float: The distance in meters the user can be from the store.
    """
    try:
        # Query the value for the allowable distance
        dist = KeyValueStore.objects.get(key="allowable_clocking_dist_m").value

        # Convert the value to floats (if stored as strings)
        return float(dist)

    except KeyValueStore.DoesNotExist:
        # If the lat or long keys dont exist in the database
        logger.critical(
            "Allowable distance limit for clocking does not exist within database. Please run the setup script."
        )
        raise
    except ValueError as e:
        # If the value stored in the database for the location is not valid
        logger.critical(
            "Allowable distance limit for clocking in the database is not valid. Please run the setup script to correct."
        )
        raise ValueError(f"Invalid value for store location: {e}")
