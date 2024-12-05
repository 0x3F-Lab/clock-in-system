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


def list_users_name(
    only_active: bool = True,
    ignore_managers: bool = False,
    order: bool = True,
    order_by_first_name: bool = True,
    clocked_in: bool = False,
) -> List[Tuple[int, str]]:
    """
    Fetches a list of users with their IDs and full names.

    Args:
        only_active (bool): Include only active users if True.
        ignore_managers (bool): Exclude managers if True.
        order (bool): Whether to order by the user's names, otherwise order by their id.
        order_by_first_name (bool): Order by first name if True, otherwise by last name.
        clocked_in (bool): Filter by clocked-in status.

    Returns:
        List[Tuple[int, str]]: A list of tuples where each tuple contains user ID and full name.
    """
    # Filter base query
    filters = {"is_active": only_active, "clocked_in": clocked_in}
    if ignore_managers:
        filters["is_manager"] = False

    # Fetch filtered users
    users = User.objects.filter(**filters)

    # Determine ordering
    if order:
        order_field = "first_name" if order_by_first_name else "last_name"
        users = users.order_by(order_field)

    # Convert users to compact list
    users_list = List()
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
