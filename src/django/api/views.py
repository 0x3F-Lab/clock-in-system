import logging
import re
import api.utils as util
import api.controllers as controllers
import api.exceptions as err
from datetime import datetime
from api.utils import round_datetime_minute, str_to_bool
from rest_framework.decorators import api_view, renderer_classes
from rest_framework.response import Response
from rest_framework import status
from auth_app.models import User, Activity, Store, StoreUserAccess
from auth_app.serializers import ActivitySerializer, ClockedInfoSerializer
from rest_framework.renderers import JSONRenderer
from django.db import transaction, IntegrityError
from django.shortcuts import render
from django.http import JsonResponse
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.utils.timezone import now, localtime, make_aware
from auth_app.utils import manager_required, api_manager_required, api_employee_required
from django.views.decorators.csrf import ensure_csrf_cookie
from clock_in_system.settings import (
    MAX_DATABASE_DUMP_LIMIT,
    FINISH_SHIFT_TIME_DELTA_THRESHOLD_MINS,
    VALID_NAME_PATTERN,
    VALID_PHONE_NUMBER_PATTERN,
)

from django.db.models import Sum, F, Q, Case, When, DecimalField
from datetime import time
from auth_app.models import Activity, User, KeyValueStore
from django.db.models.functions import ExtractWeekDay

logger = logging.getLogger("api")


