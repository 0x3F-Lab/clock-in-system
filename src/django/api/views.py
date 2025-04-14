import logging
import json
import api.utils as util
from api.utils import round_datetime_minute
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


@manager_required
@ensure_csrf_cookie
@api_view(["GET", "POST"])
@renderer_classes([JSONRenderer])
def raw_data_logs_view(request):
    if request.method == "GET":
        if request.headers.get("Accept") == "application/json":
            activities = (
                Activity.objects.all()
                .select_related("employee_id")
                .order_by("-login_timestamp")
            )
            data = []
            for act in activities:
                staff_name = f"{act.employee_id.first_name} {act.employee_id.last_name}"
                hours_decimal = (
                    act.shift_length_mins / 60.0 if act.shift_length_mins else 0.0
                )
                data.append(
                    {
                        "id": act.id,
                        "staff_name": staff_name,
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
                        "exact_login_timestamp": (
                            localtime(act.login_timestamp).strftime("%d/%m/%Y %H:%M")
                            if act.login_timestamp
                            else "N/A"
                        ),
                        "exact_logout_timestamp": (
                            localtime(act.logout_timestamp).strftime("%d/%m/%Y %H:%M")
                            if act.logout_timestamp
                            else "N/A"
                        ),
                        "deliveries": act.deliveries,
                        "hours_worked": f"{hours_decimal:.2f}",
                    }
                )
            return JsonResponse(data, safe=False)
        else:
            # Render HTML template
            get_token(request)  # ensure CSRF token
            return render(request, "auth_app/raw_data_logs.html")

    elif request.method == "POST":
        """
        Create a new Activity record.
        exact_login_timestamp & exact_logout_timestamp remain None to show as N/A.
        """
        data = request.data

        required_fields = ["employee_id", "login_time", "logout_time"]
        missing = [f for f in required_fields if f not in data]
        if missing:
            return JsonResponse(
                {"Error": f"Missing field(s): {', '.join(missing)}"},
                status=400,
            )

        try:
            employee_id = data.get("employee_id")
            login_str = data.get("login_time")  # e.g. "2025-01-01T14:30:00"
            logout_str = data.get("logout_time")  # e.g. "2025-01-01T17:45:00"
            is_public_holiday = data.get("is_public_holiday", False)
            deliveries = data.get("deliveries", 0)

            # Parse naive datetimes (no time zone)
            login_dt = datetime.strptime(login_str, "%Y-%m-%dT%H:%M:%S")
            logout_dt = datetime.strptime(logout_str, "%Y-%m-%dT%H:%M:%S")

            emp = get_object_or_404(User, id=employee_id)

            now_ts = datetime.now()

            # Create the new activity record
            activity = Activity.objects.create(
                employee_id=emp,
                login_time=login_dt,
                logout_time=logout_dt,
                login_timestamp=now_ts,
                logout_timestamp=now_ts,
                is_public_holiday=is_public_holiday,
                deliveries=deliveries,
            )

            # Calculate shift length if both times exist
            if activity.login_time and activity.logout_time:
                delta = activity.logout_time - activity.login_time
                activity.shift_length_mins = int(delta.total_seconds() // 60)
                activity.save()

            return JsonResponse(
                {"message": "Activity created successfully", "id": activity.id},
                status=201,
            )

        except ValueError as ve:
            # e.g., datetime parsing error
            logger.error(f"Date parse error: {ve}")
            return JsonResponse(
                {"Error": f"Invalid date/time format: {ve}"}, status=400
            )
        except User.DoesNotExist:
            return JsonResponse({"Error": "Invalid employee_id"}, status=404)
        except Exception as e:
            logger.error(f"Error creating Activity: {e}")
            return JsonResponse({"Error": "Internal error."}, status=500)


@manager_required
@ensure_csrf_cookie
@api_view(["GET", "PUT", "DELETE"])
@renderer_classes([JSONRenderer])
def raw_data_logs_detail_view(request, id):
    """
    Handle retrieval (GET) and updates (PUT) for a single Activity record.
    """
    # Attempt to fetch the activity by ID
    activity = get_object_or_404(Activity, id=id)

    if request.method == "GET":
        # Return JSON data for a single Activity
        staff_name = (
            f"{activity.employee_id.first_name} {activity.employee_id.last_name}"
        )
        hours_decimal = (
            activity.shift_length_mins / 60.0 if activity.shift_length_mins else 0.0
        )

        data = {
            "login_time": (
                localtime(activity.login_time).strftime("%Y-%m-%dT%H:%M:%S")
                if activity.login_time
                else None
            ),
            "logout_time": (
                localtime(activity.logout_time).strftime("%Y-%m-%dT%H:%M:%S")
                if activity.logout_time
                else None
            ),
            "is_public_holiday": activity.is_public_holiday,
            "login_timestamp": (
                activity.login_timestamp.strftime("%Y-%m-%dT%H:%M:%S")
                if activity.login_timestamp
                else None
            ),
            "logout_timestamp": (
                activity.logout_timestamp.strftime("%Y-%m-%dT%H:%M:%S")
                if activity.logout_timestamp
                else None
            ),
            "deliveries": activity.deliveries,
            "shift_length_mins": activity.shift_length_mins,
            "hours_worked": f"{hours_decimal:.2f}",
        }

        return JsonResponse(data, safe=False)

    if request.method == "PUT":
        required_fields = ["login_time", "logout_time"]
        # Update the Activity
        data = request.data
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return JsonResponse(
                {"Error": f"Missing required fields: {', '.join(missing_fields)}"},
                status=400,
            )

        # For example, if you decide to let the manager update the rounded times:
        login_time_str = data.get("login_time")
        logout_time_str = data.get("logout_time")

        # Check if manually logging out a user
        employee = get_object_or_404(User, id=activity.employee_id)

        # Parse the string times if provided (assuming they come in as ISO8601, e.g. "2025-01-01T14:30:00")
        if login_time_str:
            login_time = datetime.strptime(login_time_str, "%Y-%m-%dT%H:%M:%S")
            activity.login_time = round_datetime_minute(login_time)
            activity.login_timestamp = login_time
        if logout_time_str:
            logout_time = datetime.strptime(logout_time_str, "%Y-%m-%dT%H:%M:%S")
            activity.logout_time = round_datetime_minute(
                logout_time
            )  # Apply rounding function
            activity.logout_timestamp = logout_time

            # Clock out user if they were clocked in
            if employee.clocked_in:
                employee.clocked_in = False
                employee.save()

        # is_public_holiday, deliveries, etc.
        if "is_public_holiday" in data:
            activity.is_public_holiday = data["is_public_holiday"]

        if "deliveries" in data:
            activity.deliveries = data["deliveries"]

        if activity.login_time and activity.logout_time:
            delta = activity.logout_time - activity.login_time
            activity.shift_length_mins = int(delta.total_seconds() // 60)

        # Save the changes
        activity.save()

        return JsonResponse({"message": "Activity updated successfully"})

    elif request.method == "DELETE":

        # Check user isn't clocked in from this activity
        if not activity.logout_time:
            employee = get_object_or_404(User, id=activity.employee_id)
            employee.clocked_in = False
            employee.save()

        activity.delete()
        return JsonResponse({"message": "Activity deleted successfully"}, status=204)

    # Fallback
    return JsonResponse({"Error": "Invalid request"}, status=400)


@manager_required
@api_view(["GET"])
@renderer_classes([JSONRenderer])
def list_all_employee_details(request):
    try:
        employees = User.objects.order_by("first_name", "last_name")

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
        return JsonResponse(employee_data, safe=False)

    except Exception as e:
        # Handle any unexpected exceptions
        logger.critical(
            f"Failed to list all employee data (full dump), resulting in the error: {str(e)}"
        )
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@manager_required
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

        return JsonResponse(employee_data, safe=False)

    except Exception as e:
        # Handle any unexpected exceptions
        logger.critical(
            f"Failed to list employee details for ID {id}, resulting in the error: {str(e)}"
        )
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@manager_required
@api_view(["POST"])
@renderer_classes([JSONRenderer])
def update_employee_details(request, id):
    try:
        employee = User.objects.get(id=id)

        # Parse data from request
        data = json.loads(request.body)
        employee.first_name = str(data.get("first_name", employee.first_name))
        employee.last_name = str(data.get("last_name", employee.last_name))
        employee.email = str(data.get("email", employee.email))
        employee.phone_number = str(data.get("phone", employee.phone_number))

        if "pin" in data:
            employee.set_pin(str(data["pin"]))

        ########## CHECKS ON THIS IS NEEDED!!!

        employee.save()
        return JsonResponse(
            {"message": "Employee updated successfully"},
            status=status.HTTP_202_ACCEPTED,
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


@manager_required
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
                {"Error": "Email already exists"},
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
            {"message": "Employee created successfully", "id": employee.id},
            status=status.HTTP_201_CREATED,
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


@manager_required
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
