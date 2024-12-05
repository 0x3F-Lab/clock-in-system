from typing import List, Tuple
import logging
from django.shortcuts import get_object_or_404
from django.utils.timezone import now
from django.db import transaction
from rest_framework.response import Response
from rest_framework import status
from auth_app.models import User, Activity
from auth_app.serializers import ActivitySerializer
import api.utils as util


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


def handle_clock_in(employee_id: int) -> Response:
    """
    Handles clocking in an employee by ID.

    Args:
        employee_id (int): The employee's ID.

    Returns:
        Response: Serialized Activity object or error message.
    """
    try:
        # Start a database transaction (rolls back on error)
        with transaction.atomic():
            # Fetch the employee (errors if they dont exist)
            employee = User.objects.get(id=employee_id)

            # Check if already clocked in
            if employee.clocked_in:
                return Response(
                    {"Error": "Employee is already clocked in."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Update employee clocked-in status
            employee.clocked_in = True
            employee.save()

            time = now()  # Consistent timestamp

            # Create Activity record
            activity = Activity.objects.create(
                employee_id=employee,
                login_timestamp=time,
                login_time=util.round_datetime_minute(
                    time, rounding_mins=1
                ),  ####################### FOR TESTING SET TO 1MINUTE -- CHANGE BACK LATER
                is_public_holiday=util.is_public_holiday(time),
                deliveries=0,
            )

            return Response(
                ActivitySerializer(activity).data, status=status.HTTP_201_CREATED
            )

    except User.DoesNotExist:
        # If the user is not found, return 404
        return Response(
            {"Error": f"Employee not found with the ID {employee_id}."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        # Catch-all exception
        logger.error(
            f"Failed to clock in employee with ID {employee_id}, resulting in the error: {str(e)}"
        )
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


def handle_clock_out(employee_id: int, deliveries: int) -> Response:
    """
    Handles clocking out an employee by ID.

    Args:
        employee_id (int): The employee's ID.
        deliveries (int): Number of deliveries made during the shift.

    Returns:
        Response: Serialized Activity object or error message.
    """
    try:
        # Start a database transaction (rolls back on error)
        with transaction.atomic():
            # Fetch the employee (errors if they dont exist)
            employee = User.objects.get(id=employee_id)

            # Check if not clocked in
            if not employee.clocked_in:
                return Response(
                    {"Error": "Employee is not clocked in."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Fetch the last active clock-in record
            activity = Activity.objects.filter(
                employee_id=employee, logout_time__isnull=True
            ).last()

            if not activity:
                return Response(
                    {"Error": "No active clock-in record found."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Update employee clocked-out status and Activity record
            employee.clocked_in = False
            employee.save()

            time = now()
            activity.logout_timestamp = time
            activity.logout_time = util.round_datetime_minute(
                time, rounding_mins=1
            )  ####################### FOR TESTING SET TO 1MINUTE -- CHANGE BACK LATER
            activity.deliveries = deliveries
            activity.shift_length_mins = util.calculate_shift_length_mins(
                start=activity.login_time, end=activity.logout_time
            )
            activity.save()

            return Response(
                ActivitySerializer(activity).data, status=status.HTTP_200_OK
            )

    except User.DoesNotExist:
        # If the user is not found, return 404
        return Response(
            {"Error": f"Employee not found with the ID {employee_id}."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.error(
            f"Failed to clock out employee with ID {employee_id}, resulting in the error: {str(e)}"
        )
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
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
