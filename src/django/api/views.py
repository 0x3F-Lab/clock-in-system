import logging
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import api.controllers as controllers
from auth_app.models import User, Activity
from rest_framework.renderers import JSONRenderer
from rest_framework.decorators import renderer_classes
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.middleware.csrf import get_token
import json

logger = logging.getLogger("api")


@api_view(["GET"])
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
        logger.error(f"Failed to list all users, resulting in the error: {str(e)}")
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@renderer_classes([JSONRenderer])
def raw_data_logs_view(request):
    if request.method == "GET":
        if request.headers.get("Accept") == "application/json":
            activities = Activity.objects.all().select_related("employee_id")
            data = []
            for act in activities:
                staff_name = f"{act.employee_id.first_name} {act.employee_id.last_name}"
                data.append(
                    {
                        "staff_name": staff_name,
                        "login_time": (
                            act.login_time.strftime("%H:%M")
                            if act.login_time
                            else "N/A"
                        ),
                        "logout_time": (
                            act.logout_time.strftime("%H:%M")
                            if act.logout_time
                            else "N/A"
                        ),
                        "is_public_holiday": act.is_public_holiday,
                        "exact_login_timestamp": (
                            act.login_timestamp.strftime("%d/%m/%Y %H:%M")
                            if act.login_timestamp
                            else "N/A"
                        ),
                        "exact_logout_timestamp": (
                            act.logout_timestamp.strftime("%d/%m/%Y %H:%M")
                            if act.logout_timestamp
                            else "N/A"
                        ),
                        "deliveries": act.deliveries,
                        "hours_worked": str(act.hours_worked),
                    }
                )
            # Log and return the JSON response
            json_response = json.dumps(data, indent=2)
            print(json_response)  # Log to console for debugging
            return JsonResponse(data, safe=False)

        else:
            # Return the template with CSRF token
            get_token(request)
            return render(request, "auth_app/raw_data_logs.html")


@api_view(["GET", "PUT"])
@renderer_classes([JSONRenderer])
def employee_details_view(request, id=None):
    if request.method == "GET":
        if request.headers.get("Accept") == "application/json":
            # JSON response logic here (unchanged)
            if id is not None:
                employee = get_object_or_404(User, id=id, is_manager=False)
                employee_data = {
                    "id": employee.id,
                    "first_name": employee.first_name,
                    "last_name": employee.last_name,
                    "email": employee.email,
                    "phone_number": employee.phone_number,
                    "pin": employee.pin,
                }
                return JsonResponse(employee_data, safe=False)
            else:
                employees = User.objects.filter(is_manager=False)
                employee_data = [
                    {
                        "id": emp.id,
                        "first_name": emp.first_name,
                        "last_name": emp.last_name,
                        "email": emp.email,
                        "phone_number": emp.phone_number,
                        "pin": emp.pin,
                    }
                    for emp in employees
                ]
                return JsonResponse(employee_data, safe=False)
        else:
            # Not JSON: Return the HTML and ensure CSRF cookie is set
            get_token(request)  # This forces a CSRF cookie to be sent
            return render(request, "auth_app/employee_details.html")

    if request.method == "PUT" and id:
        # PUT logic unchanged
        employee = get_object_or_404(User, id=id)
        data = request.data
        employee.first_name = data.get("first_name", employee.first_name)
        employee.last_name = data.get("last_name", employee.last_name)
        employee.email = data.get("email", employee.email)
        employee.phone_number = data.get("phone_number", employee.phone_number)

        if "pin" in data:
            employee.pin = data["pin"]

        employee.save()
        return JsonResponse({"message": "Employee updated successfully"})

    return JsonResponse({"error": "Invalid request"}, status=400)


def employee_details_page(request):
    """
    View to render the employee details HTML page.
    """
    get_token(request)
    return render(request, "auth_app/employee_details.html")


