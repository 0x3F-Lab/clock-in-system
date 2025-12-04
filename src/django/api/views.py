import re
import string
import logging
import traceback
import api.utils as util
import api.exceptions as err
import api.controllers as controllers
import auth_app.tasks as tasks

from datetime import date, datetime, time, timedelta
from rest_framework import status
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer
from rest_framework.decorators import api_view, renderer_classes
from django.conf import settings
from django.http import JsonResponse
from django.db import transaction, IntegrityError, DatabaseError
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.utils.timezone import now, localtime, make_aware
from auth_app.utils import (
    sanitise_markdown_title_text,
    sanitise_markdown_message_text,
    update_user_stats_cache,
)
from auth_app.models import (
    User,
    Activity,
    Store,
    StoreUserAccess,
    Notification,
    NotificationReceipt,
    Shift,
    Role,
    ShiftException,
    ShiftRequest,
)
from auth_app.utils import api_manager_required, api_employee_required
from auth_app.serializers import ActivitySerializer, ClockedInfoSerializer
from django.db.models import Q

from django.http import HttpResponse
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet


logger = logging.getLogger("api")


@api_employee_required
@api_view(["GET"])
@renderer_classes([JSONRenderer])
def list_store_employee_names(request):
    """
    API view to fetch a list of users with their IDs and full names who are related to a certain store.
    The authenticated user MUST be associated to the store to list their employees.
    SUCCESS FORMAT: {"names": [{"id": 1, "name": "Alice Smith"}, {..}, ...]}
    """
    try:
        # Extract query parameters from the request, with defaults
        only_active = util.str_to_bool(request.query_params.get("only_active", "true"))
        ignore_managers = util.str_to_bool(
            request.query_params.get("ignore_managers", "false")
        )
        order = util.str_to_bool(request.query_params.get("order", "true"))
        order_by_first_name = util.str_to_bool(
            request.query_params.get("order_by_first_name", "true")
        )
        ignore_clocked_in = util.str_to_bool(
            request.query_params.get("ignore_clocked_in", "false")
        )
        ignore_self = util.str_to_bool(request.query_params.get("ignore_self", "false"))
        store_id = util.clean_param_str(request.query_params.get("store_id", None))

        if store_id is None:
            return Response(
                {"Error": "Missing store_id in request params. Please try again."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get the user information of the manager requesting this info from their session
        user = util.api_get_user_object_from_session(request)

        # Only allow related store members list the store's employee names
        if not user.is_associated_with_store(store=int(store_id)):
            raise err.NotAssociatedWithStoreError

        # Allow non-managers to only request non-hidden users
        elif not user.is_manager(store=int(store_id)):
            only_active = True

        # Call the controller function
        users_list = controllers.get_store_employee_names(
            store_id=store_id,
            only_active=only_active,
            ignore_managers=ignore_managers,
            order=order,
            order_by_first_name=order_by_first_name,
            ignore_clocked_in=ignore_clocked_in,
            ignore_id=user.id if ignore_self else None,
        )

        # Return the list of users in the response
        return Response({"names": users_list}, status=status.HTTP_200_OK)

    except User.DoesNotExist:
        # Return a 404 if the user does not exist
        return Response(
            {"Error": "No users found matching the given criteria."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except err.NotAssociatedWithStoreError:
        return Response(
            {"Error": "Not authorised to get employee names for this store."},
            status=status.HTTP_403_FORBIDDEN,
        )
    except ValueError:
        return Response(
            {
                "Error": "Could not convert a value into an integer. Did you set your values correctly?"
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception as e:
        # Handle any unexpected exceptions
        logger.critical(
            f"Failed to list all users, resulting in the error: {str(e)}\n{traceback.format_exc()}"
        )
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_manager_required
@api_view(["GET"])
@renderer_classes([JSONRenderer])
def list_all_shift_details(request):
    try:
        # Get the account info of the user requesting these shifts
        try:
            user = util.api_get_user_object_from_session(request)
        except User.DoesNotExist:
            return Response(
                {
                    "Error": "Failed to get your account's information for authorisation. Please login again."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get store id
        store_id = util.clean_param_str(request.query_params.get("store_id", None))
        if store_id is None:
            return Response(
                {
                    "Error": "Missing required store_id field in query params. Please retry."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        elif not user.is_manager(store=int(store_id)):
            raise err.NotAssociatedWithStoreAsManagerError

        # Get pagination values
        offset, limit = util.get_pagination_values_from_request(request)

        # Get remaining param settings
        only_unfinished = util.str_to_bool(
            request.query_params.get("only_unfinished", "false")
        )
        only_public_hol = util.str_to_bool(
            request.query_params.get("only_pub", "false")
        )
        hide_deactivated = util.str_to_bool(
            request.query_params.get("hide_deactive", "false")
        )
        hide_resigned = util.str_to_bool(
            request.query_params.get("hide_resign", "false")
        )
        sort_field = util.clean_param_str(request.query_params.get("sort", "time"))
        start_date = util.clean_param_str(request.query_params.get("start", None))
        end_date = util.clean_param_str(request.query_params.get("end", None))
        filter_names = util.clean_param_str(request.query_params.get("filter", ""))

        if start_date is None or end_date is None:
            return Response(
                {"Error": "Missing start or end date."},
                status=status.HTTP_417_EXPECTATION_FAILED,
            )

        # Validate other given fields
        try:
            datetime.strptime(start_date, "%Y-%m-%d")
            datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            return Response(
                {"Error": "Invalid date format. Use YYYY-MM-DD."},
                status=status.HTTP_406_NOT_ACCEPTABLE,
            )

        VALID_SORT_FIELDS = {"time", "name", "length", "delivery"}
        if sort_field not in VALID_SORT_FIELDS:
            return Response(
                {
                    "Error": f"Invalid sort field. Must be one of: {', '.join(VALID_SORT_FIELDS)}."
                },
                status=status.HTTP_406_NOT_ACCEPTABLE,
            )

        # Convert filter_names string to list
        try:
            filter_names_list = util.get_filter_list_from_string(filter_names)
        except ValueError:
            return Response(
                {"Error": "Invalid characters in filter list."},
                status=status.HTTP_406_NOT_ACCEPTABLE,
            )

        results, total = controllers.get_all_shifts(
            store_id=store_id,
            offset=offset,
            limit=limit,
            start_date=start_date,
            end_date=end_date,
            sort_field=sort_field,
            filter_names=filter_names_list,
            only_unfinished=only_unfinished,
            only_public_hol=only_public_hol,
            hide_deactivated=hide_deactivated,
            hide_resigned=hide_resigned,
            allow_inactive_store=True,  # ONLY MANAGERS ACCESS THIS PAGE -- no need to check perms
        )

        return JsonResponse(
            {
                "total": total,
                "offset": offset,
                "limit": limit,
                "results": results,
            },
            status=status.HTTP_200_OK,
        )

    except ValueError:
        logger.warning(
            f"A VALUE ERROR occured when trying to get shift summaries for store ID {store_id}, resulting in the error: {str(e)}"
        )
        return Response(
            {
                "Error": "Could not convert a value into an integer. Did you set your values correctly?"
            },
            status=status.HTTP_412_PRECONDITION_FAILED,
        )
    except Store.DoesNotExist:
        return Response(
            {"Error": f"Failed to get the store information for ID {store_id}."},
            status=status.HTTP_409_CONFLICT,
        )
    except err.NotAssociatedWithStoreAsManagerError:
        return Response(
            {"Error": "Not authorised to get shift information for the store."},
            status=status.HTTP_403_FORBIDDEN,
        )
    except err.InactiveStoreError:
        return Response(
            {"Error": "Not authorised to get shift information for an inactive store."},
            status=status.HTTP_403_FORBIDDEN,
        )
    except Exception as e:
        # Handle any unexpected exceptions
        logger.critical(
            f"Failed to list all shift details (full dump), resulting in the error: {str(e)}\n{traceback.format_exc()}"
        )
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_manager_required
@api_view(["GET"])
def list_singular_shift_details(request, id):
    try:
        act = Activity.objects.get(pk=id)

        # Get the account info of the user requesting this shift info
        manager = util.api_get_user_object_from_session(request=request)

        if not manager.is_manager(store=act.store_id):
            return Response(
                {"Error": "Not authorised to get shift information for the store."},
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
            f"Failed to list activity details for ID {id}, resulting in the error: {str(e)}\n{traceback.format_exc()}"
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
        activity = Activity.objects.select_related("employee", "store").get(pk=id)

        # Get the account info of the user requesting this shift info
        manager = util.api_get_user_object_from_session(request=request)

        if not manager.is_manager(store=activity.store_id):
            return Response(
                {
                    "Error": "Not authorised to update a shift's information for the store."
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        elif not activity.store.is_active:
            return Response(
                {"Error": "Not authorised to update a shift to an inactive store."},
                status=status.HTTP_403_FORBIDDEN,
            )
        elif activity.employee.is_hidden:
            return Response(
                {"Error": "Not authorised to interact with a hidden account."},
                status=status.HTTP_403_FORBIDDEN,
            )
        elif activity.login_time.date() < (
            localtime(now()).date()
            - timedelta(days=settings.MAX_SHIFT_ACTIVITY_AGE_MODIFIABLE_DAYS)
        ):
            return Response(
                {
                    "Error": f"Not authorised to interact with a shift older than {settings.MAX_SHIFT_ACTIVITY_AGE_MODIFIABLE_DAYS} days."
                },
                status=status.HTTP_424_FAILED_DEPENDENCY,
            )

        # Save activity info
        original = {
            "id": activity.id,
            "deliveries": activity.deliveries,
            "login_time": localtime(activity.login_time),
            "login_timestamp": localtime(activity.login_timestamp),
            "logout_time": localtime(activity.logout_time),
            "logout_timestamp": localtime(activity.logout_timestamp),
            "shift_length_mins": activity.shift_length_mins,
            "is_public_holiday": activity.is_public_holiday,
        }

        # If DELETING the activity
        if request.method == "DELETE":
            with transaction.atomic():
                activity.delete()

                # Create exception IF there is a correlated shift
                shift = (
                    Shift.objects.select_related("store")
                    .filter(
                        store_id=activity.store_id,
                        employee_id=activity.employee_id,
                        date=activity.login_time.date(),
                        is_deleted=False,
                    )
                    .defer("comment")
                    .first()
                )
                if shift:
                    controllers.link_activity_to_shift(shift=shift)

            logger.info(
                f"Manager ID {manager.id} ({manager.first_name} {manager.last_name}) deleted an ACTIVITY with ID {id} for the employee ID {activity.employee.id} ({activity.employee.first_name} {activity.employee.last_name}) under the store [{activity.store.code}])."
            )
            logger.debug(
                f"[DELETE: ACTIVITY (ID: {original['id']})] [MANUAL] Login: {original['login_time']} ({original['login_timestamp']}) -- Logout: {original['logout_time']} ({original['logout_timestamp']}) -- Deliveries: {original['deliveries']} -- Shift Length: {original['shift_length_mins']}mins -- PUBLIC HOLIDAY: {original['is_public_holiday']}"
            )
            return JsonResponse(
                {"message": "Employee deleted successfully"},
                status=status.HTTP_200_OK,
            )

        # If UPDATING the activity
        elif (request.method == "POST") or (request.method == "PATCH"):
            # Parse data from request
            login_timestamp = util.clean_param_str(
                request.data.get("login_timestamp", None)
            )
            logout_timestamp = util.clean_param_str(
                request.data.get("logout_timestamp", None)
            )
            now_time = localtime(now())

            try:
                if login_timestamp:
                    login_timestamp = datetime.strptime(
                        login_timestamp, "%Y-%m-%dT%H:%M:%S"
                    )
                    # Add timezone information to timstamp
                    login_timestamp = localtime(make_aware(login_timestamp))
                    login_time = util.round_datetime_minute(login_timestamp)
                    activity.login_time = login_time
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
                    # Add timezone information to timstamp
                    logout_timestamp = localtime(make_aware(logout_timestamp))
                    logout_time = util.round_datetime_minute(logout_timestamp)
                    activity.logout_time = logout_time
                    activity.logout_timestamp = logout_timestamp
                else:
                    # If manually deleting start time, set logout time to null
                    activity.logout_time = None
                    activity.logout_timestamp = None

                    # Ensure logout is set regardless if its given
                    logout_timestamp = logout_time = None

            except ValueError as e:
                return Response(
                    {
                        "Error": "Times must be sent in ISO8601 format (YYYY-MM-DDTHH:MM:SS)."
                    },
                    status=status.HTTP_412_PRECONDITION_FAILED,
                )

            # Check when deleting clockout time (hence clocking user in) for shift older than current day.
            if (not logout_timestamp) and (login_timestamp.date() != now_time.date()):
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

            elif (login_timestamp > now_time) or (
                logout_timestamp and logout_timestamp > now_time
            ):
                return Response(
                    {"Error": "A timestamp cannot be in the future."},
                    status=status.HTTP_417_EXPECTATION_FAILED,
                )

            # Check if its a unfinished shift BEFORE TODAY (cant have a unfinished shift in the past)
            elif (not logout_timestamp) and (login_timestamp.date() != now_time.date()):
                return JsonResponse(
                    {"Error": "Cannot have a unfinished shift in the past."},
                    status=status.HTTP_417_EXPECTATION_FAILED,
                )

            # Set public holiday state (keep same if not given)
            activity.is_public_holiday = util.str_to_bool(
                request.data.get("is_public_holiday", activity.is_public_holiday)
            )

            # Set deliveries (keep same if not given) -- ENSURE >= 0
            try:
                activity.deliveries = max(
                    int(request.data.get("deliveries", activity.deliveries)),
                    0,
                )
            except ValueError:
                return JsonResponse(
                    {"Error": "Deliveries must be an integer."},
                    status=status.HTTP_412_PRECONDITION_FAILED,
                )

            # Set default shift length
            activity.shift_length_mins = 0

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
                if (
                    activity.shift_length_mins
                    < settings.FINISH_SHIFT_TIME_DELTA_THRESHOLD_MINS
                ):
                    return JsonResponse(
                        {
                            "Error": f"Rounded shift duration must be at least {settings.FINISH_SHIFT_TIME_DELTA_THRESHOLD_MINS} minutes."
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # Check shift does not interfere with another one (i.e doesnt start right after another one - exception is over midnight break)
            if util.employee_has_conflicting_activities(
                employee_id=activity.employee_id,
                store_id=activity.store_id,
                login=login_time,
                logout=logout_time,
                exclude_activity_id=activity.id,
            ):
                return JsonResponse(
                    {
                        "Error": "Activity has interferes with another activity or has an inadequate gap between other activities."
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            with transaction.atomic():
                activity.save()

                # If activity is finished -> check for exceptions
                if activity.logout_time:
                    controllers.link_activity_to_shift(activity=activity)

            logger.info(
                f"Manager ID {manager.id} ({manager.first_name} {manager.last_name}) updated an ACTIVITY with ID {id} for the employee ID {activity.employee.id} ({activity.employee.first_name} {activity.employee.last_name}) under the store [{activity.store.code}])."
            )
            logger.debug(
                f"[UPDATE: ACTIVITY (ID: {activity.id})] [MANUAL] Login: {original['login_time']} ({original['login_timestamp']}) → {activity.login_time} ({activity.login_timestamp}) -- Logout: {original['logout_time']} ({original['logout_timestamp']}) → {activity.logout_time} ({activity.logout_timestamp}) -- Deliveries: {original['deliveries']} → {activity.deliveries} -- Shift Length: {original['shift_length_mins']} → {activity.shift_length_mins} -- PUBLIC HOLIDAY: {original['is_public_holiday']} → {activity.is_public_holiday}"
            )
            return JsonResponse(
                {"message": "Shift updated successfully."},
                status=status.HTTP_202_ACCEPTED,
            )

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
            f"Failed to update activity details for activity ID {id}, resulting in the error: {str(e)}\n{traceback.format_exc()}"
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
        employee_id = util.clean_param_str(request.data.get("employee_id", None))
        # Type checking done later when converting form
        login_timestamp = util.clean_param_str(
            request.data.get("login_timestamp", None)
        )
        logout_timestamp = util.clean_param_str(
            request.data.get("logout_timestamp", None)
        )
        is_public_holiday = util.str_to_bool(
            request.data.get("is_public_holiday", False)
        )
        store_id = util.clean_param_str(request.data.get("store_id", None))
        now_time = localtime(now())

        # Get the account info of the user requesting this shift info
        manager_id = request.session.get("user_id")
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

        elif store_id is None:
            return JsonResponse(
                {"Error": "Missing store_id information in request data."},
                status=status.HTTP_417_EXPECTATION_FAILED,
            )

        # Ensure deliveries is an int and that its >= 0
        try:
            deliveries = max(
                int(request.data.get("deliveries", 0)),
                0,
            )
        except ValueError as e:
            return Response(
                {"Error": "Deliveries must be an integer."},
                status=status.HTTP_417_EXPECTATION_FAILED,
            )

        # Get the employee
        employee = User.objects.get(pk=employee_id)

        # Get the store object to link it
        store = Store.objects.get(pk=store_id)

        # Check user is authorised to interact with the store and the user
        if not manager.is_manager(store=int(store_id)):
            return Response(
                {"Error": "Not authorised to create a new shift for the store."},
                status=status.HTTP_403_FORBIDDEN,
            )
        elif not store.is_active:
            return Response(
                {"Error": "Not authorised to interact with an inactive store."},
                status=status.HTTP_403_FORBIDDEN,
            )
        elif not employee.is_associated_with_store(store=int(store_id)):
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
        elif not employee.is_active:
            return Response(
                {"Error": "Not authorised to assign a shift to an inactive account."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Ensure the timestamps are in the correct form and are TIMEZONE AWARE (allows comparison)
        try:
            login_timestamp = datetime.strptime(login_timestamp, "%Y-%m-%dT%H:%M:%S")
            # Add timezone info to timestamp
            login_timestamp = localtime(make_aware(login_timestamp))

            if logout_timestamp:
                logout_timestamp = datetime.strptime(
                    logout_timestamp, "%Y-%m-%dT%H:%M:%S"
                )
                # Add timezone info to timestamp
                logout_timestamp = localtime(make_aware(logout_timestamp))
        except ValueError as e:
            return Response(
                {
                    "Error": "Times must be sent in ISO8601 format (YYYY-MM-DDTHH:MM:SS)."
                },
                status=status.HTTP_412_PRECONDITION_FAILED,
            )

        # Check user isnt editing a shift older than 2 weeks
        if login_timestamp.date() < (
            now_time.date()
            - timedelta(days=settings.MAX_SHIFT_ACTIVITY_AGE_MODIFIABLE_DAYS)
        ):
            return JsonResponse(
                {
                    "Error": f"Not authorised to create an activity older than {settings.MAX_SHIFT_ACTIVITY_AGE_MODIFIABLE_DAYS} days."
                },
                status=status.HTTP_424_FAILED_DEPENDENCY,
            )

        # Check if login_timestamp is in the future
        elif login_timestamp > now_time:
            return JsonResponse(
                {"Error": "Login time cannot be in the future."},
                status=status.HTTP_417_EXPECTATION_FAILED,
            )

        # Check if logout_timestamp is in the future
        elif (logout_timestamp) and (logout_timestamp > now_time):
            return JsonResponse(
                {"Error": "Logout time cannot be in the future."},
                status=status.HTTP_417_EXPECTATION_FAILED,
            )

        # Check if its a unfinished shift BEFORE TODAY (cant have a unfinished shift in the past)
        elif (not logout_timestamp) and (login_timestamp.date() != now_time.date()):
            return JsonResponse(
                {"Error": "Cannot have a unfinished shift in the past."},
                status=status.HTTP_417_EXPECTATION_FAILED,
            )

        # Get the rounded login/logout times
        login_time = util.round_datetime_minute(
            login_timestamp
        )  # Login timestamp MUST be pass to reach this point
        logout_time = None
        if logout_timestamp:
            logout_time = util.round_datetime_minute(logout_timestamp)

        # Ensure a value is set to prevent error
        shift_length_mins = 0

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
                < settings.FINISH_SHIFT_TIME_DELTA_THRESHOLD_MINS
            ):
                return JsonResponse(
                    {
                        "Error": f"Rounded shift duration must be at least {settings.FINISH_SHIFT_TIME_DELTA_THRESHOLD_MINS} minutes."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Ensure shift starts and ends on same day
            if login_timestamp.date() != logout_timestamp.date():
                return JsonResponse(
                    {"Error": "A shift must be finished on the same day it started."},
                    status=status.HTTP_417_EXPECTATION_FAILED,
                )

            # Set shift length field
            delta = logout_time - login_time
            shift_length_mins = int(delta.total_seconds() // 60)

        # Check shift does not interfere with another one (i.e doesnt start right after another one - exception is over midnight break)
        if util.employee_has_conflicting_activities(
            employee_id=employee.id,
            store_id=store.id,
            login=login_time,
            logout=logout_time,
        ):
            return JsonResponse(
                {
                    "Error": "Activity has interferes with another activity or has an inadequate gap between other activities."
                },
                status=status.HTTP_409_CONFLICT,
            )

        with transaction.atomic():
            # Create the new activity record
            activity = Activity.objects.create(
                employee=employee,
                store=store,
                login_time=login_time,
                logout_time=logout_time,
                login_timestamp=login_timestamp,
                logout_timestamp=logout_timestamp,
                shift_length_mins=shift_length_mins,
                is_public_holiday=is_public_holiday,
                deliveries=deliveries,
            )

            # If activity is finished -> check for exceptions
            if activity.logout_time:
                controllers.link_activity_to_shift(activity=activity.id)

        logger.info(
            f"Manager ID {manager.id} ({manager.first_name} {manager.last_name}) created a new ACTIVITY with ID {activity.id} for the employee ID {employee.id} ({employee.first_name} {employee.last_name}) under the store [{store.code}]."
        )
        logger.debug(
            f"[CREATE: ACTIVITY (ID: {activity.id})] [MANUAL] Login: {activity.login_time} ({activity.login_timestamp}) -- Logout: {activity.logout_time} ({activity.logout_timestamp}) -- Deliveries: {activity.deliveries} -- Shift Length: {activity.shift_length_mins}mins"
        )
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
    except ValueError:
        return Response(
            {
                "Error": "Could not convert a value into an integer. Did you set your values correctly?"
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception as e:
        # Handle any unexpected exceptions
        logger.critical(
            f"Failed to create new shift for employee ID {employee_id}, resulting in the error: {str(e)}\n{traceback.format_exc()}"
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
        # Get the account info of the user requesting these shifts
        try:
            manager = util.api_get_user_object_from_session(request)
        except User.DoesNotExist:
            return Response(
                {
                    "Error": "Failed to get your account's information for authorisation. Please login again."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get store id
        store_id = util.clean_param_str(request.query_params.get("store_id", None))
        if store_id is None:
            return Response(
                {
                    "Error": "Missing required store_id field in query params. Please retry."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        elif not manager.is_manager(store=int(store_id)):
            raise err.NotAssociatedWithStoreAsManagerError

        # Get pagination values
        offset, limit = util.get_pagination_values_from_request(request)

        # Get remaining param settings
        hide_deactivated = util.str_to_bool(
            request.query_params.get("hide_deactive", "false")
        )
        sort_field = util.clean_param_str(request.query_params.get("sort", "name"))
        filter_names = util.clean_param_str(request.query_params.get("filter", ""))

        # Validate other given fields
        VALID_SORT_FIELDS = {"name", "age", "acc_age"}
        if sort_field not in VALID_SORT_FIELDS:
            return Response(
                {
                    "Error": f"Invalid sort field. Must be one of: {', '.join(VALID_SORT_FIELDS)}."
                },
                status=status.HTTP_406_NOT_ACCEPTABLE,
            )

        # Convert filter_names string to list
        try:
            filter_names_list = util.get_filter_list_from_string(filter_names)
        except ValueError:
            return Response(
                {"Error": "Invalid characters in filter list."},
                status=status.HTTP_406_NOT_ACCEPTABLE,
            )

        results, total = controllers.get_all_employee_details(
            store_id=store_id,
            offset=offset,
            limit=limit,
            sort_field=sort_field,
            filter_names=filter_names_list,
            hide_deactivated=hide_deactivated,
            allow_inactive_store=True,  # ONLY MANAGERS ACCESS THIS PAGE -- no need to check perms
        )

        return JsonResponse(
            {
                "total": total,
                "offset": offset,
                "limit": limit,
                "results": results,
            },
            status=status.HTTP_200_OK,
        )

    except ValueError:
        logger.warning(
            f"A VALUE ERROR occured when trying to get shift summaries for store ID {store_id}, resulting in the error: {str(e)}"
        )
        return Response(
            {
                "Error": "Could not convert a value into an integer. Did you set your values correctly?"
            },
            status=status.HTTP_412_PRECONDITION_FAILED,
        )
    except Store.DoesNotExist:
        return Response(
            {"Error": f"Failed to get the store information for ID {store_id}."},
            status=status.HTTP_409_CONFLICT,
        )
    except err.NotAssociatedWithStoreAsManagerError:
        return Response(
            {"Error": "Not authorised to view employee data for this store."},
            status=status.HTTP_403_FORBIDDEN,
        )
    except err.InactiveStoreError:
        return Response(
            {"Error": "Not authorised to get shift information for an inactive store."},
            status=status.HTTP_403_FORBIDDEN,
        )
    except Exception as e:
        # Handle any unexpected exceptions
        logger.critical(
            f"Failed to list all employee data (full dump), resulting in the error: {str(e)}\n{traceback.format_exc()}"
        )
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_manager_required
@api_view(["GET"])
def list_singular_employee_details(request, id):
    try:
        employee = User.objects.get(pk=id)

        # Get manager's info from their session
        manager = util.api_get_user_object_from_session(request=request)

        # Ensure manager can list employee's info
        if not manager.is_manager_of(employee=employee, ignore_inactive_stores=False):
            return Response(
                {
                    "Error": "Not authorised to get employee information of an employee associated to a different store."
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
            f"Failed to list employee details for ID {id}, resulting in the error: {str(e)}\n{traceback.format_exc()}"
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
        first_name = util.clean_param_str(request.data.get("first_name", ""))
        last_name = util.clean_param_str(request.data.get("last_name", ""))
        email = util.clean_param_str(request.data.get("email", "")).lower()
        phone_number = util.clean_param_str(request.data.get("phone", "")) or None
        dob = util.clean_param_str(request.data.get("dob", "")) or None
        store_id = util.clean_param_str(request.data.get("store_id", ""))

        # Get the store object
        store = Store.objects.get(pk=int(store_id))

        # Get manager account's info
        manager = util.api_get_user_object_from_session(request=request)

        # Ensure user is a manager of the store
        if not manager.is_manager(store=store.id):
            raise err.NotAssociatedWithStoreAsManagerError

        # Ensure store is active
        elif not store.is_active:
            raise err.InactiveStoreError

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

            # Save association
            new_association.save()

            # Send a notification
            tasks.notify_managers_and_employee_account_assigned.delay(
                user_id=employee.id, store_id=store.id, manager_id=manager.id
            )

            logger.info(
                f"Manager ID {manager.id} ({manager.first_name} {manager.last_name}) created a STORE ASSOCIATION with ID {new_association.id} between employee ID {employee.id} ({employee.first_name} {employee.last_name}) and store ID {store.id} [{store.code}]."
            )
            logger.debug(
                f"[CREATE: STOREUSERACCESS (ID: {new_association.id})] Employee ID {employee.id} ({employee.first_name} {employee.last_name}) ⇔ Store ID {store.id} [{store.code}]"
            )
            return JsonResponse(
                {
                    "message": f"Existing employee assigned to store {store.code} successfully.",
                    "id": employee.id,
                },
                status=status.HTTP_202_ACCEPTED,
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
        elif not re.match(settings.VALID_NAME_PATTERN, first_name):
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
        elif not re.match(settings.VALID_NAME_PATTERN, last_name):
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

        # VALIDATE REMAINING NON-ESSENTIAL INFORMATION
        if phone_number:
            if len(phone_number) > 15:
                return Response(
                    {"Error": "Phone number cannot be longer than 15 characters."},
                    status=status.HTTP_412_PRECONDITION_FAILED,
                )
            elif not re.match(settings.VALID_PHONE_NUMBER_PATTERN, phone_number):
                return Response(
                    {
                        "Error": "Invalid phone number. Only numbers, spaces, hyphens, and plus are allowed."
                    },
                    status=status.HTTP_412_PRECONDITION_FAILED,
                )

        parsed_dob = None
        if dob:
            try:
                parsed_dob = datetime.strptime(dob.strip(), "%Y-%m-%d").date()

                if parsed_dob >= now().date():
                    return Response(
                        {"Error": "Date of birth must be before today."},
                        status=status.HTTP_412_PRECONDITION_FAILED,
                    )

            except ValueError:
                return Response(
                    {"Error": "Invalid DOB format. Expected format is YYYY-MM-DD."},
                    status=status.HTTP_412_PRECONDITION_FAILED,
                )

        # Create user
        employee = User.objects.create(
            first_name=string.capwords(first_name),
            last_name=string.capwords(last_name),
            email=email,
            phone_number=phone_number,
            birth_date=parsed_dob,
            is_active=True,
            is_hidden=False,
            is_setup=False,
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

        # Send notifications
        tasks.notify_managers_and_employee_account_assigned.delay(
            user_id=employee.id, store_id=store.id, manager_id=manager.id
        )

        logger.info(
            f"Manager ID {manager.id} ({manager.first_name} {manager.last_name}) created a NEW USER with ID {employee.id} ({employee.first_name} {employee.last_name}) and associated them to the store ID {store.id} [{store.code}]."
        )
        logger.debug(
            f"[CREATE: USER (ID: {employee.id})] Name: {employee.first_name} {employee.last_name} -- Email: {employee.email} -- Phone: {employee.phone_number} -- DOB: {employee.birth_date} -- PIN: {employee.pin} -- ACTIVE: {employee.is_active} -- SETUP: {employee.is_setup} -- HIDDEN: {employee.is_hidden}"
        )
        logger.debug(
            f"[CREATE: STOREUSERACCESS (ID: {new_association.id})] Employee ID {employee.id} ({employee.first_name} {employee.last_name}) ⇔ Store ID {store.id} [{store.code}]"
        )
        return JsonResponse(
            {
                "message": f"New employee created successfully and assigned to store {store.code}.",
                "id": employee.id,
            },
            status=status.HTTP_201_CREATED,
        )

    except ValueError:
        return Response(
            {
                "Error": "Could not convert a value into an integer. Did you set your values correctly?"
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
            f"Failed to create new employee account with email {email} ({first_name} {last_name}) due to an database integrity error, resulting in the error: {str(e)}\n{traceback.format_exc()}"
        )
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    except err.NotAssociatedWithStoreAsManagerError:
        return Response(
            {"Error": "Not authorised to this store's employee list."},
            status=status.HTTP_403_FORBIDDEN,
        )
    except err.InactiveStoreError:
        return Response(
            {"Error": "Not authorised to update an inactive store's employee list."},
            status=status.HTTP_403_FORBIDDEN,
        )
    except Exception as e:
        # Handle any unexpected exceptions
        logger.critical(
            f"Failed to create new employee account for store ID {store_id} with employee name '{first_name} {last_name}', resulting in the error: {str(e)}\n{traceback.format_exc()}"
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
            user = util.api_get_user_object_from_session(request=request)
            employee_to_update = user
        except User.DoesNotExist:
            return Response(
                {
                    "Error": "Failed to get your account's information for authorisation. Please login again."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if id:
            employee = User.objects.get(pk=id)

            # Check manager is able to modify employee info
            if not user.is_manager_of(employee=id):
                return Response(
                    {
                        "Error": "Not authorised to update this employee's account information."
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

        # Parse data from request
        first_name = util.clean_param_str(request.data.get("first_name", None))
        last_name = util.clean_param_str(request.data.get("last_name", None))
        phone = util.clean_param_str(request.data.get("phone", None))
        dob = util.clean_param_str(request.data.get("dob", None))

        # Save original data for logging
        original = {
            "first_name": employee_to_update.first_name,
            "last_name": employee_to_update.last_name,
            "phone": employee_to_update.phone_number,
            "dob": employee_to_update.birth_date,
        }

        # Validate and update first name
        if first_name:
            if len(first_name) > 100:
                return Response(
                    {"Error": "First name cannot be longer than 100 characters."},
                    status=status.HTTP_412_PRECONDITION_FAILED,
                )
            elif not re.match(settings.VALID_NAME_PATTERN, first_name):
                return Response(
                    {
                        "Error": "Invalid first name. Only letters, spaces, hyphens, and apostrophes are allowed."
                    },
                    status=status.HTTP_412_PRECONDITION_FAILED,
                )
            employee_to_update.first_name = string.capwords(first_name)

        # Validate and update last name
        if last_name:
            if len(last_name) > 100:
                return Response(
                    {"Error": "Last name cannot be longer than 100 characters."},
                    status=status.HTTP_412_PRECONDITION_FAILED,
                )
            elif not re.match(settings.VALID_NAME_PATTERN, last_name):
                return Response(
                    {
                        "Error": "Invalid last name. Only letters, spaces, hyphens, and apostrophes are allowed."
                    },
                    status=status.HTTP_412_PRECONDITION_FAILED,
                )
            employee_to_update.last_name = string.capwords(last_name)

        # Validate and update phone
        if phone:
            if len(phone) > 15:
                return Response(
                    {"Error": "Phone number cannot be longer than 15 characters."},
                    status=status.HTTP_412_PRECONDITION_FAILED,
                )
            elif not re.match(settings.VALID_PHONE_NUMBER_PATTERN, phone):
                return Response(
                    {
                        "Error": "Invalid phone number. Only numbers, spaces, hyphens, and plus are allowed."
                    },
                    status=status.HTTP_412_PRECONDITION_FAILED,
                )
            employee_to_update.phone_number = phone

        # Validate and update DOB
        if dob:
            # If trying to forcefully update DOB without going through manager page
            if not id:
                return Response(
                    {
                        "Error": "Not authorised to modify your own account date of birth."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            try:
                parsed_dob = datetime.strptime(dob, "%Y-%m-%d").date()

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

        logger.info(
            f"Account ID {user.id} ({user.first_name} {user.last_name}) updated account information for a USER with ID {employee_to_update.id} ({employee_to_update.first_name} {employee_to_update.last_name})."
        )
        logger.debug(
            f"[UPDATE: USER (ID: {employee_to_update.id})] Name: {original['first_name']} {original['last_name']} → {employee_to_update.first_name} {employee_to_update.last_name} -- Phone: {original['phone']} → {employee_to_update.phone_number} -- DOB: {original['dob']} → {employee_to_update.birth_date}"
        )
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
    except ValueError:
        return Response(
            {
                "Error": "Could not convert a value into an integer. Did you set your values correctly?"
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception as e:
        # Handle any unexpected exceptions
        logger.critical(
            f"Failed to update employee details for ID {id}, resulting in the error: {str(e)}\n{traceback.format_exc()}"
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
        status_type = util.clean_param_str(
            request.data.get("status_type", None)
        ).lower()
        store_id = util.clean_param_str(request.data.get("store_id"))

        if not status_type or not store_id:
            return JsonResponse(
                {"Error": "Required status type and store ID fields are missing."},
                status=status.HTTP_417_EXPECTATION_FAILED,
            )

        # Get employee and manager
        employee = User.objects.get(pk=id)
        manager = util.api_get_user_object_from_session(request=request)

        # Check account can be modified
        if not manager.is_manager(store=int(store_id)):
            return Response(
                {"Error": "Not authorised to update employee status'."},
                status=status.HTTP_403_FORBIDDEN,
            )
        elif not employee.is_associated_with_store(store=int(store_id)):
            return Response(
                {"Error": "Not authorised to update this employee's status."},
                status=status.HTTP_403_FORBIDDEN,
            )
        elif employee.is_hidden:
            return Response(
                {"Error": "Not authorised to update a hidden account's status."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Seperate status type modification
        if status_type == "deactivate":
            if not employee.is_active:
                return JsonResponse(
                    {
                        "Error": "Employee account is already deactivated.",
                        "id": employee.id,
                    },
                    status=status.HTTP_409_CONFLICT,
                )
            employee.is_active = False
            employee.save()
            tasks.notify_managers_account_deactivated.delay(
                user_id=employee.id, manager_id=manager.id
            )

        elif status_type == "activate":
            if employee.is_active:
                return JsonResponse(
                    {
                        "Error": "Employee account is already activated.",
                        "id": employee.id,
                    },
                    status=status.HTTP_409_CONFLICT,
                )
            employee.is_active = True
            employee.save()
            tasks.notify_managers_account_activated.delay(
                user_id=employee.id, manager_id=manager.id
            )

        elif status_type == "reset_password":
            employee.is_setup = False
            employee.save()
            tasks.notify_employee_account_reset_password.delay(
                user_id=employee.id, manager_id=manager.id
            )

        elif status_type == "reset_pin":
            employee.set_unique_pin()
            employee.save()
            tasks.notify_employee_account_reset_pin.delay(
                user_id=employee.id, manager_id=manager.id
            )

        elif status_type == "give_manager":
            link = StoreUserAccess.objects.filter(
                user_id=employee.id, store_id=store_id
            ).first()

            if link == None:
                raise StoreUserAccess.DoesNotExist

            link.is_manager = True
            link.save()

            tasks.notify_managers_and_user_elevated_permission.delay(
                store_id=store_id,
                user_id=employee.id,
                authorising_manager_id=manager.id,
            )

        elif status_type == "remove_manager":
            link = StoreUserAccess.objects.filter(
                user_id=employee.id, store_id=store_id
            ).first()

            if link == None:
                raise StoreUserAccess.DoesNotExist

            link.is_manager = False
            link.save()

            tasks.notify_managers_and_user_removed_permission.delay(
                store_id=store_id,
                user_id=employee.id,
                authorising_manager_id=manager.id,
            )

        elif status_type == "resign":
            if not store_id or not store_id.isdigit():
                return JsonResponse(
                    {"Error": "Invalid store_id provided.", "id": employee.id},
                    status=status.HTTP_417_EXPECTATION_FAILED,
                )

            try:
                store = Store.objects.get(pk=int(store_id))
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
                association = StoreUserAccess.objects.filter(
                    user_id=employee.id, store_id=store.id
                ).last()
                association.delete()

                tasks.notify_managers_and_employee_account_resigned.delay(
                    user_id=employee.id, store_id=store.id, manager_id=manager.id
                )
                logger.info(
                    f"Manager ID {manager.id} ({manager.first_name} {manager.last_name}) removed STORE ASSOCIATION for employee with ID {employee.id} ({employee.first_name} {employee.last_name}) under the store ID {store.id} [{store.code}]."
                )
                logger.debug(
                    f"[DELETE: STOREUSERACCESS (ID: {association.id})] Employee ID {employee.id} ({employee.first_name} {employee.last_name}) ⇔ Store ID {store.id} [{store.code}]"
                )
                return JsonResponse(
                    {
                        "message": f"Employee resigned from store ID {store.id} successfully.",
                        "id": employee.id,
                    },
                    status=status.HTTP_202_ACCEPTED,
                )

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

        logger.info(
            f"Manager ID {manager.id} ({manager.first_name} {manager.last_name}) updated account status for a USER with ID {employee.id} ({employee.first_name} {employee.last_name}). Type: {status_type.replace('_', ' ').upper()}."
        )
        logger.debug(
            f"[UPDATE: USER (ID: {employee.id})] Status update: {status_type.replace('_', ' ').upper()}"
            + (
                f". Set new PIN to {employee.pin}."
                if status_type == "reset_pin"
                else ""
            )
        )
        return JsonResponse(
            {"message": "Employee status updated successfully.", "id": employee.id},
            status=status.HTTP_202_ACCEPTED,
        )

    except User.DoesNotExist as e:
        return Response(
            {"Error": f"Employee with ID {id} does not exist."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except StoreUserAccess.DoesNotExist:
        return Response(
            {"Error": "Failed to find user link to store. Please contact admins."},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    except ValueError:
        return Response(
            {
                "Error": "Could not convert a value into an integer. Did you set your values correctly?"
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception as e:
        # Handle any unexpected exceptions
        logger.critical(
            f"Failed to update employee status of type '{status_type}' for ID {id}, resulting in the error: {str(e)}\n{traceback.format_exc()}"
        )
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_employee_required
@api_view(["PUT"])
@renderer_classes([JSONRenderer])
def modify_account_password(request):
    try:
        # Parse data from request
        old_pass = util.clean_param_str(request.data.get("old_pass", None))
        new_pass = util.clean_param_str(request.data.get("new_pass", None))

        if not old_pass or not new_pass:
            return JsonResponse(
                {"Error": "Required old and new password fields are missing."},
                status=status.HTTP_417_EXPECTATION_FAILED,
            )

        old_pass = str(old_pass)
        new_pass = str(new_pass)

        # Get employee
        employee_id = request.session.get("user_id")
        employee = User.objects.get(pk=employee_id)

        # Check account can be modified
        if not employee.is_active:
            return Response(
                {"Error": "Not authorised to update an inactive account's password."},
                status=status.HTTP_403_FORBIDDEN,
            )
        elif not employee.is_setup:
            return Response(
                {
                    "Error": "Employee account must be setup before the password can be modified."
                },
                status=status.HTTP_409_CONFLICT,
            )

        # Validate new password to generate errors to add
        errors = {"old_pass": [], "new_pass": []}
        if len(new_pass) < settings.PASSWORD_MIN_LENGTH:
            errors["new_pass"].append(
                f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters long."
            )
        if len(new_pass) > settings.PASSWORD_MAX_LENGTH:
            errors["new_pass"].append(
                f"Password cannot be longer than {settings.PASSWORD_MAX_LENGTH} characters long."
            )
        if not re.search(settings.VALID_PASSWORD_PATTERN, new_pass):
            errors["new_pass"].append(
                f"Password must contain at least one uppercase letter, one lowercase letter, and one number."
            )

        # If the old password is not valid
        if not employee.check_password(raw_password=old_pass):
            errors["old_pass"].append("Invalid old account password.")
            return Response(
                {"Error": "Invalid old account password.", "field_errors": errors},
                status=status.HTTP_403_FORBIDDEN,
            )
        elif employee.check_password(raw_password=new_pass):
            errors["new_pass"].append("New password cannot match current password.")
            return Response(
                {"Error": "Cannot set the same password.", "field_errors": errors},
                status=status.HTTP_417_EXPECTATION_FAILED,
            )

        # If the new password is not valid
        if len(errors["new_pass"]) > 0:
            return Response(
                {"Error": "Invalid new account password.", "field_errors": errors},
                status=status.HTTP_417_EXPECTATION_FAILED,
            )

        # Update user password
        employee.set_password(raw_password=new_pass)
        employee.save()

        logger.info(
            f"Employee ID {employee.id} ({employee.first_name} {employee.last_name}) updated their password."
        )
        logger.debug(
            f"[UPDATE: USER (ID: {employee.id})] [PASSWORD-CHANGE] Name: {employee.first_name} {employee.last_name} -- Email: {employee.email} -- HIDDEN: {employee.is_hidden}"
        )
        util.flush_user_sessions(
            user_id=employee_id
        )  # FLUSH ALL SESSIONS WITH THE USER'S ID -> FORCE THEM TO RELOGGIN
        return JsonResponse(
            {
                "message": "Employee password updated successfully. Please login again.",
                "id": employee.id,
            },
            status=status.HTTP_202_ACCEPTED,
        )

    except User.DoesNotExist as e:
        return Response(
            {"Error": f"Employee with ID {employee_id} does not exist."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except ValueError:
        return Response(
            {
                "Error": "Could not convert a value into an integer. Did you set your values correctly?"
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception as e:
        # Handle any unexpected exceptions
        logger.critical(
            f"Failed to update employee password for user with ID {employee_id}, resulting in the error: {str(e)}\n{traceback.format_exc()}"
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
        location_lat = util.clean_param_str(request.data.get("location_latitude", None))
        location_long = util.clean_param_str(
            request.data.get("location_longitude", None)
        )
        store_id = util.clean_param_str(request.data.get("store_id", None))

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
            {"Error": "Missing store_id in request."},
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
    except ValueError:
        return Response(
            {
                "Error": "Could not convert a value into an integer. Did you set your values correctly?"
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception as e:
        # General error capture -- including database location errors
        logger.critical(
            f"An error occured when clocking in employee ID '{user_id}' for store ID '{store_id}', giving the error: {str(e)}\n{traceback.format_exc()}"
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
            {"Error": "Missing store_id in request."},
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
        logger.critical(
            f"An error occured when trying to clock out employee ID '{user_id}' for store ID '{store_id}': {str(e)}\n{traceback.format_exc()}\n{traceback.format_exc()}"
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
        store_id = util.clean_param_str(request.query_params.get("store_id", None))

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
    except ValueError:
        return Response(
            {
                "Error": "Could not convert a value into an integer. Did you set your values correctly?"
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception as e:
        logger.critical(
            f"An error occured when trying to get the clocked state of employee ID '{employee.id}' for store ID '{store_id}', giving the error: {str(e)}\n{traceback.format_exc()}"
        )
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_manager_required
@api_view(["POST", "PATCH"])
@renderer_classes([JSONRenderer])
def update_store_info(request, id):
    try:
        # Get the user object from the session information
        manager = util.api_get_user_object_from_session(request)
        store = Store.objects.get(pk=id)

        if not store.is_active:
            raise err.InactiveStoreError
        elif not manager.is_manager(store=store.id):
            raise err.NotAssociatedWithStoreAsManagerError

        # Get the request data
        name = util.clean_param_str(request.data.get("name", None))
        street = util.clean_param_str(request.data.get("loc_street", None))
        code = util.clean_param_str(request.data.get("code", None))
        clocking_dist = (
            util.clean_param_str(request.data.get("clocking_dist", None)) or 0
        )
        cap_scheduling = util.str_to_bool(
            request.data.get("cap_scheduling", store.is_scheduling_enabled)
        )
        cap_global_shift_view = util.str_to_bool(
            request.data.get(
                "cap_global_shift_view", store.is_global_shift_view_enabled
            )
        )

        try:
            clocking_dist = int(clocking_dist)
            clocking_dist = max(clocking_dist, 0)
        except ValueError:
            return Response(
                {"Error": "Invalid clocking distance provided."},
                status=status.HTTP_406_NOT_ACCEPTABLE,
            )

        # Length validation
        if name and len(name) > 230:
            return Response(
                {"Error": "Length of Store name cannot be longer than 230 characters."},
                status=status.HTTP_412_PRECONDITION_FAILED,
            )
        elif street and len(street) > 250:
            return Response(
                {
                    "Error": "Length of Store street location cannot be longer than 250 characters."
                },
                status=status.HTTP_412_PRECONDITION_FAILED,
            )
        elif code and len(code) > 10:
            return Response(
                {"Error": "Length of Store code cannot be longer than 10 characters."},
                status=status.HTTP_412_PRECONDITION_FAILED,
            )
        elif code and len(code) < 4:
            return Response(
                {"Error": "Length of Store code cannot be shorter than 4 characters."},
                status=status.HTTP_412_PRECONDITION_FAILED,
            )
        elif clocking_dist and clocking_dist > 2500:
            return Response(
                {
                    "Error": "Allowable clocking distance of a Store cannot be greater than 2500m."
                },
                status=status.HTTP_412_PRECONDITION_FAILED,
            )

        # Regex validation
        if name and not re.match(r"^[\w\s.,'\/+\-&]+$", name):
            return Response(
                {"Error": "Invalid characters in store name."},
                status=status.HTTP_406_NOT_ACCEPTABLE,
            )
        elif code and not re.match(settings.VALID_STORE_CODE_PATTERN, code):
            return Response(
                {"Error": "Store code must be alphanumeric uppercase."},
                status=status.HTTP_406_NOT_ACCEPTABLE,
            )
        elif street and not re.match(r"^[\w\s.,'\/+\-&]+$", street):
            return Response(
                {"Error": "Invalid characters in street location."},
                status=status.HTTP_406_NOT_ACCEPTABLE,
            )

        # Get original store values for logging
        original = {
            "id": store.id,
            "name": store.name,
            "code": store.code,
            "loc_street": store.location_street,
            "clocking_dist": store.allowable_clocking_dist_m,
            "cap_scheduling": store.is_scheduling_enabled,
            "cap_global_shift_view": store.is_global_shift_view_enabled,
        }

        # Ensure only update DB if something has changed
        update = False

        # Check unique store code and name AND SET THEM
        if (
            code
            and not Store.objects.filter(code=code.upper()).exists()
            and store.code != code.upper()
        ):
            # If store exists with the new code OR same code for the store, ignore setting it
            store.code = code.upper()
            update = True

        if name and not Store.objects.filter(name=name).exists() and store.name != name:
            store.name = name
            update = True

        if clocking_dist and store.allowable_clocking_dist_m != clocking_dist:
            store.allowable_clocking_dist_m = clocking_dist
            update = True

        if street and store.location_street != street:
            store.location_street = street
            update = True

        if store.is_scheduling_enabled != cap_scheduling:
            store.is_scheduling_enabled = cap_scheduling
            update = True

        if store.is_global_shift_view_enabled != cap_global_shift_view:
            store.is_global_shift_view_enabled = cap_global_shift_view
            update = True

        if not update:
            return JsonResponse(
                {"Error": "No changes detected."},
                status=status.HTTP_418_IM_A_TEAPOT,
            )

        # Save and inform store managers of change.
        store.save()
        tasks.notify_managers_store_information_updated.delay(
            store_id=store.id, manager_id=manager.id
        )

        logger.info(
            f"Manager ID {manager.id} ({manager.first_name} {manager.last_name}) updated STORE INFORMATION for Store ID {store.id} ({original['code']})."
        )
        logger.debug(
            f"[UPDATE: STORE (ID: {original['id']})] Name: {original['name']} → {store.name} -- Code: {original['code']} → {store.code} -- Clocking Dist: {original['clocking_dist']} → {store.allowable_clocking_dist_m} -- Street Loc: {original['loc_street']} → {store.location_street} -- CAP Scheduling: {original['cap_scheduling']} → {store.is_scheduling_enabled} -- CAP Global Shift View: {original['cap_global_shift_view']} → {store.is_global_shift_view_enabled}"
        )
        return JsonResponse(
            {"id": store.id, "code": store.code}, status=status.HTTP_202_ACCEPTED
        )

    except User.DoesNotExist:
        # Return a 404 if the user does not exist
        return Response(
            {
                "Error": "The account you have been authenticated with is bugged. Please login again."
            },
            status=status.HTTP_404_NOT_FOUND,
        )
    except Store.DoesNotExist:
        return Response(
            {"Error": f"The Store ID {id} does not exist."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except err.InactiveStoreError:
        return Response(
            {"Error": "Not authorised to update an inactive store."},
            status=status.HTTP_409_CONFLICT,
        )
    except err.NotAssociatedWithStoreAsManagerError:
        return Response(
            {"Error": "Not authorised to update this store."},
            status=status.HTTP_403_FORBIDDEN,
        )
    except DatabaseError:
        return Response(
            {
                "Error": "Failed to save the updated store information. Please contact an admin."
            },
            status=status.HTTP_417_EXPECTATION_FAILED,
        )
    except Exception as e:
        logger.critical(
            f"An error occured when trying to update the store ID ({id})'s information, resulting in the error: {str(e)}\n{traceback.format_exc()}"
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
    If the user is a manager, then it will list inactive stores the user is associated to.
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
            f"An error occured when trying to get a user ID ({employee.id})'s associated stores, resulting in the error: {str(e)}\n{traceback.format_exc()}"
        )
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_employee_required
@api_view(["GET"])
@renderer_classes([JSONRenderer])
def list_user_activities(request):
    try:
        user_id = request.session.get("user_id")
        store_id = util.clean_param_str(request.query_params.get("store_id", None))
        week = util.clean_param_str(request.query_params.get("week", None))

        if store_id is None:
            return Response(
                {
                    "Error": "Missing store_id from the request params. Please try again."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get the shifts
        results = controllers.get_user_activities(
            user_id=user_id, store_id=store_id, week=week
        )

        return JsonResponse({"activities": results}, status=status.HTTP_200_OK)

    except ValueError:
        return Response(
            {"Error": "Week provided is not in ISO format."},
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
            f"An error occured when trying to get recent shifts for employee ID {user_id} associated to the store ID {store_id}, resulting in the error: {str(e)}\n{traceback.format_exc()}"
        )
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_manager_required
@api_view(["GET"])
@renderer_classes([JSONRenderer])
def list_account_summaries(request):
    try:
        manager = util.api_get_user_object_from_session(request=request)

        store_id = util.clean_param_str(request.query_params.get("store_id", None))
        ignore_no_hours = util.str_to_bool(
            request.query_params.get("ignore_no_hours", "false")
        )
        sort_field = util.clean_param_str(request.query_params.get("sort", "name"))
        start_date = util.clean_param_str(request.query_params.get("start", None))
        end_date = util.clean_param_str(request.query_params.get("end", None))
        filter_names = util.clean_param_str(request.query_params.get("filter", ""))

        if not store_id or not start_date or not end_date:
            return Response(
                {
                    "Error": "Missing required request parameters of store_id, start, and end. Please try again."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Ensure manager is authorised
        if not manager.is_manager(store=int(store_id)):
            raise err.NotAssociatedWithStoreAsManagerError

        # Get pagination values
        offset, limit = util.get_pagination_values_from_request(request)

        # Validate other given fields
        if start_date is None or end_date is None:
            return Response(
                {"Error": "Missing start or end date."},
                status=status.HTTP_417_EXPECTATION_FAILED,
            )

        try:
            datetime.strptime(start_date, "%Y-%m-%d")
            datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            return Response(
                {"Error": "Invalid date format. Use YYYY-MM-DD."},
                status=status.HTTP_406_NOT_ACCEPTABLE,
            )

        VALID_SORT_FIELDS = {"name", "hours", "age", "deliveries"}
        if sort_field not in VALID_SORT_FIELDS:
            return Response(
                {
                    "Error": f"Invalid sort field. Must be one of: {', '.join(VALID_SORT_FIELDS)}."
                },
                status=status.HTTP_406_NOT_ACCEPTABLE,
            )

        # Convert filter_names string to list
        try:
            filter_names_list = util.get_filter_list_from_string(filter_names)
        except ValueError:
            return Response(
                {"Error": "Invalid characters in filter list."},
                status=status.HTTP_406_NOT_ACCEPTABLE,
            )

        # Get the summaries
        summaries, total = controllers.get_account_summaries(
            store_id=store_id,
            offset=offset,
            limit=limit,
            start_date=start_date,
            end_date=end_date,
            ignore_no_hours=ignore_no_hours,
            sort_field=sort_field,
            filter_names=filter_names_list,
            allow_inactive_store=True,  # ONLY MANAGERS ACCESS THIS PAGE - no need to check user perms
        )

        return JsonResponse(
            {
                "total": total,
                "offset": offset,
                "limit": limit,
                "results": summaries,
            },
            status=status.HTTP_200_OK,
        )

    except ValueError:
        logger.warning(
            f"A VALUE ERROR occured when trying to get account summaries for store ID {store_id}, resulting in the error: {str(e)}"
        )
        return Response(
            {
                "Error": "Could not convert a value into an integer. Did you set your values correctly?"
            },
            status=status.HTTP_412_PRECONDITION_FAILED,
        )
    except Store.DoesNotExist:
        return Response(
            {"Error": f"Failed to get the store information for ID {store_id}."},
            status=status.HTTP_409_CONFLICT,
        )
    except err.NotAssociatedWithStoreAsManagerError:
        return Response(
            {"Error": "Not authorised to get summaries for this store."},
            status=status.HTTP_403_FORBIDDEN,
        )
    except err.InactiveStoreError:
        return Response(
            {"Error": "Not authorised to get summaries for an inactive store."},
            status=status.HTTP_403_FORBIDDEN,
        )
    except err.ShiftExceptionExistsError:
        return Response(
            {
                "Error": "There exists unapproved shift exceptions for the period. Please resolve them first."
            },
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    except Exception as e:
        logger.critical(
            f"An error occured when trying to get account summaries for store ID {store_id}, resulting in the error: {str(e)}\n{traceback.format_exc()}"
        )
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_employee_required
@api_view(["POST", "PUT"])
@renderer_classes([JSONRenderer])
def mark_notification_read(request, id):
    try:
        # Get user information
        user_id = request.session.get("user_id")

        # Get notification
        notif = Notification.objects.get(pk=id)

        # Mark the notification as read
        marked = notif.mark_notification_as_read(user=user_id)

        if marked:
            update_user_stats_cache(user_id=user_id, increase_notif_count=-1)

        # Logging
        logger.debug(
            f"[UPDATE: NOTIFICATION (ID: {notif.id})] [MARK-READ] User ID: {user_id} || Type: {notif.notification_type} -- Title: {notif.title}"
        )

        # Return the results after serialisation
        return Response({"notification_id": id}, status=status.HTTP_202_ACCEPTED)

    except User.DoesNotExist:
        return Response(
            {"Error": f"Employee not found with the ID {user_id}."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Notification.DoesNotExist:
        return Response(
            {"Error": f"Notification ID {id} does not exist."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except NotificationReceipt.DoesNotExist:
        logger.error(
            f"An error occured when trying to mark notification ID '{id}' as READ for user ID '{user_id}' due to a missing NotificationReceipt."
        )
        return Response(
            {
                "Error": f"Failed to mark notification {id} as READ due to missing receipt. Please contact a site admin."
            },
            status=status.HTTP_417_EXPECTATION_FAILED,
        )
    except Exception as e:
        # General error capture -- including database location errors
        logger.critical(
            f"An error occured when trying to mark notification ID '{id}' as READ for user ID '{user_id}', producing the error: {str(e)}\n{traceback.format_exc()}"
        )
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_manager_required
@api_view(["POST"])
@renderer_classes([JSONRenderer])
def send_employee_notification(request, id):
    try:
        # Get employee info
        try:
            employee = User.objects.get(pk=id)
        except User.DoesNotExist:
            return Response(
                {"Error": f"Employee not found with the ID {id}."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get manager info
        manager = util.api_get_user_object_from_session(request=request)

        # Check manager can send message to user
        if not manager.is_manager_of(employee=employee, ignore_inactive_stores=False):
            return Response(
                {
                    "Error": "Not authorised to send a message to an unassociated employee."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        elif not employee.is_active:
            raise err.InactiveUserError

        # Get title and message
        title = util.clean_param_str(request.data.get("title", None))
        msg = util.clean_param_str(request.data.get("message", None))
        notification_type = util.clean_param_str(
            request.data.get("notification_type", None)
        )
        # Check title and message provided
        if title is None or msg is None:
            return Response(
                {"Error": "Must provide a notification title and message."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check notification type provided
        elif notification_type is None:
            return Response(
                {"Error": "Must provide a notification type."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check notification type
        elif notification_type not in Notification.Type:
            return Response(
                {"Error": "Invalid notification type."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        elif notification_type == Notification.Type.AUTOMATIC_ALERT:
            return Response(
                {"Error": "Not authorised to use AUTOMATIC_ALERT notification type."},
                status=status.HTTP_403_FORBIDDEN,
            )

        elif (
            notification_type
            in [Notification.Type.SYSTEM_ALERT, Notification.Type.ADMIN_NOTE]
            and not manager.is_hidden
        ):
            return Response(
                {
                    "Error": f"Not authorised to use {notification_type.upper()} notification type."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Clean title and message
        str_title = sanitise_markdown_title_text(title)
        str_msg = sanitise_markdown_message_text(msg)

        notif = Notification.send_to_users(
            users=[employee],
            title=str_title,
            message=str_msg,
            notification_type=notification_type,
            recipient_group=Notification.RecipientType.INDIVIDUAL,
            sender=manager,
        )

        # Logging
        logger.info(
            f"Manager {manager.id} ({manager.first_name} {manager.last_name}) sent a message to employee {employee.id} ({employee.first_name} {employee.last_name}) of type '{notification_type.upper()}'."
        )
        logger.debug(
            f"[CREATE: NOTIFICATION (ID: {notif.id})] [INDIVIDUAL-MESSAGE] Manager: {manager.id} ({manager.first_name} {manager.last_name}) >>> Employee: {employee.id} ({employee.first_name} {employee.last_name}) || Type: {notification_type.upper()} -- Title: {title} -- Msg (char_len={len(msg)}): {msg[:25]}...."
        )

        # Return the notification ID after creating message
        return Response(
            {"notification_id": notif.id, "employee_name": employee.first_name},
            status=status.HTTP_201_CREATED,
        )

    except err.InactiveUserError:
        return Response(
            {"Error": "Not authorised to send a message to an inactive account."},
            status=status.HTTP_403_FORBIDDEN,
        )
    except Exception as e:
        # General error capture -- including database location errors
        logger.critical(
            f"An error occured when manager ID '{manager.id}' ({manager.first_name} {manager.last_name}) tried to send a message to employee ID '{id}' : {str(e)}\n{traceback.format_exc()}"
        )
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


################################### SCHEDULING ######################################################################


@api_manager_required
@api_view(["GET"])
@renderer_classes([JSONRenderer])
def list_store_roles(request, id):
    try:
        manager = util.api_get_user_object_from_session(request)
        store = Store.objects.prefetch_related("roles").get(pk=id)

        # Ensure manager is authorised
        if not manager.is_manager(store=store.id):
            raise err.NotAssociatedWithStoreAsManagerError

        elif not store.is_active and not manager.is_hidden:
            raise err.InactiveStoreError

        # Get roles
        roles = store.roles.all().order_by("name")

        info = []
        for role in roles:
            info.append(
                {
                    "id": role.id,
                    "name": role.name,
                    "description": role.description,
                    "colour": role.colour_hex,
                }
            )

        return JsonResponse({"data": info}, status=status.HTTP_200_OK)

    except Store.DoesNotExist:
        return Response(
            {
                "Error": f"Failed to get the a store's role information for store ID {id}."
            },
            status=status.HTTP_409_CONFLICT,
        )
    except err.NotAssociatedWithStoreAsManagerError:
        return Response(
            {"Error": "Not authorised to get role information for this store."},
            status=status.HTTP_403_FORBIDDEN,
        )
    except err.InactiveStoreError:
        return Response(
            {"Error": "Not authorised to get role information for an inactive store."},
            status=status.HTTP_403_FORBIDDEN,
        )
    except Exception as e:
        logger.critical(
            f"An error occured when trying to get a store's roles for store ID {id}, resulting in the error: {str(e)}\n{traceback.format_exc()}"
        )
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_manager_required
@api_view(["POST", "PATCH", "DELETE"])
@renderer_classes([JSONRenderer])
def manage_store_role(request, role_id=None):  # None when CREATING ROLE
    try:
        # Get request data
        manager = util.api_get_user_object_from_session(request)
        name = util.clean_param_str(request.data.get("name", None))
        description = util.clean_param_str(request.data.get("description", None))
        colour_hex = util.clean_param_str(request.data.get("colour_hex", "#adb5bd"))
        store_id = util.clean_param_str(request.data.get("store_id", None))

        # Check given fields are valid
        if name:
            # Capitalise the role name
            name = string.capwords(name)
            if len(name) > settings.ROLE_NAME_MAX_LENGTH:
                return Response(
                    {
                        "Error": f"Role name must be less than {settings.ROLE_NAME_MAX_LENGTH} characters."
                    },
                    status=status.HTTP_412_PRECONDITION_FAILED,
                )
            elif not re.match(settings.VALID_ROLE_NAME_DESC_PATTERN, name):
                return Response(
                    {"Error": f"Role name includes invalid characters."},
                    status=status.HTTP_412_PRECONDITION_FAILED,
                )

        if description:
            description = description.strip().replace("\n", "").replace("\t", "")
            if len(description) > settings.ROLE_DESC_MAX_LENGTH:
                return Response(
                    {
                        "Error": f"Role description must be less than {settings.ROLE_DESC_MAX_LENGTH} characters."
                    },
                    status=status.HTTP_412_PRECONDITION_FAILED,
                )
            elif not re.match(settings.VALID_ROLE_NAME_DESC_PATTERN, description):
                return Response(
                    {"Error": "Role description includes invalid characters."},
                    status=status.HTTP_412_PRECONDITION_FAILED,
                )

        if colour_hex:
            if not re.match(settings.VALID_HEX_COLOUR_PATTERN, colour_hex):
                return Response(
                    {"Error": f"Role colour must be a hex colour."},
                    status=status.HTTP_412_PRECONDITION_FAILED,
                )

        # POST -> Create a new role given the role information
        if request.method == "POST":
            if not all([name, store_id]):
                return Response(
                    {"Error": "Missing required parameters."},
                    status=status.HTTP_428_PRECONDITION_REQUIRED,
                )

            store = Store.objects.get(pk=int(store_id))
            if not manager.is_manager(store=store.id):
                raise err.NotAssociatedWithStoreAsManagerError
            elif not store.is_active:
                raise err.InactiveStoreError
            elif not store.is_scheduling_enabled:
                raise err.StoreNotSchedulingCapable

            with transaction.atomic():
                role = Role.objects.create(
                    store=store, name=name, colour_hex=colour_hex
                )
                if description:
                    role.description = description
                    role.save()

            logger.info(
                f"Manager ID {manager} ({manager.first_name} {manager.last_name}) created a ROLE '{role.name}' for store [{store.code}]."
            )
            desc = (role.description or "")[:15]
            logger.debug(
                f"[CREATE: ROLE (ID: {role.id})] Name: {role.name} -- Store: {store.code} -- Colour: {role.colour_hex} -- Description: {desc}"
            )
            return JsonResponse({"id": role.id}, status=status.HTTP_201_CREATED)

        # Get ROLE
        role = Role.objects.select_related("store").get(pk=role_id)

        # Ensure manager is authorised
        if not manager.is_manager(store=role.store_id):
            raise err.NotAssociatedWithStoreAsManagerError
        elif not role.store.is_active:
            raise err.InactiveStoreError

        # Save original role info for logging
        original = {
            "id": role.id,
            "name": role.name,
            "desc": (role.description or "")[:15],
            "colour": role.colour_hex,
            "store_code": role.store.code,
        }

        # PATCH -> Update the given role information
        if request.method == "PATCH":
            update = False
            if name:
                role.name = name
                update = True
            if description:
                role.description = description
                update = True
            if colour_hex:
                role.colour_hex = colour_hex
                update = True

            if not update:
                return JsonResponse(
                    {"Error": "No changes detected."},
                    status=status.HTTP_418_IM_A_TEAPOT,
                )

            role.save()
            logger.info(
                f"Manager ID {manager} ({manager.first_name} {manager.last_name}) updated ROLE '{original['name']}' from store [{original['store_code']}]."
            )
            desc = (role.description or "")[:15]
            logger.debug(
                f"[UPDATE: ROLE (ID: {original['id']})] Name: {role.name} → {original['name']} -- Store: {original['store_code']} -- Colour: {role.colour_hex} → {original['colour']} -- Description: {desc} → {original['desc']}"
            )
            return JsonResponse({"id": role.id}, status=status.HTTP_202_ACCEPTED)

        # DELETE -> Delete the role
        if request.method == "DELETE":
            role.delete()
            logger.info(
                f"Manager ID {manager} ({manager.first_name} {manager.last_name}) deleted ROLE '{original['name']}' from store [{original['store_code']}]."
            )
            logger.debug(
                f"[DELETE: ROLE (ID: {original['id']})] Name: {original['name']} -- Store: {original['store_code']} -- Colour: {original['colour']} -- Description: {original['desc']}"
            )
            return Response(status=status.HTTP_200_OK)

        # Never practically reached -> ignore this.
        return JsonResponse(
            {"Error": "Method not allowed."}, status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    except IntegrityError:
        return Response(
            {"Error": "The role MUST have a unique name."},
            status=status.HTTP_409_CONFLICT,
        )
    except DatabaseError:
        return Response(
            {"Error": "Failed to update/create the role due to database constraints."},
            status=status.HTTP_409_CONFLICT,
        )
    except Role.DoesNotExist:
        return Response(
            {"Error": f"Failed to get the the information for Role ID {role_id}."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Store.DoesNotExist:
        return Response(
            {"Error": f"Failed to get the the information for Store ID {store_id}."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except ValueError:
        return Response(
            {"Error": "Store ID must be a valid integer."},
            status=status.HTTP_412_PRECONDITION_FAILED,
        )
    except err.NotAssociatedWithStoreAsManagerError:
        return Response(
            {"Error": "Not authorised to update role information for this store."},
            status=status.HTTP_403_FORBIDDEN,
        )
    except err.InactiveStoreError:
        return Response(
            {
                "Error": "Not authorised to update role information for an inactive store."
            },
            status=status.HTTP_403_FORBIDDEN,
        )
    except err.StoreNotSchedulingCapable:
        return Response(
            {"Error": "Store does not have scheduling enabled."},
            status=status.HTTP_423_LOCKED,
        )
    except Exception as e:
        logger.critical(
            f"An error occured when trying to manage Role ID {role_id} with method {request.method}, resulting in the error: {str(e)}\n{traceback.format_exc()}"
        )
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_employee_required
@api_view(["GET"])
@renderer_classes([JSONRenderer])
def get_store_shifts(request, id):
    try:
        user = util.api_get_user_object_from_session(request)
        store = Store.objects.get(pk=id)

        # Ensure manager is authorised
        if not user.is_associated_with_store(store=store.id):
            raise err.NotAssociatedWithStoreError

        elif not store.is_active and not user.is_manager(store=store):
            raise err.InactiveStoreError

        # Get other request data
        get_all = util.str_to_bool(request.query_params.get("get_all", "false"))
        week = util.clean_param_str(request.query_params.get("week", None))
        hide_deactivated = util.str_to_bool(
            request.query_params.get("hide_deactive", "false")
        )
        hide_resigned = util.str_to_bool(
            request.query_params.get("hide_resign", "false")
        )
        legacy = util.str_to_bool(request.query_params.get("legacy", "false"))
        sort_field = util.clean_param_str(
            request.query_params.get("sort", ("time" if legacy else "name"))
        )
        filter_names = util.clean_param_str(
            request.query_params.get("filter_names", "")
        )
        filter_roles = util.clean_param_str(
            request.query_params.get("filter_roles", "")
        )
        offset, limit = util.get_pagination_values_from_request(
            request, default_limit=100
        )

        # Check the week is passed
        if not week:
            return Response(
                {"Error": "Missing starting week date from request params."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check the date is correct
        try:
            datetime.strptime(week, "%Y-%m-%d")
        except ValueError:
            return Response(
                {"Error": "Invalid date format. Use YYYY-MM-DD."},
                status=status.HTTP_412_PRECONDITION_FAILED,
            )

        if get_all:
            if not user.is_manager(store=store):
                if not store.is_global_shift_view_enabled:
                    return Response(
                        {
                            "Error": "Not authorised to view store-wide roster for this store."
                        },
                        status=status.HTTP_403_FORBIDDEN,
                    )

                # Reset certain filter options - prevent regular employees modifying them
                hide_deactivated = hide_resigned = legacy = (
                    True  # Non-legacy is not needed as view only uses legacy
                )

            VALID_SORT_FIELDS = (
                {"time", "name", "role_name", "length"}
                if legacy
                else {"name", "age", "acc_age"}
            )
            if sort_field not in VALID_SORT_FIELDS:
                return Response(
                    {
                        "Error": f"Invalid sort field. Must be one of: {', '.join(VALID_SORT_FIELDS)}."
                    },
                    status=status.HTTP_406_NOT_ACCEPTABLE,
                )

            # Convert filter_names string to list
            try:
                filter_names_list = util.get_filter_list_from_string(
                    filter_names, settings.VALID_NAME_LIST_PATTERN
                )
                filter_roles_list = util.get_filter_list_from_string(
                    filter_roles, settings.VALID_ROLE_NAME_DESC_PATTERN
                )
            except ValueError:
                return Response(
                    {"Error": "Invalid characters in either filter list."},
                    status=status.HTTP_406_NOT_ACCEPTABLE,
                )

            # Use legacy view function IF requesting legacy view
            if legacy:
                data = controllers.get_all_store_schedules_legacy(
                    store=store,
                    week=week,
                    include_deleted=False,
                    hide_deactivated=hide_deactivated,
                    hide_resigned=hide_resigned,
                    sort_field=sort_field,
                    filter_names=filter_names_list,
                    filter_roles=filter_roles_list,
                    requesting_user_id=user.id,
                )

            # Use new function to get data if not requesting legacy view
            else:
                data = controllers.get_all_store_schedules(
                    store=store,
                    week=week,
                    offset=offset,
                    limit=limit,
                    include_deleted=False,
                    hide_deactivated=hide_deactivated,
                    hide_resigned=hide_resigned,
                    sort_field=sort_field,
                    filter_names=filter_names_list,
                    filter_roles=filter_roles_list,
                )

        # Only get the user's shifts
        else:
            data = controllers.get_user_store_schedules(
                store=store, user=user, week=week
            )

        return JsonResponse(data, status=status.HTTP_200_OK)

    except ValueError:
        return Response(
            {"Error": "The week provided must be in ISO format."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Store.DoesNotExist:
        return Response(
            {"Error": f"Failed to get the a store's schedule for store ID {id}."},
            status=status.HTTP_409_CONFLICT,
        )
    except err.NotAssociatedWithStoreError:
        return Response(
            {
                "Error": "Not authorised to get schedule information for a unassociated store."
            },
            status=status.HTTP_403_FORBIDDEN,
        )
    except err.InactiveStoreError:
        return Response(
            {
                "Error": "Not authorised to get schedule information for an inactive store."
            },
            status=status.HTTP_403_FORBIDDEN,
        )
    except Exception as e:
        if get_all:
            logger.critical(
                f"An error occured when trying to get a store's entire schedule for store ID {id} for week {week}, resulting in the error: {str(e)}\n{traceback.format_exc()}"
            )
        else:
            logger.critical(
                f"An error occured when trying to get user ID {user.id}'s schedule for store ID {id}, resulting in the error: {str(e)}\n{traceback.format_exc()}"
            )
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_employee_required
@api_view(["GET", "POST", "DELETE"])
@renderer_classes([JSONRenderer])
def manage_store_shift(request, id):
    try:
        manager = util.api_get_user_object_from_session(request)
        shift = Shift.objects.select_related("store", "employee", "role").get(pk=id)

        # Ensure manager is authorised
        if not manager.is_manager(store=shift.store.id) and (
            request.method != "GET"
            or shift.employee_id != manager.id
            or shift.is_deleted
        ):
            return Response(
                {"Error": "Not authorised to make this request."},
                status=status.HTTP_403_FORBIDDEN,
            )
        elif not shift.store.is_active and not manager.is_hidden:
            raise err.InactiveStoreError
        elif not shift.store.is_scheduling_enabled and request.method != "GET":
            raise err.StoreNotSchedulingCapable

        # Save original info for logging
        original = {
            "id": shift.id,
            "emp_id": shift.employee.id,
            "emp_name": f"{shift.employee.first_name} {shift.employee.last_name}",
            "date": shift.date,
            "start_time": shift.start_time,
            "end_time": shift.end_time,
            "role": shift.role.name if shift.role else "N/A",
            "comment": shift.comment[:50] if shift.comment else "N/A",
        }

        # If GET -> Get the specific INFO for this one schedule
        if request.method == "GET":
            info = {
                "id": shift.id,
                "employee_id": shift.employee_id,
                "employee_name": f"{shift.employee.first_name} {shift.employee.last_name}",
                "date": shift.date.isoformat(),
                "start_time": shift.start_time.strftime("%H:%M"),
                "end_time": shift.end_time.strftime("%H:%M"),
                "role_id": shift.role.id if shift.role else None,
                "role_name": shift.role.name if shift.role else None,
                "role_desc": shift.role.description if shift.role else None,
                "role_colour": shift.role.colour_hex if shift.role else None,
                "comment": shift.comment if shift.comment else "",
                "in_future": False if shift.date <= localtime(now()).date() else True,
            }

            # IF REGULAR EMPLOYEE -> REMOVE SOME CONTENT
            if not manager.is_manager:
                return Response(info, status=status.HTTP_200_OK)

            return Response(
                {
                    **info,
                    "is_unscheduled": shift.is_unscheduled,
                    "is_deleted": shift.is_deleted,
                },
                status=status.HTTP_200_OK,
            )

        elif request.method == "DELETE":

            current_date = localtime(now()).date()
            current_time = localtime(now()).time()

            if shift.date < current_date or (
                shift.date == current_date and shift.start_time <= current_time
            ):
                return Response(
                    {"Error": "Not authorised to delete a past or active shift."},
                    status=status.HTTP_410_GONE,
                )

            shift.delete()

            logger.info(
                f"Manager ID {manager.id} ({manager.first_name} {manager.last_name}) deleted a SHIFT with ID {id} (for date {original['date']}) for the employee ID {shift.employee.id} ({shift.employee.first_name} {shift.employee.last_name}) under the store [{shift.store.code}])."
            )
            logger.debug(
                f"[DELETE: SHIFT (ID: {original['id']})] Employee: {original['emp_name']} ({original['emp_id']}) -- Date: {original['date']} -- Time: {original['start_time']} <> {original['end_time']} -- Role: {original['role']} -- Comment: {original['comment']}"
            )
            return Response(
                {
                    "message": "Scheduled shift deleted successfully.",
                    "date": shift.date,
                },
                status=status.HTTP_200_OK,
            )

        elif request.method == "POST":
            # Cannot edit a shift for an inactive store
            if not shift.store.is_active:
                raise err.InactiveStoreError

            # Get other request data
            employee_id = util.clean_param_str(request.data.get("employee_id", None))
            role_id = util.clean_param_str(request.data.get("role_id", None))
            date = util.clean_param_str(request.data.get("date", None))
            start_time = util.clean_param_str(request.data.get("start_time", None))
            end_time = util.clean_param_str(request.data.get("end_time", None))
            comment = util.clean_param_str(request.data.get("comment", ""))

            if not all([employee_id, date, start_time, end_time]):
                return Response(
                    {"Error": "Missing required parameters."},
                    status=status.HTTP_428_PRECONDITION_REQUIRED,
                )

            try:
                employee_id = int(employee_id)
                if role_id:
                    role_id = int(role_id)
            except (ValueError, TypeError):
                return Response(
                    {"Error": "Employee and Role ID must be an integer."},
                    status=status.HTTP_412_PRECONDITION_FAILED,
                )

            try:
                date = datetime.strptime(date, "%Y-%m-%d").date()
                start_time = datetime.strptime(start_time, "%H:%M")
                end_time = datetime.strptime(end_time, "%H:%M")

                # Round times -- PASS DATETIME OBJ TO RETURN DATETIME OBJ -> get time
                start_time = util.round_datetime_minute(start_time).time()
                end_time = util.round_datetime_minute(end_time).time()
            except ValueError:
                return Response(
                    {
                        "Error": "All date-time data must be formed correctly (YYYY-MM-DD or HH:MM)"
                    },
                    status=status.HTTP_412_PRECONDITION_FAILED,
                )

            if comment:
                comment = comment.strip().replace("\n", "").replace("\t", "")
                if len(comment) > settings.SHIFT_COMMENT_MAX_LENGTH:
                    return Response(
                        {
                            "Error": f"Comment must be less than {settings.SHIFT_COMMENT_MAX_LENGTH} characters."
                        },
                        status=status.HTTP_412_PRECONDITION_FAILED,
                    )
                elif not re.match(settings.VALID_SHIFT_COMMENT_PATTERN, comment):
                    return Response(
                        {"Error": "Comment includes invalid characters."},
                        status=status.HTTP_412_PRECONDITION_FAILED,
                    )

            # Get the employee
            employee = User.objects.get(pk=int(employee_id))

            # Check not editing an OLD shift
            current_date = localtime(now()).date()
            current_time = localtime(now()).time()
            if date < current_date or (
                date == current_date and start_time <= current_time
            ):
                return Response(
                    {"Error": "Not authorised to update a past shift."},
                    status=status.HTTP_410_GONE,
                )

            # Check store has the role
            elif role_id and not shift.store.has_role(role=int(role_id)):
                return Response(
                    {"Error": "Not authorised to assign another store's role."},
                    status=status.HTTP_406_NOT_ACCEPTABLE,
                )

            # Check if employee is inactive
            elif not employee.is_active:
                raise err.InactiveUserError

            # Check the employee is assigned to the store
            elif not employee.is_associated_with_store(store=shift.store_id):
                return Response(
                    {
                        "Error": "Not authorised to assign an unassociated user to the shift."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Check times are acceptable
            elif end_time <= start_time:
                return Response(
                    {"Error": "A shift cannot have a end time before the start time."},
                    status=status.HTTP_412_PRECONDITION_FAILED,
                )
            elif not util.is_shift_duration_valid(
                start_time=start_time, end_time=end_time
            ):
                return Response(
                    {
                        "Error": f"A shift cannot be shorter than {settings.MINIMUM_SHIFT_LENGTH_ASSIGNMENT_MINS} minutes"
                    },
                    status=status.HTTP_412_PRECONDITION_FAILED,
                )

            # Check shift does not interfere with another one (i.e doesnt start right after another one - exception is over midnight break)
            elif util.employee_has_conflicting_shifts(
                employee_id=employee.id,
                store_id=shift.store_id,
                date=date,
                login=start_time,
                logout=end_time,
                exclude_shift_id=shift.id,
            ):
                return JsonResponse(
                    {
                        "Error": "Shift has interferes with another shift or has an inadequate gap between other shifts."
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            update = False
            if shift.employee.id != employee.id:
                shift.employee = employee
                update = True

            # Handle cases of removing the role or adding a new role
            if role_id:
                if shift.role_id != role_id:
                    shift.role_id = int(role_id)
                    update = True
            else:
                if shift.role is not None:
                    shift.role = None
                    update = True

            if shift.date != date:
                shift.date = date
                update = True

            if shift.start_time != start_time:
                shift.start_time = start_time
                update = True

            if shift.end_time != end_time:
                shift.end_time = end_time
                update = True

            if shift.comment != comment:
                shift.comment = comment
                update = True

            if not update:
                return JsonResponse(
                    {"Error": "No changes detected."},
                    status=status.HTTP_418_IM_A_TEAPOT,
                )

            # Only save the DB if changes are made -> reduces DB load.
            shift.save()

            logger.info(
                f"Manager ID {manager.id} ({manager.first_name} {manager.last_name}) updated a SHIFT with ID {id} (for date {original['date']}) for the employee ID {shift.employee.id} ({shift.employee.first_name} {shift.employee.last_name}) under the store [{shift.store.code}])."
            )
            logger.debug(
                f"[UPDATE: SHIFT (ID: {original['id']})] Employee: {original['emp_name']} ({original['emp_id']}) → {shift.employee.first_name} {shift.employee.last_name} ({shift.employee.id}) -- Date: {original['date']} → {shift.date} -- Time: {original['start_time']} <> {original['end_time']} → {shift.start_time} <> {shift.end_time} -- Comment: {original['comment']} → {shift.comment if shift.comment else 'N/A'}"
            )
            return JsonResponse(
                {
                    # "employee_name": employee.first_name,
                    "employee_id": employee.id,
                    "date": shift.date,
                    "start_time": shift.start_time,
                    "end_time": shift.end_time,
                },
                status=status.HTTP_202_ACCEPTED,
            )

        # Never practically reached -> ignore this.
        return JsonResponse(
            {"Error": "Method not allowed."}, status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    except Shift.DoesNotExist:
        return Response(
            {"Error": f"Failed to get the shift for ID {id}."},
            status=status.HTTP_409_CONFLICT,
        )
    except err.NotAssociatedWithStoreAsManagerError:
        return Response(
            {"Error": "Not authorised to interact with this store's shift."},
            status=status.HTTP_403_FORBIDDEN,
        )
    except err.InactiveStoreError:
        return Response(
            {"Error": "Not authorised to interact with an inactive store's shift."},
            status=status.HTTP_403_FORBIDDEN,
        )
    except err.InactiveUserError:
        return Response(
            {
                "Error": "Cannot modify an inactive user's shift. This can only be done via exceptions."
            },
            status=status.HTTP_403_FORBIDDEN,
        )
    except err.StoreNotSchedulingCapable:
        return Response(
            {"Error": "Store does not have scheduling enabled."},
            status=status.HTTP_423_LOCKED,
        )
    except Exception as e:
        logger.critical(
            f"An error occured when trying to interact with a store's shift for shift ID {id} for method {request.method}, resulting in the error: {str(e)}\n{traceback.format_exc()}"
        )
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_manager_required
@api_view(["PUT"])
@renderer_classes([JSONRenderer])
def create_store_shift(request, store_id):
    try:
        manager = util.api_get_user_object_from_session(request)
        store = Store.objects.get(pk=store_id)

        employee_id = util.clean_param_str(request.data.get("employee_id", None))
        role_id = util.clean_param_str(request.data.get("role_id", None))
        date = util.clean_param_str(request.data.get("date", None))
        start_time = util.clean_param_str(request.data.get("start_time", None))
        end_time = util.clean_param_str(request.data.get("end_time", None))
        comment = util.clean_param_str(request.data.get("comment", ""))

        if not all([employee_id, date, start_time, end_time]):
            return Response(
                {"Error": "Missing required parameters."},
                status=status.HTTP_428_PRECONDITION_REQUIRED,
            )

        try:
            employee_id = int(employee_id)
            if role_id:
                role_id = int(role_id)
        except (ValueError, TypeError):
            return Response(
                {"Error": "Employee and Role ID must be an integer."},
                status=status.HTTP_412_PRECONDITION_FAILED,
            )

        try:
            date = datetime.strptime(date, "%Y-%m-%d").date()
            start_time = datetime.strptime(start_time, "%H:%M")
            end_time = datetime.strptime(end_time, "%H:%M")

            # Round times -- PASS DATETIME OBJ TO RETURN DATETIME OBJ -> get time
            start_time = util.round_datetime_minute(start_time).time()
            end_time = util.round_datetime_minute(end_time).time()
        except ValueError:
            return Response(
                {"Error": "Incorrect date/time format."},
                status=status.HTTP_412_PRECONDITION_FAILED,
            )

        if comment:
            comment = comment.strip().replace("\n", "").replace("\t", "")
            if len(comment) > settings.SHIFT_COMMENT_MAX_LENGTH:
                return Response(
                    {
                        "Error": f"Comment must be less than {settings.SHIFT_COMMENT_MAX_LENGTH} characters."
                    },
                    status=status.HTTP_412_PRECONDITION_FAILED,
                )
            elif not re.match(settings.VALID_SHIFT_COMMENT_PATTERN, comment):
                return Response(
                    {"Error": "Comment includes invalid characters."},
                    status=status.HTTP_412_PRECONDITION_FAILED,
                )

        employee = User.objects.get(pk=int(employee_id))

        if not manager.is_manager(store=store.id):
            raise err.NotAssociatedWithStoreAsManagerError
        elif not store.is_active:
            raise err.InactiveStoreError
        elif not store.is_scheduling_enabled:
            raise err.StoreNotSchedulingCapable
        elif not employee.is_active:
            raise err.InactiveUserError
        elif role_id and not store.has_role(role=int(role_id)):
            return Response(
                {"Error": "Role not associated with this store."},
                status=status.HTTP_406_NOT_ACCEPTABLE,
            )

        elif not employee.is_associated_with_store(store.id):
            return Response(
                {
                    "Error": "Not authorised to create a shift for an unassociated employee."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        now_datetime = localtime(now())
        if date < now_datetime.date() or (
            date == now_datetime.date() and start_time <= now_datetime.time()
        ):
            return Response(
                {"Error": "Cannot create a shift in the past."},
                status=status.HTTP_412_PRECONDITION_FAILED,
            )

        # Check times are acceptable
        elif end_time <= start_time:
            return Response(
                {"Error": "A shift cannot have a end time before the start time."},
                status=status.HTTP_412_PRECONDITION_FAILED,
            )

        elif not util.is_shift_duration_valid(start_time=start_time, end_time=end_time):
            return Response(
                {
                    "Error": f"A shift cannot be shorter than {settings.MINIMUM_SHIFT_LENGTH_ASSIGNMENT_MINS} minutes"
                },
                status=status.HTTP_412_PRECONDITION_FAILED,
            )

        # Check shift does not interfere with another one (i.e doesnt start right after another one - exception is over midnight break)
        elif util.employee_has_conflicting_shifts(
            employee_id=employee.id,
            store_id=store.id,
            date=date,
            login=start_time,
            logout=end_time,
        ):
            return JsonResponse(
                {
                    "Error": "Shift has interferes with another shift or has an inadequate gap between other shifts."
                },
                status=status.HTTP_409_CONFLICT,
            )

        # Create the shift
        shift = Shift.objects.create(
            store=store,
            employee=employee,
            role_id=None if not role_id else role_id,
            date=date,
            start_time=start_time,
            end_time=end_time,
            comment=comment,
        )

        logger.info(
            f"Manager ID {manager.id} ({manager.first_name} {manager.last_name}) created a SHIFT for employee ID {employee.id} ({employee.first_name} {employee.last_name}) on {date} at store [{store.code}]."
        )
        logger.debug(
            f"[CREATE: SHIFT (ID: {shift.id})] Employee: {employee.first_name} {employee.last_name} ({shift.employee.id}) -- Date: {shift.date} -- Time: {shift.start_time} <> {shift.end_time}"
        )
        return Response(
            {
                "id": shift.id,
                "date": shift.date,
                "start_time": shift.start_time,
                "end_time": shift.end_time,
            },
            status=status.HTTP_201_CREATED,
        )

    except User.DoesNotExist:
        return Response(
            {"Error": f"Employee with ID {employee_id} does not exist."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Store.DoesNotExist:
        return Response(
            {"Error": f"Store with ID {store_id} does not exist."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except err.NotAssociatedWithStoreAsManagerError:
        return Response(
            {"Error": "Not authorised create a shift for this store."},
            status=status.HTTP_403_FORBIDDEN,
        )
    except err.InactiveStoreError:
        return Response(
            {"Error": "Not authorised create a shift for an inactive store."},
            status=status.HTTP_403_FORBIDDEN,
        )
    except err.InactiveUserError:
        return Response(
            {"Error": "Not authorised create a shift for an inactive user."},
            status=status.HTTP_403_FORBIDDEN,
        )
    except err.StoreNotSchedulingCapable:
        return Response(
            {"Error": "Store does not have scheduling enabled."},
            status=status.HTTP_423_LOCKED,
        )
    except Exception as e:
        logger.critical(f"Error creating shift: {str(e)}\n{traceback.format_exc()}")
        return Response(
            {"Error": "Internal error."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_manager_required
@api_view(["POST", "PATCH"])
@renderer_classes([JSONRenderer])
def manage_store_exception(request, exception_id):
    """
    POST -> Approve the ACTIVITY and over-write the rostered SHIFT (schedule)
    PATCH -> Approve the ACTIVITY, BUT, update the activity login/logout times and over-write the rostered SHIFT (schedule)
    """
    try:
        manager = util.api_get_user_object_from_session(request)
        exception = ShiftException.objects.select_related("activity__store").get(
            id=exception_id
        )
        login_time = util.clean_param_str(request.data.get("login_time", None))
        logout_time = util.clean_param_str(request.data.get("logout_time", None))
        role_id = util.clean_param_str(request.data.get("role_id", None))
        comment = util.clean_param_str(request.data.get("comment", ""))

        store = exception.get_store()

        if not store.is_active:
            raise err.InactiveStoreError
        elif not manager.is_manager(store=store.id):
            raise err.NotAssociatedWithStoreAsManagerError
        elif exception.is_approved:
            raise err.ShiftExceptionAlreadyApprovedError

        # POST -> APPROVE EXCEPTION (no updates to activity data needed)
        if request.method == "POST":
            with transaction.atomic():
                controllers.approve_exception(exception=exception_id)

                logger.info(
                    f"Manager ID {manager.id} ({manager.first_name} {manager.last_name}) APPROVED exception ID {exception.id} for store [{store.code}] with reason '{exception.reason.upper()}'."
                )
                logger.debug(
                    f"[UPDATE: SHIFTEXCEPTION (ID: {exception.id})] [APRV] Shift ID: {exception.shift_id if exception.shift else 'N/A'} -- Activity ID: {exception.activity_id if exception.activity else 'N/A'} -- Reason: {exception.reason.upper()}"
                )

        # PATCH -> UPDATE THE ACTIVITY THEN APPROVE EXCEPTION
        elif request.method == "PATCH":
            if not all([login_time, logout_time]):
                return Response(
                    {"Error": "Missing required parameters."},
                    status=status.HTTP_428_PRECONDITION_REQUIRED,
                )

            try:
                # Safely parse time strings (HH:MM or HH:MM:SS)
                login = time.fromisoformat(login_time)
                logout = time.fromisoformat(logout_time)
            except ValueError:
                return Response(
                    {"Error": "Invalid datetime format. Expected HH:MM or HH:MM:SS."},
                    status=status.HTTP_412_PRECONDITION_FAILED,
                )

            if comment:
                comment = comment.strip().replace("\n", "").replace("\t", "")
                if len(comment) > settings.SHIFT_COMMENT_MAX_LENGTH:
                    return Response(
                        {
                            "Error": f"Comment must be less than {settings.SHIFT_COMMENT_MAX_LENGTH} characters."
                        },
                        status=status.HTTP_412_PRECONDITION_FAILED,
                    )
                elif not re.match(settings.VALID_SHIFT_COMMENT_PATTERN, comment):
                    return Response(
                        {"Error": "Comment includes invalid characters."},
                        status=status.HTTP_412_PRECONDITION_FAILED,
                    )

            # Make sure activity is there
            activity = exception.activity
            if not activity:
                raise Exception(
                    "Cannot update activity times — exception is not linked to an activity."
                )
            elif not activity.login_time and not activity.logout_time:
                raise err.IncompleteActivityError

            # Ensure the role given is valid and usable
            elif role_id:
                try:
                    role_id = int(role_id)
                    if not activity.store.has_role(role=int(role_id)):
                        return Response(
                            {"Error": "Not authorised to assign another store's role."},
                            status=status.HTTP_406_NOT_ACCEPTABLE,
                        )
                except ValueError:  # No need to check for Role.DoesNotExist
                    return Response(
                        {"Error": "Role ID must be a valid integer."},
                        status=status.HTTP_412_PRECONDITION_FAILED,
                    )

            # Construct new datetime values by combining the original date with new time values
            login_dt = localtime(activity.login_timestamp).replace(
                hour=login.hour, minute=login.minute, second=login.second, microsecond=0
            )
            logout_dt = localtime(activity.logout_timestamp).replace(
                hour=logout.hour,
                minute=logout.minute,
                second=logout.second,
                microsecond=0,
            )

            # Round as required
            login_dt_rounded = util.round_datetime_minute(login_dt)
            logout_dt_rounded = util.round_datetime_minute(logout_dt)

            original = {
                "id": activity.id,
                "login_time": localtime(activity.login_time),
                "login_timestamp": localtime(activity.login_timestamp),
                "logout_time": localtime(activity.logout_time),
                "logout_timestamp": localtime(activity.logout_timestamp),
                "shift_length_mins": activity.shift_length_mins,
            }

            # Update the activity with the new times provided
            with transaction.atomic():
                delta = logout_dt_rounded - login_dt_rounded
                activity.login_time = login_dt_rounded
                activity.login_timestamp = login_dt
                activity.logout_time = logout_dt_rounded
                activity.logout_timestamp = logout_dt
                activity.shift_length_mins = int(delta.total_seconds() // 60)
                activity.save()

                controllers.approve_exception(
                    exception=exception.id, override_role_id=role_id, comment=comment
                )

                logger.info(
                    f"Manager ID {manager.id} ({manager.first_name} {manager.last_name}) updated an ACTIVITY with ID {activity.id} for the employee ID {activity.employee.id} under the store ID [{activity.store_id}]) when APPROVING an EXCEPTION."
                )
                logger.debug(
                    f"[UPDATE: ACTIVITY (ID: {activity.id})] [EXCEP-APRV] Login: {original['login_time']} ({original['login_timestamp']}) → {activity.login_time} ({activity.login_timestamp}) -- Logout: {original['logout_time']} ({original['logout_timestamp']}) → {activity.logout_time} ({activity.logout_timestamp}) -- Shift Length: {original['shift_length_mins']} → {activity.shift_length_mins}"
                )

                logger.info(
                    f"Manager ID {manager.id} ({manager.first_name} {manager.last_name}) APPROVED exception ID {exception.id} for store [{store.code}] with reason '{exception.reason.upper()}'."
                )
                logger.debug(
                    f"[UPDATE: SHIFTEXCEPTION (ID: {exception.id})] [APRV] Shift ID: {exception.shift_id if exception.shift else 'N/A'} -- Activity ID: {exception.activity_id if exception.activity else 'N/A'} -- Reason: {exception.reason.upper()}"
                )

        # Never practically reached -> ignore this.
        else:
            return JsonResponse(
                {"Error": "Method not allowed."},
                status=status.HTTP_405_METHOD_NOT_ALLOWED,
            )

        return JsonResponse(
            {"exception_id": exception_id}, status=status.HTTP_202_ACCEPTED
        )

    except err.IncompleteActivityError:
        return Response(
            {"Error": "Cannot approve an exception related to an unfinished shift."},
            status=status.HTTP_409_CONFLICT,
        )
    except err.ShiftExceptionAlreadyApprovedError:
        return Response(
            {"Error": "Exception is already approved."},
            status=status.HTTP_406_NOT_ACCEPTABLE,
        )
    except ShiftException.DoesNotExist:
        return Response(
            {"Error": f"Exception with ID {exception_id} does not exist."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except err.NotAssociatedWithStoreAsManagerError:
        return Response(
            {"Error": "Not authorised interact with exceptions of this store."},
            status=status.HTTP_403_FORBIDDEN,
        )
    except err.InactiveStoreError:
        return Response(
            {"Error": "Not authorised interact with exceptions of an inactive store."},
            status=status.HTTP_403_FORBIDDEN,
        )
    except Exception as e:
        logger.critical(
            f"Error approving exception ID {exception_id}: {str(e)}\n{traceback.format_exc()}"
        )
        return Response(
            {"Error": "Internal error."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# --- EXCEPTIONS ---
@api_manager_required
@api_view(["GET"])
@renderer_classes([JSONRenderer])
def list_store_exceptions(request, store_id):
    try:
        manager = util.api_get_user_object_from_session(request)
        store = Store.objects.get(pk=store_id)

        # Get params
        offset, limit = util.get_pagination_values_from_request(request)
        get_unapproved = util.str_to_bool(
            request.query_params.get("get_unapproved", "True")
        )

        # Check user is authorised
        if not manager.is_manager(store=store.id):
            raise err.NotAssociatedWithStoreAsManagerError

        elif not store.is_active and not manager.is_hidden:
            raise err.InactiveStoreError

        # Get the exceptions
        info, total = controllers.get_store_exceptions(
            store=store, get_unapproved=get_unapproved, offset=offset, limit=limit
        )

        return Response(
            {
                "store_id": store_id,
                "total": total,
                "offset": offset,
                "limit": limit,
                "exceptions": info,
            },
            status=status.HTTP_200_OK,
        )

    except Store.DoesNotExist:
        return Response(
            {"Error": f"Store with ID {store_id} does not exist."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except err.NotAssociatedWithStoreAsManagerError:
        return Response(
            {"Error": "Not authorised get exceptions for this store."},
            status=status.HTTP_403_FORBIDDEN,
        )
    except err.InactiveStoreError:
        return Response(
            {"Error": "Not authorised get exceptions for an inactive store."},
            status=status.HTTP_403_FORBIDDEN,
        )
    except Exception as e:
        logger.critical(
            f"Error listing store ID {store_id}'s ShiftExceptions: {str(e)}\n{traceback.format_exc()}"
        )
        return Response(
            {"Error": "Internal error."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# --- COPY WEEK ---
@api_manager_required
@api_view(["POST"])
@renderer_classes([JSONRenderer])
def copy_week_schedule(request, store_id):
    """
    Copies only non-conflicting shifts from a source week to the next week for a specific store.
    Does not delete existing shifts.
    """
    try:
        manager = util.api_get_user_object_from_session(request=request)
        store = Store.objects.get(pk=store_id)
        source_week = util.clean_param_str(request.data.get("source_week", None))
        target_week = util.clean_param_str(request.data.get("target_week", None))
        override_shifts = util.str_to_bool(request.data.get("override_shifts", "false"))
        include_unscheduled = util.str_to_bool(
            request.data.get("include_unscheduled", "false")
        )

        if not source_week or not target_week:
            return Response(
                {"Error": "Missing target or source week in request."},
                status=status.HTTP_428_PRECONDITION_REQUIRED,
            )

        try:
            source_week = util.get_week_start(date.fromisoformat(source_week))
            target_week = util.get_week_start(date.fromisoformat(target_week))
        except ValueError:
            return Response(
                {"Error": "Incorrect date format. Must be in ISO YYYY-MM-DD format."},
                status=status.HTTP_412_PRECONDITION_FAILED,
            )

        if not store.is_active:
            raise err.InactiveStoreError
        elif not manager.is_associated_with_store(store=store.id):
            raise err.NotAssociatedWithStoreError
        elif target_week <= localtime(now()).date():
            return Response(
                {"Error": "Cannot copy schedules into a past week."},
                status=status.HTTP_406_NOT_ACCEPTABLE,
            )

        results = controllers.copy_week_schedule(
            store=store,
            source_week=source_week,
            target_week=target_week,
            override_shifts=override_shifts,
            include_unscheduled=include_unscheduled,
        )

        logger.info(
            f"Manager ID {manager.id} ({manager.first_name} {manager.last_name}) copied a schedule week {source_week} -> {target_week} for store [{store.code}] [Override: {'YES' if override_shifts else 'NO'}]"
        )
        logger.debug(
            f"[COPY: SHIFTs] Source Wk: {source_week} -- Target Wk: {target_week} -- Override: {'YES' if override_shifts else 'NO'} -- # Created: {results['created']} -- # Updated: {results['updated']} -- # Skipped: {results['skipped']} -- Total: {results['total']}"
        )
        return Response(
            {"results": results, "target_week": target_week},
            status=status.HTTP_202_ACCEPTED,
        )

    except Store.DoesNotExist:
        return Response(
            {"Error": f"Store with ID {store_id} does not exist."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except err.NotAssociatedWithStoreError:
        return Response(
            {"Error": "Not authorised modify the schedule for this store."},
            status=status.HTTP_403_FORBIDDEN,
        )
    except err.InactiveStoreError:
        return Response(
            {"Error": "Not authorised to modify the schedule for an inactive store."},
            status=status.HTTP_403_FORBIDDEN,
        )
    except err.StoreNotSchedulingCapable:
        return Response(
            {"Error": "Store does not have scheduling enabled."},
            status=status.HTTP_423_LOCKED,
        )
    except DatabaseError as e:
        logger.critical(
            f"A database error occured when trying to copy a schedule week ({source_week} -> {target_week}) [override: {'YES' if override_shifts else 'NO'}]: {str(e)}\n{traceback.format_exc()}"
        )
        return Response(
            {
                "Error": "Failed to copy schedule week due to internal database errors. Please contact an admin."
            },
            status=status.HTTP_423_LOCKED,
        )
    except Exception as e:
        logger.critical(
            f"An error occurred during copy_week_schedule: {str(e)}\n{traceback.format_exc()}"
        )
        return Response(
            {"Error": "An internal error occurred while copying the schedule."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


################################### SHIFT COVERING ######################################################################


@api_employee_required
@api_view(["POST", "PATCH"])  # POST=REQUEST FROM STORE, PATCH=REQUEST FROM USER
@renderer_classes([JSONRenderer])
def request_shift_cover(request, shift_id):
    try:
        employee = util.api_get_user_object_from_session(request)
        shift = Shift.objects.defer("comment").select_related("store").get(pk=shift_id)
        selected_employee_id = util.clean_param_str(
            request.data.get("selected_employee_id", None)
        )

        if not shift.store.is_active:
            raise err.InactiveStoreError
        elif employee.id != shift.employee_id:
            return Response(
                {"Error": "Can only interact with your own shifts."},
                status=status.HTTP_403_FORBIDDEN,
            )
        elif shift.get_active_shift_requests().exists():
            return Response(
                {"Error": "An active cover request already exists for this shift."},
                status=status.HTTP_409_CONFLICT,
            )
        elif shift.date <= localtime(now()).date():
            return Response(
                {"Error": "Cover requests can only be made for future shifts."},
                status=status.HTTP_412_PRECONDITION_FAILED,
            )

        # POST -> REQUEST COVER FROM THE WHOLE STORE
        if request.method == "POST":
            # Create a cover request
            req = ShiftRequest.objects.create(
                type=ShiftRequest.Type.COVER,
                requester=employee,
                store=shift.store,
                shift=shift,
            )

        # PATCH -> REQUEST COVER FROM THE SELECTED EMPLOYEE
        elif request.method == "PATCH":
            if not selected_employee_id:
                return Response(
                    {"Error": "Missing `selected_employee_id` in request."},
                    status=status.HTTP_428_PRECONDITION_REQUIRED,
                )

            # Get user object to check if they're active
            selected_employee = User.objects.get(pk=int(selected_employee_id))
            if not selected_employee.is_active:
                raise err.InactiveUserError

            elif selected_employee.id == employee.id:
                return Response(
                    {"Error": "Cannot select yourself to cover the shift."},
                    status=status.HTTP_412_PRECONDITION_FAILED,
                )

            # Check selected user is assigned to store
            elif (
                not shift.store.is_associated_with_user(selected_employee.id)
                or selected_employee.is_hidden
            ):
                return Response(
                    {"Error": "Selected employee is not associated to the store."},
                    status=status.HTTP_412_PRECONDITION_FAILED,
                )

            # Create a cover request
            req = ShiftRequest.objects.create(
                type=ShiftRequest.Type.SWAP,
                requester=employee,
                target_user=selected_employee,
                store=shift.store,
                shift=shift,
            )

        logger.info(
            f"User ID {employee.id} ({employee.first_name} {employee.last_name}) requested COVER for shift ID {shift.id} from {f'[{shift.store.code}]' if req.type != ShiftRequest.Type.SWAP else f'Employee ID {selected_employee_id}'}."
        )
        logger.debug(
            f"[CREATE: SHIFTREQUEST (ID: {req.id})] Shift ID: {shift.id} -- Type: {req.type.upper()} -- Store Code: {shift.store.code} -- Target User ID: {selected_employee_id if req.type == ShiftRequest.Type.SWAP else 'N/A'}"
        )
        return JsonResponse(
            {"shift_id": shift_id, "request_id": req.id}, status=status.HTTP_201_CREATED
        )

    except ValueError:
        return Response(
            {"Error": "A invalid value was passed in the request."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Shift.DoesNotExist:
        return Response(
            {"Error": f"Shift with ID {shift_id} does not exist."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except err.InactiveStoreError:
        return Response(
            {"Error": "Not authorised interact with an inactive store."},
            status=status.HTTP_403_FORBIDDEN,
        )
    except err.InactiveUserError:
        return Response(
            {"Error": "Not authorised interact with an inactive user account."},
            status=status.HTTP_403_FORBIDDEN,
        )
    except Exception as e:
        logger.critical(
            f"Error requesting cover for shift ID {shift_id}: {str(e)}\n{traceback.format_exc()}"
        )
        return Response(
            {"Error": "Internal error."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_employee_required
@api_view(
    ["POST", "PUT", "PATCH", "DELETE"]
)  # POST=ACCEPT, PUT=MANAGER APPROV, PATCH=REJECT, DELETE=DELETE/CANCEL
@renderer_classes([JSONRenderer])
def manage_shift_request(request, req_id):
    try:
        employee = util.api_get_user_object_from_session(request)
        req = ShiftRequest.objects.select_related("shift", "shift__store").get(
            pk=req_id
        )

        if not req.shift.store.is_active:
            raise err.InactiveStoreError
        if not req.shift.store.is_associated_with_user(employee):
            raise err.NotAssociatedWithStoreError

        original = {
            "status": req.status.upper(),
        }

        # POST -> REQUESTING EMPLOYEE ACCEPTS THE COVER
        if request.method == "POST":
            # Ensure request can be covered
            if req.status != ShiftRequest.Status.PENDING:
                return Response(
                    {"Error": "Can only accept a PENDING request."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Ensure user isnt covering for themselves
            elif employee.id == req.requester_id:
                return Response(
                    {"Error": "Cannot accept your own request."},
                    status=status.HTTP_412_PRECONDITION_FAILED,
                )

            # Ensure cover acceptance happens before current date of shift
            elif req.shift.date <= localtime(now()).date():
                return Response(
                    {"Error": "Can only accept future shifts."},
                    status=status.HTTP_412_PRECONDITION_FAILED,
                )

            elif util.employee_has_conflicting_shifts(
                employee_id=employee.id,
                store_id=req.shift.store_id,
                date=req.shift.date,
                login=req.shift.start_time,
                logout=req.shift.end_time,
            ):
                return Response(
                    {
                        "Error": "You already have a conflicting shift at this time. Cannot accept request."
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            # Update request
            req.target_user_id = employee.id
            req.status = ShiftRequest.Status.ACCEPTED
            req.save()

            # Manually update user's cache
            update_user_stats_cache(user_id=employee.id, increase_shift_req_count=-1)

        # PUT -> MANAGER APPROVES THE COVER -> UPDATE SHIFT
        elif request.method == "PUT":
            # Ensure user is manager
            if not employee.is_manager(store=req.store_id):
                return Response(
                    {"Error": "Not authorised to approve a shift request."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            elif req.status != ShiftRequest.Status.ACCEPTED:
                return Response(
                    {"Error": "Can only approve ACCEPTED shift requests."},
                    status=status.HTTP_409_CONFLICT,
                )

            elif not req.target_user:
                raise Exception(
                    "Could not APPROVE SHIFT REQUEST due to request missing `target_user` field."
                )

            elif req.shift.date <= localtime(now()).date():
                return Response(
                    {"Error": "Can only approve future shifts."},
                    status=status.HTTP_412_PRECONDITION_FAILED,
                )

            elif util.employee_has_conflicting_shifts(
                employee_id=req.target_user.id,
                store_id=req.shift.store_id,
                date=req.shift.date,
                login=req.shift.start_time,
                logout=req.shift.end_time,
            ):
                return Response(
                    {
                        "Error": f"{req.target_user.first_name} already has a conflicting shift at this time. Cannot approve request."
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            # DELETE RELAVENT EXCEPTIONS (IF MANAGER DIDNT APPROVE BEFORE SHIFT WAS WORKED)
            # then UPDATE SHIFT
            # then IF IN PAST -> CHECK EXCEPTIONS
            with transaction.atomic():
                try:
                    excep = ShiftException.objects.get(shift=req.shift)
                    excep.delete()
                except ShiftException.DoesNotExist:
                    pass

                req.shift.employee = req.target_user
                req.shift.save()
                req.status = ShiftRequest.Status.APPROVED
                req.save()

                # If shift in past -> check for exception
                shift_end_dt = make_aware(
                    datetime.combine(req.shift.date, req.shift.end_time)
                )
                if shift_end_dt < localtime(now()):
                    controllers.link_activity_to_shift(shift=req.shift_id)

            update_user_stats_cache(user_id=employee.id, increase_shift_req_count=-1)

        # PATCH -> MANAGER/TARGET USER REJECTS REQUEST
        elif request.method == "PATCH":
            if req.status != ShiftRequest.Status.ACCEPTED and req.type in [
                ShiftRequest.Type.COVER,
                ShiftRequest.Type.BID,
            ]:
                return Response(
                    {"Error": "Cannot reject this type of request."},
                    status=status.HTTP_424_FAILED_DEPENDENCY,
                )

            # Only target user OR manager can reject request
            elif not (
                (
                    employee.id == req.target_user_id
                    and req.status == ShiftRequest.Status.PENDING
                )
                or (
                    employee.is_manager(store=req.store_id)
                    and req.status == ShiftRequest.Status.ACCEPTED
                )
            ):
                return Response(
                    {"Error": "Not authorised to reject the request."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            req.status = ShiftRequest.Status.REJECTED
            req.save()

            # Manually update user's cache
            update_user_stats_cache(user_id=employee.id, increase_shift_req_count=-1)

        # DELETE -> MANAGER/REQUESTING USER DELETES/CANCELS IT IN `PENDING` STATE
        elif request.method == "DELETE":
            # Ensure user is MANAGER or AUTHORING user
            if not (
                req.requester_id == employee.id
                or employee.is_manager(store=req.store_id)
            ):
                return Response(
                    {"Error": "Not authorised to cancel this request."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            if req.status != ShiftRequest.Status.PENDING:
                return Response(
                    {"Error": "Can only cancel PENDING requests."},
                    status=status.HTTP_424_FAILED_DEPENDENCY,
                )

            req.status = ShiftRequest.Status.CANCELLED
            req.save()

            # Manually update user's cache -- manager doesnt get an active notification for it, so ignore them
            if employee.id == req.requester_id:
                update_user_stats_cache(
                    user_id=employee.id, increase_shift_req_count=-1
                )

        tasks.notify_shift_request_status_change.delay(
            request_id=req.id, acting_user_id=employee.id
        )

        logger.info(
            f"User ID {employee.id} ({employee.first_name} {employee.last_name}) updated status of Shift Request ID {req.id} to {req.type.upper()}."
        )
        logger.debug(
            f"[UPDATE: SHIFTREQUEST (ID: {req.id})] Status: {original['status']} → {req.status.upper()} -- Type: {req.type.upper()} -- Shift ID: {req.shift_id} -- Store Code: {req.shift.store.code} -- Target User ID: {req.target_user_id if (req.target_user is not None) else 'N/A'}"
        )

        return Response({"request_id": req.id}, status=status.HTTP_202_ACCEPTED)

    except ValueError:
        return Response(
            {"Error": "A invalid value was passed in the request."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Shift.DoesNotExist:
        return Response(
            {"Error": f"Shift Request with ID {req_id} does not exist."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except err.InactiveStoreError:
        return Response(
            {"Error": "Not authorised interact with an inactive store."},
            status=status.HTTP_403_FORBIDDEN,
        )
    except err.NotAssociatedWithStoreError:
        return Response(
            {"Error": "Cannot interact with an unassociated store's shift request."},
            status=status.HTTP_403_FORBIDDEN,
        )
    except Exception as e:
        logger.critical(
            f"Error managing Shift Request ID {req_id} [Method: {request.method}]: {str(e)}\n{traceback.format_exc()}"
        )
        return Response(
            {"Error": "Internal error."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_employee_required
@api_view(["GET"])
@renderer_classes([JSONRenderer])
def list_shift_requests(request):
    """
    Lists shift requests based on the new consolidated view types.
    ?view=pending | active | approval | history
    """
    try:
        employee = util.api_get_user_object_from_session(request)
        view_type = util.clean_param_str(request.query_params.get("type", "pending"))
        offset, limit = util.get_pagination_values_from_request(request)

        data, total = controllers.get_shift_requests(
            employee=employee, offset=offset, limit=limit, view_type=view_type
        )

        return Response(
            {"requests": data, "total": total, "offset": offset, "limit": limit},
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        logger.critical(
            f"Error listing shift requests of type {view_type.upper()}: {str(e)}\n{traceback.format_exc()}"
        )
        return Response(
            {"Error": "Internal error."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_manager_required
def generate_shift_logs_report(request):
    try:
        user = util.api_get_user_object_from_session(request)

        store_id = util.clean_param_str(request.GET.get("store_id"))
        start = util.clean_param_str(request.GET.get("start"))
        end = util.clean_param_str(request.GET.get("end"))

        # Validate essential fields
        if not all([store_id, start, end]):
            return HttpResponse("Missing required parameters.", status=400)

        if not user.is_manager(store=int(store_id)):
            return HttpResponse("Not authorised.", status=403)

        # Optional filters
        only_unfinished = util.str_to_bool(request.GET.get("only_unfinished", "false"))
        only_pub = util.str_to_bool(request.GET.get("only_pub", "false"))
        filter_names_raw = util.clean_param_str(request.GET.get("filter", ""))

        try:
            filter_names_list = util.get_filter_list_from_string(filter_names_raw)
        except ValueError:
            return HttpResponse(
                "Invalid characters in employee filter field.", status=400
            )

        # Fetch shift data
        results, total = controllers.get_all_shifts(
            store_id=store_id,
            offset=0,
            limit=9999,
            start_date=start,
            end_date=end,
            sort_field="time",
            filter_names=filter_names_list,
            only_unfinished=only_unfinished,
            only_public_hol=only_pub,
            hide_deactivated=False,
            hide_resigned=False,
            allow_inactive_store=True,
        )

        # Generate PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=36,
            leftMargin=36,
            topMargin=54,
            bottomMargin=36,
        )

        elements = []
        styles = getSampleStyleSheet()

        # Header
        elements.append(
            Paragraph(f"Shift Logs Report — Store #{store_id}", styles["Title"])
        )
        elements.append(Paragraph(f"Date Range: {start} to {end}", styles["Normal"]))
        elements.append(Spacer(1, 12))

        # Table data
        table_data = [
            [
                "Staff Name",
                "Rounded Login",
                "Rounded Logout",
                "Public Hol",
                "Deliveries",
                "Hours Worked",
            ]
        ]

        for r in results:
            full_name = (
                f"{r.get('emp_first_name','')} {r.get('emp_last_name','')}".strip()
                or "-"
            )
            try:
                hours = float(r.get("hours_worked", 0) or 0)
            except ValueError:
                hours = 0.0

            table_data.append(
                [
                    full_name,
                    r.get("login_time", "-") or "-",
                    r.get("logout_time", "-") or "-",
                    "Yes" if r.get("is_public_holiday") else "No",
                    str(r.get("deliveries", 0)),
                    f"{hours:.2f}",
                ]
            )

        if len(table_data) == 1:
            table_data.append(["No shifts found", "", "", "", "", ""])

        # Table formatting
        table = Table(table_data, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d6efd")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.whitesmoke),
                ]
            )
        )

        elements.append(table)
        elements.append(Spacer(1, 12))

        # Timestamp Footer
        generated_time = datetime.now().strftime("%d %b %Y %H:%M:%S")
        timestamp = f"<font size=8 color='#888888'>Generated: {generated_time}</font>"
        elements.append(Paragraph(timestamp, styles["Normal"]))

        doc.build(elements)

        pdf = buffer.getvalue()
        buffer.close()

        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'inline; filename="shift_logs_{store_id}.pdf"'
        )
        return response

    except err.NotAssociatedWithStoreAsManagerError:
        return HttpResponse("Not authorised.", status=403)

    except Exception as e:
        logger.critical(f"Shift logs report error: {e}\n{traceback.format_exc()}")
        return HttpResponse("Internal error.", status=500)


@api_manager_required
def generate_account_summary_report(request):
    try:
        # Validate user & params
        user = util.api_get_user_object_from_session(request)

        store_id = util.clean_param_str(request.GET.get("store_id"))
        start = util.clean_param_str(request.GET.get("start"))
        end = util.clean_param_str(request.GET.get("end"))
        if not all([store_id, start, end]):
            return HttpResponse("Missing required parameters.", status=400)

        if not user.is_manager(store=int(store_id)):
            return HttpResponse("Not authorised.", status=403)

        # Optional filters
        ignore_no_hours = util.str_to_bool(request.GET.get("ignore_no_hours", "false"))
        filter_raw = util.clean_param_str(request.GET.get("filter", ""))

        try:
            filter_list = util.get_filter_list_from_string(filter_raw)
        except ValueError:
            return HttpResponse("Invalid name filter.", status=400)

        # Get the account summaries
        summaries, total = controllers.get_account_summaries(
            store_id=store_id,
            offset=0,
            limit=9999,
            start_date=start,
            end_date=end,
            ignore_no_hours=ignore_no_hours,
            sort_field="name",
            filter_names=filter_list,
            allow_inactive_store=True,
        )

        # ===  PDF GENERATION STARTS HERE ===

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=36,
            leftMargin=36,
            topMargin=54,
            bottomMargin=36,
        )

        elements = []
        styles = getSampleStyleSheet()

        # Title
        elements.append(
            Paragraph(f"Account Summary Report — Store #{store_id}", styles["Title"])
        )
        elements.append(Paragraph(f"Date Range: {start} to {end}", styles["Normal"]))

        if ignore_no_hours:
            elements.append(
                Paragraph("Ignored employees with no hours", styles["Normal"])
            )

        if filter_list:
            elements.append(
                Paragraph(
                    f"Filtered Employees: {', '.join(filter_list)}", styles["Normal"]
                )
            )

        elements.append(Spacer(1, 12))

        # Table header
        data = [
            [
                "Staff Name",
                "Weekday Hrs",
                "Weekend Hrs",
                "Public Hol Hrs",
                "Deliveries",
                "Total Hours",
                "Age",
            ]
        ]

        # Populate rows
        for summary in summaries:

            data.append(
                [
                    summary.get("name", "-"),
                    summary.get("hours_weekday", 0),
                    summary.get("hours_weekend", 0),
                    summary.get("hours_public_holiday", 0),
                    summary.get("deliveries", 0),
                    summary.get("hours_total", 0),
                    summary.get("age", "N/A"),
                ]
            )

        if len(data) == 1:
            data.append(["No records found", "", "", "", "", "", ""])

        table = Table(data, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d6efd")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.whitesmoke),
                ]
            )
        )

        elements.append(table)
        elements.append(Spacer(1, 12))

        # Footer timestamp
        generated_time = datetime.now().strftime("%d %b %Y %H:%M:%S")
        elements.append(
            Paragraph(
                f"<font size=8 color='#888888'>Generated: {generated_time}</font>",
                styles["Normal"],
            )
        )

        doc.build(elements)

        pdf = buffer.getvalue()
        buffer.close()

        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'inline; filename="account_summary_{store_id}.pdf"'
        )
        return response

    except err.NotAssociatedWithStoreAsManagerError:
        return HttpResponse("Not authorised.", status=403)
    except Exception as e:
        logger.critical(f"Account summary PDF error: {e}\n{traceback.format_exc()}")
        return HttpResponse("Internal error.", status=500)
