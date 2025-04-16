import logging
import json
import api.utils as util
from api.utils import round_datetime_minute, str_to_bool
import api.controllers as controllers
import api.exceptions as err
from rest_framework.decorators import api_view, renderer_classes
from rest_framework.response import Response
from rest_framework import status
from auth_app.models import User, Activity
from auth_app.serializers import ActivitySerializer, ClockedInfoSerializer
from rest_framework.renderers import JSONRenderer
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils.timezone import now, localtime, make_aware
from auth_app.utils import manager_required, api_manager_required
from django.views.decorators.csrf import ensure_csrf_cookie
from clock_in_system.settings import (
    MAX_DATABASE_DUMP_LIMIT,
    FINISH_SHIFT_TIME_DELTA_THRESHOLD,
)

from django.db.models import Sum, F, Q, Case, When, DecimalField
from datetime import datetime, time
from auth_app.models import Activity, User, KeyValueStore
from django.db.models.functions import ExtractWeekDay

logger = logging.getLogger("api")


@api_view(["GET"])
@renderer_classes([JSONRenderer])
def list_users_name_view(request):
    """
    API view to fetch a list of users with their IDs and full names.
    """
    try:
        # Extract query parameters from the request, with defaults
        only_active = request.query_params.get("only_active", "true").lower() == "true"
        ignore_managers = (
            request.query_params.get("ignore_managers", "false").lower() == "true"
        )
        order = request.query_params.get("order", "true").lower() == "true"
        order_by_first_name = (
            request.query_params.get("order_by_first_name", "true").lower() == "true"
        )
        ignore_clocked_in = (
            request.query_params.get("ignore_clocked_in", "false").lower() == "true"
        )

        # Call the controller function
        users_list = controllers.get_users_name(
            only_active=only_active,
            ignore_managers=ignore_managers,
            order=order,
            order_by_first_name=order_by_first_name,
            ignore_clocked_in=ignore_clocked_in,
        )

        # Return the list of users in the response
        return Response(users_list, status=status.HTTP_200_OK)

    except User.DoesNotExist:
        # Return a 404 if the user does not exist
        return Response(
            {"Error": "No users found matching the given criteria."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        # Handle any unexpected exceptions
        logger.critical(f"Failed to list all users, resulting in the error: {str(e)}")
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_manager_required
@api_view(["GET"])
@renderer_classes([JSONRenderer])
def list_all_shift_details(request):
    try:
        try:
            # enforce min offset = 0
            offset = max(int(request.GET.get("offset", "0")), 0)
        except ValueError:
            offset = 0

        try:
            # Enforce min limit = 1 and max limit = 150 (settings controlled)
            limit = min(
                max(int(request.GET.get("limit", "25")), 1), MAX_DATABASE_DUMP_LIMIT
            )
        except ValueError:
            limit = 25

        # Query & order: by login_timestamp DESC, then first_name, last_name ASC (JOIN TABLE WITH USERS TO GET THEIR INFO AS WELL)
        activities_query = Activity.objects.select_related("employee_id").order_by(
            "-login_timestamp", "employee_id__first_name", "employee_id__last_name"
        )

        # Get total
        total = activities_query.count()

        # Ensure slicing happens on DB level for most performance
        activities = activities_query[offset : offset + limit]

        data = []
        for act in activities:
            hours_decimal = (
                (act.shift_length_mins / 60.0) if act.shift_length_mins else 0.0
            )

            data.append(
                {
                    "id": act.id,
                    "employee_first_name": act.employee_id.first_name,
                    "employee_last_name": act.employee_id.last_name,
                    "login_time": (
                        localtime(act.login_time).strftime("%H:%M")
                        if act.login_time
                        else "N/A"
                    ),
                    "logout_time": (
                        localtime(act.logout_time).strftime("%H:%M")
                        if act.logout_time
                        else "N/A"
                    ),
                    "is_public_holiday": act.is_public_holiday,
                    "login_timestamp": (
                        localtime(act.login_timestamp).strftime("%d/%m/%Y %H:%M")
                        if act.login_timestamp
                        else "N/A"
                    ),
                    "logout_timestamp": (
                        localtime(act.logout_timestamp).strftime("%d/%m/%Y %H:%M")
                        if act.logout_timestamp
                        else "N/A"
                    ),
                    "deliveries": act.deliveries,
                    "hours_worked": f"{hours_decimal:.2f}",
                }
            )

        return JsonResponse(
            {
                "total": total,
                "offset": offset,
                "limit": limit,
                "results": data,
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        # Handle any unexpected exceptions
        logger.critical(
            f"Failed to list all shift details (full dump), resulting in the error: {str(e)}"
        )
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_manager_required
@api_view(["GET"])
def list_singular_shift_details(request, id):
    try:
        act = Activity.objects.get(id=id)

        activity_data = {
            "id": id,
            "login_timestamp": (
                localtime(act.login_timestamp).strftime("%d/%m/%Y %H:%M")
                if act.login_timestamp
                else "N/A"
            ),
            "logout_timestamp": (
                localtime(act.logout_timestamp).strftime("%d/%m/%Y %H:%M")
                if act.logout_timestamp
                else "N/A"
            ),
            "is_public_holiday": act.is_public_holiday,
            "deliveries": act.deliveries,
        }

        return JsonResponse(activity_data, status=status.HTTP_200_OK)

    except Activity.DoesNotExist as e:
        return Response(
            {"Error": f"Shift with ID {id} does not exist."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        # Handle any unexpected exceptions
        logger.critical(
            f"Failed to list activity details for ID {id}, resulting in the error: {str(e)}"
        )
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_manager_required
@api_view(["POST", "PATCH", "DELETE"])
@renderer_classes([JSONRenderer])
def update_shift_details(request, id):
    try:
        activity = Activity.objects.get(id=id)

        # If DELETING the activity
        if request.method == "DELETE":
            activity.delete()

            return JsonResponse(
                {"message": "Employee deleted successfully"},
                status=status.HTTP_200_OK,
            )

        elif (request.method == "POST") or (request.method == "PATCH"):
            # Parse data from request
            data = json.loads(request.body)

            if data.get("login_timestamp") is not None:
                login_timestamp = datetime.strptime(
                    data.get("login_timestamp"), "%Y-%m-%dT%H:%M:%S"
                )
                activity.login_time = round_datetime_minute(login_timestamp)
                activity.login_timestamp = login_timestamp

            if data.get("logout_timestamp") is not None:
                logout_timestamp = datetime.strptime(
                    data.get("logout_timestamp"), "%Y-%m-%dT%H:%M:%S"
                )
                activity.logout_time = round_datetime_minute(logout_timestamp)
                activity.logout_timestamp = logout_timestamp

            # If finishing a shift manually, check that the user doesnt need to be clocked out
            if activity.logout_time is not None:
                user_latest_activity = (
                    Activity.objects.filter(employee_id=activity.employee_id)
                    .order_by("-login_timestamp")
                    .first()
                )
                user = activity.employee_id  # Get the user from the activity

                # If the user's latest activity is the current one being edited and they're clocked in (manually being clocked out) their state needs to be manually modified
                if (activity.id == user_latest_activity.id) and (user.clocked_in):
                    user.clocked_in = False
                    user.save()

            # Set public holiday state (keep same if not given)
            activity.is_public_holiday = str_to_bool(
                data.get("is_public_holiday", activity.is_public_holiday)
            )

            # Set deliveries (keep same if not given)
            try:
                activity.deliveries = int(data.get("deliveries", activity.deliveries))
            except ValueError:
                return JsonResponse(
                    {"Error": "Deliveries must be an integer."},
                    status=status.HTTP_412_PRECONDITION_FAILED,
                )

            # Update shift length if both login and logout time exist
            if activity.login_time and activity.logout_time:
                # Check that logout time is not before login time
                if activity.logout_time < activity.login_time:
                    return JsonResponse(
                        {"Error": "Logout time cannot be before login time."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Update shift length
                delta = activity.logout_time - activity.login_time
                activity.shift_length_mins = int(delta.total_seconds() // 60)

                # Check that shift length reaches minimum required shift length
                if activity.shift_length_mins < FINISH_SHIFT_TIME_DELTA_THRESHOLD:
                    return JsonResponse(
                        {
                            "Error": f"Rounded shift duration must be at least {FINISH_SHIFT_TIME_DELTA_THRESHOLD.total_seconds() // 60:.0f} minutes."
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            activity.save()
            return JsonResponse(
                {"message": "Shift updated successfully."},
                status=status.HTTP_202_ACCEPTED,
            )

        else:
            return Response(
                {"Error": "Invalid method."},
                status=status.HTTP_405_METHOD_NOT_ALLOWED,
            )

    except ValueError as e:
        return Response(
            {"Error": "Times must be sent in ISO8601 format (YYYY-MM-DDTHH:MM:SS)."},
            status=status.HTTP_412_PRECONDITION_FAILED,
        )
    except Activity.DoesNotExist as e:
        return Response(
            {"Error": f"Shift with ID {id} does not exist."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        # Handle any unexpected exceptions
        logger.critical(
            f"Failed to update activity details for ID {id}, resulting in the error: {str(e)}"
        )
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_manager_required
@api_view(["PUT"])
@renderer_classes([JSONRenderer])
def create_new_shift(request):
    try:
        # Parse data from request
        data = json.loads(request.body)
        employee_id = str(data.get("employee_id", ""))
        login_timestamp = data.get(
            "login_timestamp", None
        )  # Type checking done when checking their form
        logout_timestamp = data.get("logout_timestamp", None)
        is_public_holiday = str_to_bool(data.get("is_public_holiday", False))

        try:
            deliveries = int(data.get("deliveries", 0))
        except ValueError as e:
            return Response(
                {"Error": "Deliveries must be an integer."},
                status=status.HTTP_417_EXPECTATION_FAILED,
            )

        # Check that the request is not missing the employee ID or the login timestamp (REQUIRED)
        if not employee_id or not login_timestamp:
            return JsonResponse(
                {"Error": "Required fields are missing. (Employee and Login time)"},
                status=status.HTTP_417_EXPECTATION_FAILED,
            )

        # Ensure the timestamps are in the correct form
        try:
            login_timestamp = datetime.strptime(login_timestamp, "%Y-%m-%dT%H:%M:%S")
            if logout_timestamp:
                logout_timestamp = datetime.strptime(
                    logout_timestamp, "%Y-%m-%dT%H:%M:%S"
                )
        except ValueError as e:
            return Response(
                {
                    "Error": "Times must be sent in ISO8601 format (YYYY-MM-DDTHH:MM:SS)."
                },
                status=status.HTTP_412_PRECONDITION_FAILED,
            )

        # Check if login_timestamp is in the future
        if login_timestamp > now():
            return JsonResponse(
                {"Error": "Login time cannot be in the future."},
                status=status.HTTP_417_EXPECTATION_FAILED,
            )

        # Check if logout_timestamp is in the future
        if (logout_timestamp) and (login_timestamp > now()):
            return JsonResponse(
                {"Error": "Logout time cannot be in the future."},
                status=status.HTTP_417_EXPECTATION_FAILED,
            )

        # Get the rounded login/logout times
        login_time = round_datetime_minute(login_timestamp)
        logout_time = None
        if logout_timestamp:
            logout_time = round_datetime_minute(logout_timestamp)

        # Ensure minimum shift length is achieve between login and logout
        if logout_timestamp:
            if logout_time < login_time:
                return JsonResponse(
                    {"Error": "Logout time cannot be before login time."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if (logout_timestamp - login_time) < FINISH_SHIFT_TIME_DELTA_THRESHOLD:
                return JsonResponse(
                    {
                        "Error": f"Rounded shift duration must be at least {FINISH_SHIFT_TIME_DELTA_THRESHOLD.total_seconds() // 60:.0f} minutes."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Get the employee
        employee = User.objects.get(id=employee_id)

        # Create the new activity record
        activity = Activity.objects.create(
            employee_id=employee,
            login_time=login_time,
            logout_time=logout_time,
            login_timestamp=login_timestamp,
            logout_timestamp=logout_timestamp,
            is_public_holiday=is_public_holiday,
            deliveries=deliveries,
        )

        activity.save()

        return JsonResponse(
            {"message": "Shift created successfully.", "id": activity.id},
            status=status.HTTP_201_CREATED,
        )

    except User.DoesNotExist as e:
        return Response(
            {"Error": f"Employee with ID {id} does not exist."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        # Handle any unexpected exceptions
        logger.critical(
            f"Failed to create new shift for employee ID {employee_id}, resulting in the error: {str(e)}"
        )
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_manager_required
@api_view(["GET"])
@renderer_classes([JSONRenderer])
def list_all_employee_details(request):
    try:
        try:
            # enforce min offset = 0
            offset = max(int(request.GET.get("offset", "0")), 0)
        except ValueError:
            offset = 0

        try:
            # Enforce min limit = 1 and max limit = 150 (settings controlled)
            limit = min(
                max(int(request.GET.get("limit", "25")), 1), MAX_DATABASE_DUMP_LIMIT
            )
        except ValueError:
            limit = 25

        # Apply slicing (converted to SQL level by django)
        employees = User.objects.order_by("first_name", "last_name")[
            offset : offset + limit
        ]

        # Get total
        total = User.objects.count()

        employee_data = [
            {
                "id": emp.id,
                "first_name": emp.first_name,
                "last_name": emp.last_name,
                "email": emp.email,
                "phone_number": emp.phone_number,
                "pin": emp.pin,
                "is_active": emp.is_active,
            }
            for emp in employees
        ]
        return JsonResponse(
            {
                "total": total,
                "offset": offset,
                "limit": limit,
                "results": employee_data,
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        # Handle any unexpected exceptions
        logger.critical(
            f"Failed to list all employee data (full dump), resulting in the error: {str(e)}"
        )
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_manager_required
@api_view(["GET"])
def list_singular_employee_details(request, id):
    try:
        employee = User.objects.get(id=id)

        employee_data = {
            "id": id,
            "first_name": employee.first_name,
            "last_name": employee.last_name,
            "email": employee.email,
            "phone_number": employee.phone_number,
            "pin": employee.pin,
            "is_active": employee.is_active,
        }

        return JsonResponse(employee_data)

    except User.DoesNotExist as e:
        return Response(
            {"Error": f"Employee with ID {id} does not exist."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        # Handle any unexpected exceptions
        logger.critical(
            f"Failed to list employee details for ID {id}, resulting in the error: {str(e)}"
        )
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_manager_required
@api_view(["POST", "PATCH"])
@renderer_classes([JSONRenderer])
def update_employee_details(request, id):
    try:
        employee = User.objects.get(id=id)

        if not employee.is_active:
            raise err.InactiveUserError

        # Parse data from request
        data = json.loads(request.body)
        employee.first_name = str(data.get("first_name", employee.first_name))
        employee.last_name = str(data.get("last_name", employee.last_name))
        employee.email = str(data.get("email", employee.email))
        employee.phone_number = str(data.get("phone", employee.phone_number))

        if data.get("pin") is not None:
            employee.set_pin(str(data["pin"]))

        ########## CHECKS ON THIS IS NEEDED!!!

        employee.save()
        return JsonResponse(
            {"message": "Employee updated successfully."},
            status=status.HTTP_202_ACCEPTED,
        )

    except User.DoesNotExist as e:
        return Response(
            {"Error": f"Employee with ID {id} does not exist."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except err.InactiveUserError as e:
        return Response(
            {"Error": "Cannot update an incative employee's details."},
            status=status.HTTP_409_CONFLICT,
        )
    except Exception as e:
        # Handle any unexpected exceptions
        logger.critical(
            f"Failed to update employee details for ID {id}, resulting in the error: {str(e)}"
        )
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_manager_required
@api_view(["PUT"])
@renderer_classes([JSONRenderer])
def create_new_employee(request):
    try:
        # Parse data from request
        data = json.loads(request.body)
        first_name = str(data.get("first_name", ""))
        last_name = str(data.get("last_name", ""))
        email = str(data.get("email", ""))
        phone_number = str(data.get("phone", ""))
        pin = str(data.get("pin", ""))

        ########## CHECKS ON THIS IS NEEDED!!!

        # You can add validation or checks here
        if not first_name or not last_name or not email:
            return JsonResponse(
                {"Error": "Required fields are missing."},
                status=status.HTTP_417_EXPECTATION_FAILED,
            )

        # Ensure email is unique
        if User.objects.filter(email=email).exists():
            return JsonResponse(
                {"Error": "Email already exists."},
                status=status.HTTP_409_CONFLICT,
            )

        # Create user
        employee = User.objects.create(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone_number=phone_number,
            pin=pin,
            is_active=True,  # or set as needed
            is_manager=False,  # presumably a normal employee
        )

        employee.save()

        return JsonResponse(
            {"message": "Employee created successfully.", "id": employee.id},
            status=status.HTTP_201_CREATED,
        )

    except Exception as e:
        # Handle any unexpected exceptions
        logger.critical(
            f"Failed to create new employee account for email {email}, resulting in the error: {str(e)}"
        )
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_manager_required
@api_view(["PUT"])
@renderer_classes([JSONRenderer])
def modify_account_status(request, id):
    try:
        # Parse data from request
        data = json.loads(request.body)
        status_type = str(data.get("status_type", ""))

        ########## CHECKS ON THIS IS NEEDED!!!

        # You can add validation or checks here
        if not status_type:
            return JsonResponse(
                {"Error": "Required status type field missing."},
                status=status.HTTP_417_EXPECTATION_FAILED,
            )

        # Get employee
        employee = User.objects.get(id=id)

        # If account deactivation
        if status_type.lower() == "deactivation":
            employee.is_active = False

        elif status_type.lower() == "activation":
            employee.is_active = True

        else:
            return JsonResponse(
                {"Error": "Invalid status type to modify.", "id": employee.id},
                status=status.HTTP_406_NOT_ACCEPTABLE,
            )

        employee.save()

        return JsonResponse(
            {"message": "Employee status updated successfully.", "id": employee.id},
            status=status.HTTP_202_ACCEPTED,
        )

    except User.DoesNotExist as e:
        return Response(
            {"Error": f"Employee with ID {id} does not exist."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        # Handle any unexpected exceptions
        logger.critical(
            f"Failed to update employee status of type '{status_type}' for ID {id}, resulting in the error: {str(e)}"
        )
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST", "PUT"])
def clock_in(request, id):
    try:
        # Get location data
        location_lat = request.data.get("location_latitude", None)
        location_long = request.data.get("location_longitude", None)

        # Perform general checks on location data (and if its close to store)
        if not util.check_location_data(
            location_lat=location_lat, location_long=location_long
        ):
            raise err.InvalidLocationError

        # Get hashed pin to check they're authorised
        pin = request.data.get("pin", None)

        # Perform checks against pin in database
        if not util.check_pin_hash(employee_id=id, pin=pin):
            raise err.InvalidPinError

        # Clock the user in
        activity = controllers.handle_clock_in(employee_id=id)

        # Return the results after serialisation
        return Response(
            ActivitySerializer(activity).data, status=status.HTTP_201_CREATED
        )

    except err.MissingLocationDataError:
        # If the request is missing the location data
        return Response(
            {"Error": "Missing location data in request."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except err.BadLocationDataError:
        # If the location data is incorrectly formed (not a float)
        return Response(
            {"Error": "Invalid location values."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except err.InvalidLocationError:
        # If the request was performed outside the store's range
        return Response(
            {"Error": "Not close enough to the store to clock in."},
            status=status.HTTP_406_NOT_ACCEPTABLE,
        )
    except err.MissingPinError:
        # If the request is missing the authentication pin
        return Response(
            {"Error": "Missing authentication pin in request."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except err.InvalidPinError:
        # If the authentication pin is invalid
        return Response(
            {"Error": "Invalid authentication pin."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    except err.AlreadyClockedInError:
        # If the user is already clocked in
        return Response(
            {"Error": "Employee is already clocked in."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except err.InactiveUserError:
        # If the user is trying to clock in an inactive account
        return Response(
            {"Error": "Cannot clock in an inactive account."},
            status=status.HTTP_403_FORBIDDEN,
        )
    except User.DoesNotExist:
        # If the user is not found, return 404
        return Response(
            {"Error": f"Employee not found with the ID {id}."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except err.StartingShiftTooSoonError:
        # If the user is trying to start a shift too soon after their last shift
        return Response(
            {"Error": f"Can't start a shift too soon after your last shift."},
            status=status.HTTP_409_CONFLICT,
        )
    except Exception as e:
        # General error capture -- including database location errors
        logger.critical(f"An error occured when clocking in employee ID '{id}': {e}")
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST", "PUT"])
def clock_out(request, id):
    try:
        # Check if they made any deliveries on clock out
        deliveries = max(
            int(request.data.get("deliveries", 0)),
            0,  # Ensure it's an integer and above 0
        )

        # Get location data
        location_lat = request.data.get("location_latitude", None)
        location_long = request.data.get("location_longitude", None)

        # Perform general checks on location data (and if its close to store)
        if not util.check_location_data(
            location_lat=location_lat, location_long=location_long
        ):
            raise err.InvalidLocationError

        # Get hashed pin to check they're authorised
        pin = request.data.get("pin", None)

        # Perform checks against pin in database
        if not util.check_pin_hash(employee_id=id, pin=pin):
            raise err.InvalidPinError

        # Clock the user out
        activity = controllers.handle_clock_out(employee_id=id, deliveries=deliveries)

        # Return the results after serialisation
        return Response(ActivitySerializer(activity).data, status=status.HTTP_200_OK)

    except err.MissingLocationDataError:
        # If the request is missing the location data
        return Response(
            {"Error": "Missing location data in request."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except err.BadLocationDataError:
        # If the location data is incorrectly formed (not a float)
        return Response(
            {"Error": "Invalid location values."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except err.InvalidLocationError:
        # If the request was performed outside the store's range
        return Response(
            {"Error": "Not close enough to the store to clock out."},
            status=status.HTTP_406_NOT_ACCEPTABLE,
        )
    except err.MissingPinError:
        # If the request is missing the authentication pin
        return Response(
            {"Error": "Missing authentication pin in request."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except err.InvalidPinError:
        # If the authentication pin is invalid
        return Response(
            {"Error": "Invalid authentication pin."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    except err.AlreadyClockedOutError:
        # If the user is already clocked out.
        return Response(
            {"Error": "Employee is not clocked in."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except err.NoActiveClockingRecordError:
        # If the user has no active clocking record (their clock-in activity is missing)
        return Response(
            {
                "Error": "No active clock-in record found. The account's state has been reset."
            },
            status=status.HTTP_417_EXPECTATION_FAILED,
        )
    except User.DoesNotExist:
        # If the user is not found, return 404
        return Response(
            {"Error": f"Employee not found with the ID {id}."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except err.InactiveUserError:
        # If the user is trying to clock out an inactive account
        return Response(
            {"Error": "Cannot clock out an inactive account."},
            status=status.HTTP_403_FORBIDDEN,
        )
    except err.ClockingOutTooSoonError:
        # If the user is trying to clock out too soon after clocking in
        return Response(
            {"Error": f"Can't clock out too soon after clocking in."},
            status=status.HTTP_409_CONFLICT,
        )
    except Exception as e:
        # General error capture -- including database location errors
        logger.critical(
            f"An error occured when trying to clock out employee ID '{id}': {e}"
        )
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
def clocked_state_view(request, id):
    """
    API view to get the clocked-in state of a user by ID.
    """
    try:
        # Get the user's info
        info = controllers.get_employee_clocked_info(employee_id=id)

        # Return the info
        return Response(ClockedInfoSerializer(info).data, status=status.HTTP_200_OK)

    except User.DoesNotExist:
        # Return a 404 if the user does not exist
        return Response(
            {"Error": f"User not found with ID {id}."}, status=status.HTTP_404_NOT_FOUND
        )
    except err.InactiveUserError:
        # If the user is trying to view the data of an inactive account
        return Response(
            {"Error": "Cannot view information from an inactive account."},
            status=status.HTTP_403_FORBIDDEN,
        )
    except err.NoActiveClockingRecordError:
        # If the user has no active clocking record (their clock-in activity is missing)
        logger.error(
            f"User with ID {id} has a bugged state due to missing activity record to complete a shift record. Their state has been reset"
        )
        return Response(
            {
                "Error": "No active clock-in record found. The account's state has been reset."
            },
            status=status.HTTP_417_EXPECTATION_FAILED,
        )
    except Exception as e:
        logger.critical(
            f"An error occured when trying to get the clocked state of employee ID '{id}': {e}"
        )
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@manager_required
@ensure_csrf_cookie
@api_view(["GET"])
@renderer_classes([JSONRenderer])
def weekly_summary_view(request):
    start_date_str = request.query_params.get("start_date")
    end_date_str = request.query_params.get("end_date")
    employee_ids_str = request.query_params.get("employee_ids")

    try:
        # Handle date range
        if start_date_str and end_date_str:
            try:
                start_day = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                end_day = datetime.strptime(end_date_str, "%Y-%m-%d").date()

                start_date = make_aware(datetime.combine(start_day, time.min))
                end_date = make_aware(datetime.combine(end_day, time.max))

                activities = Activity.objects.filter(
                    login_time__gte=start_date, login_time__lte=end_date
                )
            except ValueError:
                return Response(
                    {"error": "Invalid date format. Use YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            # No date range provided, use last reset date
            try:
                kv = KeyValueStore.objects.get(key="last_weekly_summary_reset")
                last_reset_date = datetime.strptime(kv.value, "%Y-%m-%d").date()
                last_reset_date = make_aware(
                    datetime.combine(last_reset_date, time.min)
                )
            except KeyValueStore.DoesNotExist:
                # Fallback date
                last_reset_date = make_aware(datetime(2023, 3, 15))

            activities = Activity.objects.filter(login_time__gte=last_reset_date)

        # Handle employee filter
        if employee_ids_str:
            employee_ids = [
                int(e_id.strip())
                for e_id in employee_ids_str.split(",")
                if e_id.strip().isdigit()
            ]
            if employee_ids:
                activities = activities.filter(employee_id__in=employee_ids)

        # Calculate hours by converting shift_length_mins to hours
        # Note: Exclude public holiday hours from weekday/weekend columns
        summary = (
            activities.annotate(day_of_week=ExtractWeekDay("login_time"))
            .values("employee_id", "employee_id__first_name", "employee_id__last_name")
            .annotate(
                weekday_hours=Sum(
                    Case(
                        When(
                            Q(day_of_week__in=[2, 3, 4, 5, 6])
                            & Q(is_public_holiday=False),
                            then=F("shift_length_mins") / 60.0,
                        ),
                        default=0,
                        output_field=DecimalField(decimal_places=2, max_digits=6),
                    )
                ),
                weekend_hours=Sum(
                    Case(
                        When(
                            Q(day_of_week__in=[1, 7]) & Q(is_public_holiday=False),
                            then=F("shift_length_mins") / 60.0,
                        ),
                        default=0,
                        output_field=DecimalField(decimal_places=2, max_digits=6),
                    )
                ),
                public_holiday_hours=Sum(
                    Case(
                        When(
                            is_public_holiday=True, then=F("shift_length_mins") / 60.0
                        ),
                        default=0,
                        output_field=DecimalField(decimal_places=2, max_digits=6),
                    )
                ),
                total_hours=Sum(F("shift_length_mins") / 60.0),
                total_deliveries=Sum("deliveries"),
            )
            .order_by("employee_id__first_name", "employee_id__last_name")
        )

        data = [
            {
                "employee_id": item["employee_id"],
                "first_name": item["employee_id__first_name"],
                "last_name": item["employee_id__last_name"],
                "weekday_hours": float(item["weekday_hours"] or 0.0),
                "weekend_hours": float(item["weekend_hours"] or 0.0),
                "public_holiday_hours": float(item["public_holiday_hours"] or 0.0),
                "total_hours": float(item["total_hours"] or 0.0),
                "total_deliveries": item["total_deliveries"] or 0,
            }
            for item in summary
        ]

        return Response(data, status=status.HTTP_200_OK)

    except Exception as e:
        logger.critical(f"An error occurred when generating weekly summary: {e}")
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@manager_required
@ensure_csrf_cookie
@api_view(["POST"])
@renderer_classes([JSONRenderer])
def reset_summary_view(request):
    # If a new date is provided in the POST, use it, otherwise today
    new_date_str = request.data.get("new_reset_date")
    if new_date_str:
        try:
            # Validate the date format
            datetime.strptime(new_date_str, "%Y-%m-%d")
        except ValueError:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        today_str = new_date_str
    else:
        # Default to today if no date provided
        today_str = now().date().isoformat()

    kv, created = KeyValueStore.objects.get_or_create(
        key="last_weekly_summary_reset", defaults={"value": today_str}
    )
    if not created:
        kv.value = today_str
        kv.save()

    return Response(
        {"message": "Weekly summary reset successfully", "reset_date": today_str},
        status=status.HTTP_200_OK,
    )


@manager_required
@ensure_csrf_cookie
@renderer_classes([JSONRenderer])
def weekly_summary_page(request):
    # Return the HTML template
    return render(request, "auth_app/weekly_summary.html")


@api_view(["POST", "PUT"])
def change_pin(request, id):
    try:
        # Get new pin
        new_pin = request.data.get("new_pin", None)

        # Check if new pin exists
        if new_pin is None:
            return Response(
                {"Error": "Missing new authentication pin."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get hashed pin to check they're authorised
        current_pin = request.data.get("current_pin", None)

        # Perform checks against pin in database
        if not util.check_pin_hash(employee_id=id, pin=current_pin):
            raise err.InvalidPinError

        # Update the pin
        employee = User.objects.get(id=id)
        employee.set_pin(raw_pin=new_pin)
        employee.save()

        return Response(
            {"message": f"Pin for account ID {id} has been updated."},
            status=status.HTTP_200_OK,
        )

    except err.MissingPinError:
        # If the request is missing the authentication pin
        return Response(
            {"Error": "Missing authentication pin in request."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except err.InvalidPinError:
        # If the authentication pin is invalid
        return Response(
            {"Error": "Invalid authentication pin."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    except User.DoesNotExist:
        # If the user is not found, return 404
        return Response(
            {"Error": f"Employee not found with the ID {id}."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except err.InactiveUserError:
        # If the user is trying to change pin of an inactive account
        return Response(
            {"Error": "Cannot change the pin of an inactive account."},
            status=status.HTTP_403_FORBIDDEN,
        )
    except Exception as e:
        # General error capture
        logger.critical(f"An error occured when changing employee pin: {e}")
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