@api_view(["GET"])
@renderer_classes([JSONRenderer])
def raw_data_logs_view(request):
    if request.method == "GET":
        if request.headers.get("Accept") == "application/json":
            activities = Activity.objects.all().select_related("employee_id")
            data = []
            for act in activities:
                staff_name = f"{act.employee_id.first_name} {act.employee_id.last_name}"
                data.append(
                    {
                        "staff_name": staff_name,
                        "login_time": (
                            act.login_time.strftime("%H:%M")
                            if act.login_time
                            else "N/A"
                        ),
                        "logout_time": (
                            act.logout_time.strftime("%H:%M")
                            if act.logout_time
                            else "N/A"
                        ),
                        "is_public_holiday": act.is_public_holiday,
                        "exact_login_timestamp": (
                            act.login_timestamp.strftime("%d/%m/%Y %H:%M")
                            if act.login_timestamp
                            else "N/A"
                        ),
                        "exact_logout_timestamp": (
                            act.logout_timestamp.strftime("%d/%m/%Y %H:%M")
                            if act.logout_timestamp
                            else "N/A"
                        ),
                        "deliveries": act.deliveries,
                        "hours_worked": str(act.hours_worked),
                    }
                )
            # Log and return the JSON response
            json_response = json.dumps(data, indent=2)
            print(json_response)  # Log to console for debugging
            return JsonResponse(data, safe=False)

        else:
            # Return the template with CSRF token
            get_token(request)
            return render(request, "auth_app/raw_data_logs.html")


@api_view(["GET", "PUT"])
@renderer_classes([JSONRenderer])
def employee_details_view(request, id=None):
    if request.method == "GET":
        if request.headers.get("Accept") == "application/json":
            # JSON response logic here (unchanged)
            if id is not None:
                employee = get_object_or_404(User, id=id, is_manager=False)
                employee_data = {
                    "id": employee.id,
                    "first_name": employee.first_name,
                    "last_name": employee.last_name,
                    "email": employee.email,
                    "phone_number": employee.phone_number,
                    "pin": employee.pin,
                }
                return JsonResponse(employee_data, safe=False)
            else:
                employees = User.objects.filter(is_manager=False)
                employee_data = [
                    {
                        "id": emp.id,
                        "first_name": emp.first_name,
                        "last_name": emp.last_name,
                        "email": emp.email,
                        "phone_number": emp.phone_number,
                        "pin": emp.pin,
                    }
                    for emp in employees
                ]
                return JsonResponse(employee_data, safe=False)
        else:
            # Not JSON: Return the HTML and ensure CSRF cookie is set
            get_token(request)  # This forces a CSRF cookie to be sent
            return render(request, "auth_app/employee_details.html")

    if request.method == "PUT" and id:
        # PUT logic unchanged
        employee = get_object_or_404(User, id=id)
        data = request.data
        employee.first_name = data.get("first_name", employee.first_name)
        employee.last_name = data.get("last_name", employee.last_name)
        employee.email = data.get("email", employee.email)
        employee.phone_number = data.get("phone_number", employee.phone_number)

        if "pin" in data:
            employee.pin = data["pin"]

        employee.save()
        return JsonResponse({"message": "Employee updated successfully"})

    return JsonResponse({"error": "Invalid request"}, status=400)


def employee_details_page(request):
    """
    View to render the employee details HTML page.
    """
    get_token(request)
    return render(request, "auth_app/employee_details.html")


@api_view(["POST", "PUT"])
def clock_in(request, id):
    # Delegate to the controller function
    return controllers.handle_clock_in(employee_id=id)


@api_view(["POST", "PUT"])
def clock_out(request, id):
    # Check if they made any deliveries on clock out
    deliveries = max(
        int(request.data.get("deliveries", 0)), 0  # Ensure it's an integer and above 0
    )

    # Delegate to the controller function
    return controllers.handle_clock_out(employee_id=id, deliveries=deliveries)


@api_view(["GET"])
def clocked_state_view(request, id):
    """
    API view to get the clocked-in state of a user by ID.
    """
    try:
        # Get the user's info
        info = controllers.get_employee_clocked_info(employee_id=id)

        # Return the info
        return Response(info, status=status.HTTP_200_OK)

    except User.DoesNotExist:
        # Return a 404 if the user does not exist
        return Response(
            {"Error": f"User not found with ID {id}."}, status=status.HTTP_404_NOT_FOUND
        )
    except Activity.DoesNotExist:
        # Return a 417 if the user's state is bugged
        logger.error(
            f"User with ID {id} has a bugged state due to missing activity record to complete a shift record."
        )
        return Response(
            {
                "Error": f"User state is bugged due to missing activity records. Please contact an admin."
            },
            status=status.HTTP_417_EXPECTATION_FAILED,
        )
    except Exception as e:
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
