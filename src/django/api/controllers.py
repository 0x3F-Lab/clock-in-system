import logging
import api.exceptions as err
import api.utils as util
from typing import List, Tuple
from datetime import timedelta
from django.utils.timezone import now, localtime
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

            # Check if user is inactive
            elif not employee.is_active:
                raise err.InactiveUserError

            # Check if the employee is trying to clock in too soon after their last shift (default=30m)
            if check_new_shift_too_soon(employee_id=employee_id):
                raise err.StartingShiftTooSoonError

            # Update employee clocked-in status
            employee.clocked_in = True
            employee.save()

            time = localtime(now())  # Consistent timestamp

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

    except (
        err.AlreadyClockedInError,
        err.InactiveUserError,
        User.DoesNotExist,
        err.AlreadyClockedInError,
        err.StartingShiftTooSoonError,
    ) as e:
        # Re-raise common errors
        raise e
    except Exception as e:
        # Catch-all exception
        logger.error(
            f"Failed to clock in employee with ID {employee_id}, resulting in the error: {str(e)}"
        )
        raise e


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

            # Check if user is inactive
            elif not employee.is_active:
                raise err.InactiveUserError

            # Fetch the last active clock-in record
            activity = Activity.objects.filter(
                employee_id=employee, logout_time__isnull=True
            ).last()

            if not activity:
                force_fix_user_bugged_clocked_state(
                    employee=employee, employee_id=employee_id
                )
                raise err.NoActiveClockingRecordError(
                    "No active clock-in activity found. Resetting user's clocked state."
                )

            # Check if the employee is trying to clock out too soon after their last shift (default=10m)
            if check_clocking_out_too_soon(employee_id=employee_id):
                raise err.ClockingOutTooSoonError

            # Update employee clocked-out status and Activity record
            employee.clocked_in = False
            employee.save()

            time = localtime(now())
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

    except (
        err.AlreadyClockedOutError,
        User.DoesNotExist,
        err.InactiveUserError,
        err.StartingShiftTooSoonError,
    ) as e:
        # Re-raise common errors
        raise e
    except err.NoActiveClockingRecordError:
        # If the user has no active clocking record (their clock-in activity is missing)
        logger.warning(
            f"Failed to clock out employee with ID {employee_id} due to a missing active clocking record (activity). Their clocked state has been reset to ensure they don't remain bugged."
        )
        raise
    except Exception as e:
        logger.error(
            f"Failed to clock out employee with ID {employee_id}, resulting in the error: {str(e)}"
        )
        raise e


def force_fix_user_bugged_clocked_state(employee: User, employee_id: int) -> bool:
    """
    Forcefully fixes a user's bugged clocked state due to missing activity records.

    Args:
        employee (User): The User instance whose clocked-in state needs correction.
        employee_id (int): The ID of the user whpse clocked-in state needs correction.
        BOTH MUST BE GIVEN!

    Returns:
        bool: Whether the user's state has been reset or not
    """
    try:
        # Ensure they dont have an active activity record before resetting state
        activity = Activity.objects.filter(
            employee_id=employee_id, logout_time__isnull=True
        ).last()

        if activity:
            return False

        # Reset user's clocked state
        employee.clocked_in = False
        employee.save()
        return True

    except Exception as e:
        logger.critical(f"Failed to fix clocked state for {employee.id}: {str(e)}")
        raise Exception(
            f"Failed to fix clocked state for {employee.id} by resetting their state."
        )


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

        # Check employee is not inactive
        if not employee.is_active:
            raise err.InactiveUserError

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
                force_fix_user_bugged_clocked_state(
                    employee=employee, employee_id=employee_id
                )
                raise err.NoActiveClockingRecordError(
                    "No active clock-in activity found. Resetting user's clocked state."
                )

            # Add the clock-in time to the info
            info["login_time"] = activity.login_time
            info["login_timestamp"] = activity.login_timestamp

        return info

    except (User.DoesNotExist, Activity.DoesNotExist, err.InactiveUserError) as e:
        raise e  # Re-raise error to be caught in view
    except err.NoActiveClockingRecordError:
        # If the user has no active clocking record (their clock-in activity is missing)
        logger.warning(
            f"Failed to get clocked status for employee with ID {employee_id} due to a missing active clocking record (activity). Their clocked state has been reset to ensure they don't remain bugged."
        )
        raise
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


def check_new_shift_too_soon(employee_id: int, limit_mins: int = 30) -> bool:
    """
    Check if the user attempts to start a new shift within time limits of their last clock-out.

    Args:
        employee_id (int): The ID of the employee.
        limit_mins (int): The minimum interval in minutes required between clock-out and clock-in. (Default = 30m)

    Returns:
        bool: Returns True if the employee is trying to clock in too soon after their last clock-out, otherwise False.
    """
    try:
        # Get the last clock-out activity for the employee
        last_activity = Activity.objects.filter(
            employee_id=employee_id, logout_timestamp__isnull=False
        ).last()

        if not last_activity:
            # No previous clock-out record found, allow clock-in
            return False

        # Calculate the time difference between the last clock-out and the attempted clock-in
        time_diff = localtime(now()) - last_activity.logout_timestamp

        # Check if the time difference is less than the allowed time gap (x_minutes)
        if time_diff < timedelta(minutes=limit_mins):
            return True

        return False

    except Exception as e:
        raise Exception(
            f"Error checking if employee {employee_id} is attempting to start a shift too soon: {str(e)}"
        )


def check_clocking_out_too_soon(employee_id: int, limit_mins: int = 15) -> bool:
    """
    Check if the user attempts to clock out within time limits after their last clock-in.

    Args:
        employee_id (int): The ID of the employee.
        limit_mins (int): The minimum interval in minutes required between consecutive clock-in and clock-outs. (Default = 15m)
                          Ensure this value equals that of the rounding minutes for shift lengths.

    Returns:
        bool: Returns True if the employee is trying to clock out too soon, otherwise False.
    """
    try:
        # Get the last activity for the employee
        last_activity = (
            Activity.objects.filter(employee_id=employee_id)
            .order_by("-login_timestamp")
            .first()
        )  # Order by latest clock-in/out

        if not last_activity:
            # No previous clock-in or clock-out record found, allow clock-in
            return False

        # Calculate the time difference between the last clock-in/out and the attempted action
        time_diff = localtime(now()) - last_activity.login_timestamp

        # Check if the time difference is less than the allowed time gap (x_minutes)
        if time_diff < timedelta(minutes=limit_mins):
            return True

        return False

    except Exception as e:
        raise Exception(
            f"Error checking if employee {employee_id} is attempting to clock in/out too soon: {str(e)}"
        )


def is_active_account(employee_id: int) -> bool:
    """
    Check if an account with the id is active or inactive.

    Args:
        employee_id (int): The ID of the employee.

    Returns:
        bool: True if the account is active, False otherwise.
    """
    try:
        employee = User.objects.get(id=employee_id)

        # Check employee is not inactive
        if employee.is_active:
            return True

        return False

    except User.DoesNotExist as e:
        raise e  # Re-raise error to be caught in view
    except Exception as e:
        # Catch-all exception
        logger.error(
            f"Failed to check if account is active with ID {employee_id}, resulting in the error: {str(e)}"
        )
        raise e  # Re-raise error to be caught in view