@api_manager_required
@api_view(["GET"])
@renderer_classes([JSONRenderer])
def list_store_employee_names(request):
    """
    API view to fetch a list of users with their IDs and full names who are related to a certain store.
    The authenticated user MUST be associated to the store to list their employees.
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
        store_id = request.query_params.get("store_id", None)

        if store_id is None:
            return Response(
                {"Error": "Missing store id in request params. Please try again."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get the user information of the manager requesting this info from their session
        try:
            user_id = request.session.get("user_id")
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {
                    "Error": "Failed to get your account's information for authorisation. Please login again."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Ensure user is associated with the store
        if not user.is_associated_with_store(store=int(store_id)):
            return Response(
                {"Error": "Cannot list employee names for an unassociated store."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Call the controller function
        users_list = controllers.get_store_employee_names(
            store_id=store_id,
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

        # Get store id
        store_id = request.GET.get("store_id", None)

        if store_id is None:
            return Response(
                {
                    "Error": "Missing required store_id field in query params. Please retry."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get the account info of the user requesting these shifts
        user_id = request.session.get("user_id")
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {
                    "Error": "Failed to get your account's information for authorisation. Please login again."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user.is_associated_with_store(store=int(store_id)):
            return Response(
                {"Error": "Cannot get shift information for an unassociated store."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Query & order: by login_timestamp DESC, then first_name, last_name ASC (JOIN TABLE WITH USERS TO GET THEIR INFO AS WELL)
        activities_query = (
            Activity.objects.select_related("employee")
            .filter(
                store_id=int(store_id), employee__is_hidden=False
            )  # Exclude hidden users
            .order_by("-login_timestamp", "employee__first_name", "employee__last_name")
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
                    "employee_first_name": act.employee.first_name,
                    "employee_last_name": act.employee.last_name,
                    "login_time": (
                        localtime(act.login_time).strftime("%H:%M")
                        if act.login_time
                        else None
                    ),
                    "logout_time": (
                        localtime(act.logout_time).strftime("%H:%M")
                        if act.logout_time
                        else None
                    ),
                    "is_public_holiday": act.is_public_holiday,
                    "login_timestamp": (
                        localtime(act.login_timestamp).strftime("%d/%m/%Y %H:%M")
                        if act.login_timestamp
                        else None
                    ),
                    "logout_timestamp": (
                        localtime(act.logout_timestamp).strftime("%d/%m/%Y %H:%M")
                        if act.logout_timestamp
                        else None
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

        # Get the account info of the user requesting this shift info
        manager_id = request.session.get("user_id")
        manager = User.objects.get(id=manager_id)

        if not manager.is_associated_with_store(store=act.store):
            return Response(
                {"Error": "Cannot get shift information for an unassociated store."},
                status=status.HTTP_403_FORBIDDEN,
            )

        activity_data = {
            "id": id,
            "login_timestamp": (
                localtime(act.login_timestamp).strftime("%d/%m/%Y %H:%M")
                if act.login_timestamp
                else None
            ),
            "logout_timestamp": (
                localtime(act.logout_timestamp).strftime("%d/%m/%Y %H:%M")
                if act.logout_timestamp
                else None
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
    except User.DoesNotExist as e:
        return Response(
            {
                "Error": "Failed to get your account's information for authorisation. Please login again."
            },
            status=status.HTTP_403_FORBIDDEN,
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
        activity = Activity.objects.select_related("employee", "store").get(id=id)

        # Get the account info of the user requesting this shift info
        manager_id = request.session.get("user_id")
        manager = User.objects.get(id=manager_id)

        if not manager.is_associated_with_store(store=activity.store):
            return Response(
                {
                    "Error": "Cannot update a shift's information for an unassociated store."
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        elif activity.employee.is_hidden:
            return Response(
                {"Error": "Not authorised to interact with a hidden account."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # If DELETING the activity
        if request.method == "DELETE":
            with transaction.atomic():
                activity.delete()

            return JsonResponse(
                {"message": "Employee deleted successfully"},
                status=status.HTTP_200_OK,
            )

        elif (request.method == "POST") or (request.method == "PATCH"):
            # Parse data from request
            login_timestamp = request.data.get("login_timestamp", None) or None
            logout_timestamp = request.data.get("logout_timestamp", None) or None

            try:
                if login_timestamp:
                    login_timestamp = datetime.strptime(
                        login_timestamp, "%Y-%m-%dT%H:%M:%S"
                    )
                    login_timestamp = make_aware(
                        login_timestamp
                    )  # Add timezone information to timstamp
                    activity.login_time = round_datetime_minute(login_timestamp)
                    activity.login_timestamp = login_timestamp
                else:
                    return Response(
                        {"Error": "Login timestamp cannot be empty. Please try again."},
                        status=status.HTTP_412_PRECONDITION_FAILED,
                    )

                if logout_timestamp:
                    logout_timestamp = datetime.strptime(
                        logout_timestamp, "%Y-%m-%dT%H:%M:%S"
                    )
                    logout_timestamp = make_aware(
                        logout_timestamp
                    )  # Add timezone information to timstamp
                    activity.logout_time = round_datetime_minute(logout_timestamp)
                    activity.logout_timestamp = logout_timestamp
                else:
                    # If manually deleting start time, set logout time to null
                    activity.logout_time = None
                    activity.logout_timestamp = None

            except ValueError as e:
                return Response(
                    {
                        "Error": "Times must be sent in ISO8601 format (YYYY-MM-DDTHH:MM:SS)."
                    },
                    status=status.HTTP_412_PRECONDITION_FAILED,
                )

            # Get the required variables
            now_date = localtime(now()).date()

            # Check when deleting clockout time (hence clocking user in) for shift older than current day.
            if (not logout_timestamp) and (login_timestamp.date() != now_date):
                return Response(
                    {
                        "Error": "Cannot have a missing clock out time for a shift older than the current day."
                    },
                    status=status.HTTP_417_EXPECTATION_FAILED,
                )

            # Check that the login and logout times are on the same day, so a shift cant be longer than 24hours.
            elif (logout_timestamp) and (
                login_timestamp.date() != logout_timestamp.date()
            ):
                return Response(
                    {"Error": "A shift must be finished on the same day it started."},
                    status=status.HTTP_417_EXPECTATION_FAILED,
                )

            elif (login_timestamp > localtime(now())) or (
                logout_timestamp and logout_timestamp > localtime(now())
            ):
                return Response(
                    {"Error": "A timestamp cannot be in the future."},
                    status=status.HTTP_417_EXPECTATION_FAILED,
                )

            # Set public holiday state (keep same if not given)
            activity.is_public_holiday = str_to_bool(
                request.data.get("is_public_holiday", activity.is_public_holiday)
            )

            # Set deliveries (keep same if not given)
            try:
                activity.deliveries = int(
                    request.data.get("deliveries", activity.deliveries)
                )
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
                if activity.shift_length_mins < FINISH_SHIFT_TIME_DELTA_THRESHOLD_MINS:
                    return JsonResponse(
                        {
                            "Error": f"Rounded shift duration must be at least {FINISH_SHIFT_TIME_DELTA_THRESHOLD_MINS} minutes."
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            with transaction.atomic():
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
    except User.DoesNotExist as e:
        return Response(
            {
                "Error": "Failed to get your account's information for authorisation. Please login again."
            },
            status=status.HTTP_403_FORBIDDEN,
        )
    except Exception as e:
        # Handle any unexpected exceptions
        logger.critical(
            f"Failed to update activity details for activity ID {id}, resulting in the error: {str(e)}"
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
        employee_id = str(request.data.get("employee_id", ""))
        # Type checking done later when converting form
        login_timestamp = request.data.get("login_timestamp", None) or None
        logout_timestamp = request.data.get("logout_timestamp", None) or None
        is_public_holiday = str_to_bool(request.data.get("is_public_holiday", False))
        store_id = request.data.get("store_id", None)

        # Get the account info of the user requesting this shift info
        manager_id = request.session.get("manager_id")
        try:
            manager = User.objects.get(id=manager_id)
        except User.DoesNotExist:
            return Response(
                {
                    "Error": "Failed to get your account's information for authorisation. Please login again."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Check that the request is not missing the employee ID or the login timestamp (REQUIRED)
        if not employee_id or not login_timestamp:
            return JsonResponse(
                {"Error": "Required fields are missing. (Employee and Login time)"},
                status=status.HTTP_417_EXPECTATION_FAILED,
            )

        if store_id is None:
            return JsonResponse(
                {"Error": "Missing store id information in request data."},
                status=status.HTTP_417_EXPECTATION_FAILED,
            )

        # Ensure deliveries is an int
        try:
            deliveries = int(request.data.get("deliveries", 0))
        except ValueError as e:
            return Response(
                {"Error": "Deliveries must be an integer."},
                status=status.HTTP_417_EXPECTATION_FAILED,
            )

        # Get the employee
        employee = User.objects.get(id=employee_id)

        # Get the store object to link it
        store = Store.objects.get(id=store_id)

        # Check user is authorised to interact with the store and the user
        if not manager.is_associated_with_store(store=int(store_id)):
            return Response(
                {"Error": "Cannot create a new shift for an unassociated store."},
                status=status.HTTP_403_FORBIDDEN,
            )
        elif not manager.is_manager_of(employee=employee):
            return Response(
                {
                    "Error": "Not authorised to create a new shift with another store's employee."
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        elif employee.is_hidden:
            return Response(
                {"Error": "Not authorised to interact with a hidden account."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Ensure the timestamps are in the correct form and are TIMEZONE AWARE (allows comparison)
        try:
            login_timestamp = datetime.strptime(login_timestamp, "%Y-%m-%dT%H:%M:%S")
            login_timestamp = make_aware(
                login_timestamp
            )  # Add timezone info to timestamp

            if logout_timestamp:
                logout_timestamp = datetime.strptime(
                    logout_timestamp, "%Y-%m-%dT%H:%M:%S"
                )
                logout_timestamp = make_aware(
                    logout_timestamp
                )  # Add timezone info to timestamp
        except ValueError as e:
            return Response(
                {
                    "Error": "Times must be sent in ISO8601 format (YYYY-MM-DDTHH:MM:SS)."
                },
                status=status.HTTP_412_PRECONDITION_FAILED,
            )

        # Check if login_timestamp is in the future
        if login_timestamp > localtime(now()):
            return JsonResponse(
                {"Error": "Login time cannot be in the future."},
                status=status.HTTP_417_EXPECTATION_FAILED,
            )

        # Check if logout_timestamp is in the future
        if (logout_timestamp) and (logout_timestamp > localtime(now())):
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

            delta = logout_time - login_time
            if (
                int(delta.total_seconds() // 60)
                < FINISH_SHIFT_TIME_DELTA_THRESHOLD_MINS
            ):
                return JsonResponse(
                    {
                        "Error": f"Rounded shift duration must be at least {FINISH_SHIFT_TIME_DELTA_THRESHOLD_MINS} minutes."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Ensure shift starts and ends on same day
            if login_timestamp.date() != logout_timestamp.date():
                return JsonResponse(
                    {"Error": "A shift must be finished on the same day it started."},
                    status=status.HTTP_417_EXPECTATION_FAILED,
                )

        # Create the new activity record
        activity = Activity.objects.create(
            employee=employee,
            store=store,
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
            {"Error": f"Employee with ID {employee_id} does not exist."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Store.DoesNotExist:
        return Response(
            {"Error": f"Store with the ID {store_id} does not exist."},
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
        # Get and validate store_id
        store_id = request.GET.get("store_id")
        if not store_id or not store_id.isdigit():
            return Response(
                {"Error": "Missing or invalid 'store_id' parameter."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        store_id = int(store_id)

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

        # Check that the manager has access to this store
        manager_id = request.session.get("user_id")
        manager = User.objects.get(id=manager_id)
        if not manager.is_associated_with_store(store_id):
            return Response(
                {"Error": "Not authorised to view employee data for this store."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get user IDs associated with the store
        associated_user_ids = StoreUserAccess.objects.filter(
            store_id=store_id
        ).values_list("user_id", flat=True)

        # Query users
        employees = User.objects.filter(
            id__in=associated_user_ids, is_hidden=False
        ).order_by("first_name", "last_name")[offset : offset + limit]

        total = User.objects.filter(id__in=associated_user_ids, is_hidden=False).count()

        employee_data = [
            {
                "id": emp.id,
                "first_name": emp.first_name,
                "last_name": emp.last_name,
                "email": emp.email,
                "phone_number": emp.phone_number if emp.phone_number else None,
                "dob": emp.birth_date.strftime("%d/%m/%Y") if emp.birth_date else None,
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

        # Get manager's info from their session
        manager_id = request.session.get("user_id")
        manager = User.objects.get(id=manager_id)

        # Ensure manager can list employee's info
        if not manager.is_manager_of(employee=employee):
            return Response(
                {
                    "Error": "Cannot request employee information of an employee associated to a different store."
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        elif employee.is_hidden:
            return Response(
                {"Error": "Not authorised to get information of a hidden account."},
                status=status.HTTP_403_FORBIDDEN,
            )

        employee_data = {
            "id": id,
            "first_name": employee.first_name,
            "last_name": employee.last_name,
            "email": employee.email,
            "phone_number": employee.phone_number,
            "dob": employee.birth_date,
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
@api_view(["PUT"])
@renderer_classes([JSONRenderer])
def create_new_employee(request):
    try:
        # Parse data from request
        first_name = str(request.data.get("first_name", "")).strip()
        last_name = str(request.data.get("last_name", "")).strip()
        email = str(request.data.get("email", "")).strip().lower()
        phone_number = str(request.data.get("phone", "")).strip()
        dob = str(request.data.get("dob", "")).strip()
        store_id = str(request.data.get("store_id", "")).strip()

        # Get the store object
        store = Store.objects.get(id=int(store_id))

        # Get manager account's info
        manager_id = request.session.get("user_id")
        manager = User.objects.get(id=manager_id)

        # Ensure user is a manager of the store
        if not manager.is_associated_with_store(store=store):
            return Response(
                {"Error": "Not authorised to update another store's employee list."},
                status=status.HTTP_403_FORBIDDEN,
            )

        #################### ASSIGNING EXISTING ACCOUNT #########################

        # Ensure basic info is given
        if not email or not store_id:
            return JsonResponse(
                {
                    "Error": "Cannot create a new account due to missing email and store id in the request."
                },
                status=status.HTTP_417_EXPECTATION_FAILED,
            )

        # If an account with given email exits, add them to the store
        if User.objects.filter(email=email).exists():
            employee = User.objects.get(email=email)

            # Check already assigned to store
            if employee.is_associated_with_store(store=store):
                return JsonResponse(
                    {"Error": "Cannot re-assign a given employee to the same store."},
                    status=status.HTTP_409_CONFLICT,
                )

            # Check user cant be modified
            elif employee.is_hidden:
                return Response(
                    {
                        "Error": "Not authorised to update a hidden account's store association."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            new_association = StoreUserAccess.objects.create(
                user=employee,
                store=store,
            )

            new_association.save()
            return JsonResponse(
                {
                    "message": f"Existing employee assigned to store {store.code} successfully.",
                    "id": employee.id,
                },
                status=status.HTTP_201_CREATED,
            )

        ####################### CREATING A NEW ACCOUNT #########################

        # Ensure other required fields are given
        if not first_name or not last_name:
            return JsonResponse(
                {
                    "Error": "Cannot create a new account due to missing first and last name in the request."
                },
                status=status.HTTP_417_EXPECTATION_FAILED,
            )

        # VALIDATE INFORMATION FOR NEW EMPLOYEE
        if len(first_name) > 100:
            return Response(
                {"Error": "First name cannot be longer than 100 characters."},
                status=status.HTTP_412_PRECONDITION_FAILED,
            )
        elif not re.match(VALID_NAME_PATTERN, first_name):
            return Response(
                {
                    "Error": "Invalid first name. Only letters, spaces, hyphens, and apostrophes are allowed."
                },
                status=status.HTTP_412_PRECONDITION_FAILED,
            )

        if len(last_name) > 100:
            return Response(
                {"Error": "Last name cannot be longer than 100 characters."},
                status=status.HTTP_412_PRECONDITION_FAILED,
            )
        elif not re.match(VALID_NAME_PATTERN, last_name):
            return Response(
                {
                    "Error": "Invalid last name. Only letters, spaces, hyphens, and apostrophes are allowed."
                },
                status=status.HTTP_412_PRECONDITION_FAILED,
            )

        try:
            validate_email(email)
        except ValidationError:
            return Response(
                {"Error": "Invalid email format."},
                status=status.HTTP_412_PRECONDITION_FAILED,
            )

        # Create user
        employee = User.objects.create(
            first_name=first_name.title(),
            last_name=last_name.title(),
            email=email,
            is_active=True,
            is_manager=False,
            is_hidden=False,
            is_setup=False,
        )

        # VALIDATE REMAINING NON-ESSENTIAL INFORMATION
        if phone_number:
            if len(phone_number) > 15:
                return Response(
                    {"Error": "Phone number cannot be longer than 15 characters."},
                    status=status.HTTP_412_PRECONDITION_FAILED,
                )
            elif not re.match(VALID_PHONE_NUMBER_PATTERN, phone_number):
                return Response(
                    {
                        "Error": "Invalid phone number. Only numbers, spaces, hyphens, and plus are allowed."
                    },
                    status=status.HTTP_412_PRECONDITION_FAILED,
                )
            employee.phone_number = phone_number

        if dob:
            try:
                parsed_dob = datetime.strptime(dob.strip(), "%Y-%m-%d").date()

                if parsed_dob >= now().date():
                    return Response(
                        {"Error": "Date of birth must be before today."},
                        status=status.HTTP_412_PRECONDITION_FAILED,
                    )
                employee.birth_date = parsed_dob

            except ValueError:
                return Response(
                    {"Error": "Invalid DOB format. Expected format is YYYY-MM-DD."},
                    status=status.HTTP_412_PRECONDITION_FAILED,
                )

        # ADD THE NEW USER TO THE STORE
        new_association = StoreUserAccess.objects.create(
            user=employee,
            store=store,
        )

        # Finally save the new employee and their association with a transation to ensure no errors occur
        with transaction.atomic():
            # Set employee account pin
            employee.set_unique_pin()
            employee.save()
            new_association.save()

        return JsonResponse(
            {
                "message": f"New employee created successfully and assigned to store {store.code}.",
                "id": employee.id,
            },
            status=status.HTTP_201_CREATED,
        )

    except ValueError as e:
        return Response(
            {
                "Error": "Failed to create a new employee account due to invalid store ID format. Please only use numbers in the ID."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Store.DoesNotExist:
        return Response(
            {"Error": f"Store with ID {store_id} does not exist."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except IntegrityError as e:
        logger.critical(
            f"Failed to create new employee account with email {email} ({first_name} {last_name}) due to an database integrity error, resulting in the error: {str(e)}"
        )
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    except Exception as e:
        # Handle any unexpected exceptions
        logger.critical(
            f"Failed to create new employee account for store ID {store_id} with employee name '{first_name} {last_name}', resulting in the error: {str(e)}"
        )
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_employee_required
@api_view(["POST", "PATCH", "PUT"])
@renderer_classes([JSONRenderer])
def modify_account_information(request, id=None):
    """
    API endpoint to either update user's own account or another account if they're a manager and is specified.
    """
    try:
        # Get user information from their session
        try:
            user_id = request.session.get("user_id")
            user = User.objects.get(id=user_id)
            employee_to_update = user
        except User.DoesNotExist:
            return Response(
                {
                    "Error": "Failed to get your account's information for authorisation. Please login again."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if id:
            employee = User.objects.get(id=id)

            # Check manager is able to modify employee info
            if not user.is_manager:
                return Response(
                    {
                        "Error": "Not authorised to update another employee's account information."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            elif not user.is_manager_of(employee=id):
                return Response(
                    {
                        "Error": "Not authorised to update another store's employee account information."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            elif employee.is_hidden:
                return Response(
                    {
                        "Error": "Not authorised to update a hidden account's information."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            elif not employee.is_active:
                raise err.InactiveUserError

            employee_to_update = employee
            if not employee.is_active:
                raise err.InactiveUserError

        # Parse data from request
        first_name = str(request.data.get("first_name", None)).strip()
        last_name = str(request.data.get("last_name", None)).strip()
        phone = str(request.data.get("phone", None))
        dob = str(request.data.get("dob", None))

        # Validate and update first name
        if first_name:
            if len(first_name) > 100:
                return Response(
                    {"Error": "First name cannot be longer than 100 characters."},
                    status=status.HTTP_412_PRECONDITION_FAILED,
                )
            elif not re.match(VALID_NAME_PATTERN, first_name):
                return Response(
                    {
                        "Error": "Invalid first name. Only letters, spaces, hyphens, and apostrophes are allowed."
                    },
                    status=status.HTTP_412_PRECONDITION_FAILED,
                )
            employee_to_update.first_name = first_name.title()

        # Validate and update last name
        if last_name:
            if len(last_name) > 100:
                return Response(
                    {"Error": "Last name cannot be longer than 100 characters."},
                    status=status.HTTP_412_PRECONDITION_FAILED,
                )
            elif not re.match(VALID_NAME_PATTERN, last_name):
                return Response(
                    {
                        "Error": "Invalid last name. Only letters, spaces, hyphens, and apostrophes are allowed."
                    },
                    status=status.HTTP_412_PRECONDITION_FAILED,
                )
            employee_to_update.last_name = last_name.title()

        # Validate and update phone
        if phone:
            if len(phone) > 15:
                return Response(
                    {"Error": "Phone number cannot be longer than 15 characters."},
                    status=status.HTTP_412_PRECONDITION_FAILED,
                )
            elif not re.match(VALID_PHONE_NUMBER_PATTERN, phone):
                return Response(
                    {
                        "Error": "Invalid phone number. Only numbers, spaces, hyphens, and plus are allowed."
                    },
                    status=status.HTTP_412_PRECONDITION_FAILED,
                )
            employee_to_update.phone_number = phone.strip()

        # Validate and update DOB
        if dob:
            try:
                parsed_dob = datetime.strptime(dob.strip(), "%Y-%m-%d").date()

                if parsed_dob >= now().date():
                    return Response(
                        {"Error": "Date of birth must be before today."},
                        status=status.HTTP_412_PRECONDITION_FAILED,
                    )

                employee_to_update.birth_date = parsed_dob

            except ValueError:
                return Response(
                    {"Error": "Invalid DOB format. Expected format is YYYY-MM-DD."},
                    status=status.HTTP_412_PRECONDITION_FAILED,
                )

        employee_to_update.save()
        return JsonResponse(
            {"message": "Account information updated successfully."},
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
def modify_account_status(request, id):
    try:
        # Parse data from request
        status_type = str(request.data.get("status_type", ""))
        store_id = str(request.data.get("store_id"))

        if not status_type:
            return JsonResponse(
                {"Error": "Required status type field missing."},
                status=status.HTTP_417_EXPECTATION_FAILED,
            )

        # Get employee and manager
        employee = User.objects.get(id=id)
        manager_id = request.session.get("user_id")
        manager = User.objects.get(id=manager_id)

        # Check account can be modified
        if not manager.is_manager_of(employee=employee):
            return Response(
                {
                    "Error": "Not authorised to update a different store employee's status."
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        elif employee.is_hidden:
            return Response(
                {"Error": "Not authorised to update a hidden account's status."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Seperate status type modification
        if status_type.lower() == "deactivation":
            employee.is_active = False

        elif status_type.lower() == "activation":
            employee.is_active = True

        elif status_type.lower() == "reset_password":
            employee.is_setup = False

        elif status_type.lower() == "reset_pin":
            employee.set_unique_pin()

        elif status_type.lower() == "resign":
            if not store_id or not store_id.isdigit():
                return JsonResponse(
                    {"Error": "Invalid store_id provided.", "id": employee.id},
                    status=status.HTTP_417_EXPECTATION_FAILED,
                )

            try:
                store = Store.objects.get(id=int(store_id))
                if not employee.is_associated_with_store(store=store):
                    return JsonResponse(
                        {
                            "Error": f"Employee with ID {id} is not associated with store ID {store_id}.",
                            "id": employee.id,
                        },
                        status=status.HTTP_409_CONFLICT,
                    )
                elif employee.is_clocked_in(store=store):
                    return JsonResponse(
                        {
                            "Error": f"Employee with ID {id} is currently clocked in at the store, cannot resign them.",
                            "id": employee.id,
                        },
                        status=status.HTTP_409_CONFLICT,
                    )

                # Resign the user
                StoreUserAccess.objects.filter(user=employee, store=store).delete()

            except Store.DoesNotExist:
                return JsonResponse(
                    {
                        "Error": f"Store with ID {store_id} does not exist.",
                        "id": employee.id,
                    },
                    status=status.HTTP_417_EXPECTATION_FAILED,
                )

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


@api_employee_required
@api_view(["POST", "PUT"])
@renderer_classes([JSONRenderer])
def clock_in(request):
    try:
        # Get location data and store
        location_lat = request.data.get("location_latitude", None)
        location_long = request.data.get("location_longitude", None)
        store_id = request.data.get("store_id", None)

        # Perform general checks on location data (and if its close to store)
        if not util.check_location_data(
            location_lat=location_lat, location_long=location_long, store_id=store_id
        ):
            return Response(
                {"Error": "Cannot clock in too far from the store's allowed range."},
                status=status.HTTP_412_PRECONDITION_FAILED,
            )

        # Get user id from their session
        user_id = request.session.get("user_id")

        # Clock the user in
        activity = controllers.handle_clock_in(employee_id=user_id, store_id=store_id)

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
    except err.MissingStoreObjectOrIDError:
        return Response(
            {"Error": "Missing store id in request."},
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
    except Store.DoesNotExist:
        return Response(
            {"Error": f"Store not found with the ID {store_id}."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except err.StartingShiftTooSoonError:
        # If the user is trying to start a shift too soon after their last shift
        return Response(
            {"Error": f"Can't start a shift too soon after your last shift."},
            status=status.HTTP_409_CONFLICT,
        )
    except err.NotAssociatedWithStoreError:
        return Response(
            {"Error": f"Can't clock in to a store you aren't associated to."},
            status=status.HTTP_403_FORBIDDEN,
        )
    except err.InactiveStoreError:
        return Response(
            {"Error": f"Can't clock in to an inactive store."},
            status=status.HTTP_409_CONFLICT,
        )
    except Exception as e:
        # General error capture -- including database location errors
        logger.critical(
            f"An error occured when clocking in employee ID '{user_id}' for store ID '{store_id}', giving the error: {str(e)}"
        )
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_employee_required
@api_view(["POST", "PUT"])
@renderer_classes([JSONRenderer])
def clock_out(request):
    try:
        # Check if they made any deliveries on clock out
        deliveries = max(
            int(request.data.get("deliveries", 0)),
            0,  # Ensure it's an integer and above 0
        )

        # Get location data and store
        location_lat = request.data.get("location_latitude", None)
        location_long = request.data.get("location_longitude", None)
        store_id = request.data.get("store_id", None)

        # Perform general checks on location data (and if its close to store)
        if not util.check_location_data(
            location_lat=location_lat, location_long=location_long, store_id=store_id
        ):
            return Response(
                {"Error": "Cannot clock out too far from the store's allowed range."},
                status=status.HTTP_412_PRECONDITION_FAILED,
            )

        # Get user id from their session
        user_id = request.session.get("user_id")

        # Clock the user out
        activity = controllers.handle_clock_out(
            employee_id=user_id, deliveries=deliveries, store_id=store_id
        )

        # Return the results after serialisation
        return Response(ActivitySerializer(activity).data, status=status.HTTP_200_OK)

    except err.MissingLocationDataError:
        # If the request is missing the location data
        return Response(
            {"Error": "Missing location data in request."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except err.MissingStoreObjectOrIDError:
        return Response(
            {"Error": "Missing store id in request."},
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
            {"Error": "No active clock-in record found. Please contact an admin."},
            status=status.HTTP_417_EXPECTATION_FAILED,
        )
    except User.DoesNotExist:
        # If the user is not found, return 404
        return Response(
            {"Error": f"Employee not found with the ID {id}."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Store.DoesNotExist:
        return Response(
            {"Error": f"Store not found with the ID {store_id}."},
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
            {"Error": "Can't clock out too soon after clocking in."},
            status=status.HTTP_409_CONFLICT,
        )
    except err.NotAssociatedWithStoreError:
        return Response(
            {"Error": "Can't clock out to a store you aren't associated to."},
            status=status.HTTP_403_FORBIDDEN,
        )
    except err.InactiveStoreError:
        return Response(
            {"Error": "Can't clock out to an inactive store."},
            status=status.HTTP_409_CONFLICT,
        )
    except Exception as e:
        # General error capture -- including database location errors
        logger.critical(
            f"An error occured when trying to clock out employee ID '{user_id}' for store ID '{store_id}': {str(e)}"
        )
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_employee_required
@api_view(["GET"])
@renderer_classes([JSONRenderer])
def clocked_state_view(request):
    """
    API view to get the clocked-in state of a user by ID for a given store (given in request data).
    THE USER MUST BE LOGGED IN AS IT USES THEIR SESSION INFORMATION TO GET THEIR ID.
    """
    try:
        # Get the store information
        store_id = request.query_params.get("store_id", None)

        if store_id is None:
            return Response(
                {
                    "Error": "Missing required store_id field in query params to obtain clocked state. Please retry."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get the user object from the session information
        employee = util.api_get_user_object_from_session(request)

        # Get the user's info
        info = controllers.get_employee_clocked_info(
            employee_id=employee.id, store_id=store_id
        )

        # Return the info
        return Response(ClockedInfoSerializer(info).data, status=status.HTTP_200_OK)

    except User.DoesNotExist:
        # Return a 404 if the user does not exist
        return Response(
            {
                "Error": "The account you have been authenticated with is bugged. Please login again."
            },
            status=status.HTTP_404_NOT_FOUND,
        )
    except Store.DoesNotExist:
        # Return a 404 if the user does not exist
        return Response(
            {"Error": "Cannot get clocked info relating to a non-existant store."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except err.InactiveUserError:
        # If the user is trying to view the data of an inactive account
        return Response(
            {"Error": "Your account is deactivated. Please login again."},
            status=status.HTTP_403_FORBIDDEN,
        )
    except err.InactiveStoreError:
        return Response(
            {"Error": "Can't get clocked information related to a inactive store."},
            status=status.HTTP_409_CONFLICT,
        )
    except err.NotAssociatedWithStoreError:
        return Response(
            {
                "Error": "Can't get clocked information related to a store your unassociated to."
            },
            status=status.HTTP_409_CONFLICT,
        )
    except err.NoActiveClockingRecordError:
        # If the user has no active clocking record (their clock-in activity is missing)
        logger.error(
            f"User with ID {id} has a bugged state due to missing activity record to complete a shift record."
        )
        return Response(
            {"Error": "No active clock-in record found. Please contact an admin."},
            status=status.HTTP_417_EXPECTATION_FAILED,
        )
    except Exception as e:
        logger.critical(
            f"An error occured when trying to get the clocked state of employee ID '{employee.id}' for store ID '{store_id}', giving the error: {str(e)}"
        )
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_employee_required
@api_view(["GET"])
@renderer_classes([JSONRenderer])
def list_associated_stores(request):
    """
    API view to list all associated stores with the user.
    THE USER MUST BE LOGGED IN AS IT USES THEIR SESSION INFORMATION TO GET THEIR ID.
    """
    try:
        # Get the user object from the session information
        employee = util.api_get_user_object_from_session(request)

        # Get the stores and format it for return
        stores = employee.get_associated_stores()
        store_data = {store.id: store.code for store in stores}

        return JsonResponse(store_data, status=status.HTTP_200_OK)

    except User.DoesNotExist:
        # Return a 404 if the user does not exist
        return Response(
            {
                "Error": "The account you have been authenticated with is bugged. Please login again."
            },
            status=status.HTTP_404_NOT_FOUND,
        )
    except err.InactiveUserError:
        # If the user is trying to view the data of an inactive account
        return Response(
            {"Error": "Your account is deactivated. Please login again."},
            status=status.HTTP_403_FORBIDDEN,
        )
    except Exception as e:
        logger.critical(
            f"An error occured when trying to get a user ID ({employee.id})'s associated stores, resulting in the error: {str(e)}"
        )
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_employee_required
@api_view(["GET"])
@renderer_classes([JSONRenderer])
def list_recent_shifts(request):
    try:
        user_id = request.session.get("user_id")
        store_id = request.query_params.get("store_id", None)
        limit = int(request.query_params.get("limit_days", "7"))

        if store_id is None:
            return Response(
                {
                    "Error": "Missing store_id from the request params. Please try again."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get the shifts
        shifts = controllers.get_users_recent_shifts(
            user_id=user_id, store_id=store_id, time_limit_days=limit
        )

        return JsonResponse(shifts, safe=False, status=status.HTTP_200_OK)

    except ValueError:
        return Response(
            {"Error": "Error converting 'limit_days' to an int, was it set correctly?"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Store.DoesNotExist:
        return Response(
            {
                "Error": "Failed to get the store information, was the store_id set correctly?"
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    except err.NotAssociatedWithStoreError:
        return Response(
            {"Error": "Can't get shift information for stores your unassociated with."},
            status=status.HTTP_403_FORBIDDEN,
        )
    except err.InactiveStoreError:
        return Response(
            {"Error": "Can't get shift information for inactive stores."},
            status=status.HTTP_409_CONFLICT,
        )
    except Exception as e:
        # General error capture -- including database location errors
        logger.critical(
            f"An error occured when trying to get recent shifts for employee ID {user_id} associated to the store ID {store_id}, resulting in the error: {str(e)}"
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
                activities = activities.filter(employee__in=employee_ids)

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
        logger.critical(f"An error occurred when generating weekly summary: {str(e)}")
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
        logger.critical(f"An error occured when changing employee pin: {str(e)}")
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
