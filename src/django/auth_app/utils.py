from functools import wraps
from rest_framework import status
from django.shortcuts import redirect
from django.http import JsonResponse
from django.urls import reverse
from django.contrib import messages
from django.utils.http import urlencode
from auth_app.models import User
from clock_in_system.settings import BASE_URL


def manager_required(view_func):
    """
    Decorator to ensure the user is an authenticated manager.
    """

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        user_id = request.session.get("user_id")
        is_manager = request.session.get("is_manager", False)
        if not user_id or not is_manager:
            return redirect("manager_login")  # Redirect to login if not a manager
        return view_func(request, *args, **kwargs)

    return _wrapped_view


# def manager_required(view_func):
#     """
#     Decorator to ensure the user is an authenticated manager.
#     """

#     @wraps(view_func)
#     def _wrapped_view(request, *args, **kwargs):
#         user_id = request.session.get("user_id")
#         is_manager = request.session.get("is_manager", False)
#         referer = request.META.get('HTTP_REFERER') # Previous page user was on

#         # Redirect to login if not logged in
#         if not user_id:
#             login_url = reverse("login")
#             params = urlencode({"next": request.get_full_path()}) ########################### NEED TO CHECK IT DOESNT NEED BASE URL
#             return redirect(f"{login_url}?{params}")

#         if not is_manager:
#             messages.error(request, "You do not have permission to access this page.")

#             # Sent user back to previous page if it was in the header
#             if referer:
#                 return redirect(referer)
#             else:
#                 return redirect("home")  # fallback if no referer

#         return view_func(request, *args, **kwargs)

#     return _wrapped_view


def api_manager_required(view_func):
    """
    Decorator to ensure the user is an authenticated manager.
    DOES NOT REDIRECT USER IF NOT AUTHENTICATED.
    """

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        user_id = request.session.get("user_id")
        is_manager = request.session.get("is_manager", False)
        if not user_id or not is_manager:
            return JsonResponse(
                {"Error": "You do not have permission to access this resource."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def employee_required(view_func):
    """
    Decorator to ensure the user is an authenticated employee (including managers & normal employees).
    """

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        user_id = request.session.get("user_id")

        # Redirect to login if they havent already
        if not user_id:
            url = create_redirection_url_for_login_including_return(request)
            return redirect(url)

        # Get employee data to check state
        try:
            employee = User.objects.get(id=user_id)

            if not employee.is_active:
                request.session.flush()
                messages.error(
                    request, "Your account is deactivated. Please login again."
                )
                url = create_redirection_url_for_login_including_return(request)
                return redirect(url)

        except User.DoesNotExist as e:
            request.session.flush()
            messages.error(
                request,
                "The account you have been authenticated with is bugged. Please login again.",
            )
            url = create_redirection_url_for_login_including_return(request)
            return redirect(url)

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def api_employee_required(view_func):
    """
    Decorator to ensure the user is an authenticated employee (including managers & normal employees).
    DOES NOT REDIRECT USER IF NOT AUTHENTICATED to be useable for api requests.
    """

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        user_id = request.session.get("user_id")

        # Redirect to login if they havent already
        if not user_id:
            return JsonResponse(
                {"Error": "You do not have permission to access this resource."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get employee data to check state
        try:
            employee = User.objects.get(id=user_id)

            if not employee.is_active:
                request.session.flush()
                return JsonResponse(
                    {"Error": "Your account is deactivated. Please login again."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        except User.DoesNotExist as e:
            request.session.flush()
            return JsonResponse(
                {
                    "Error": "The account you have been authenticated with is bugged. Please login again."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def create_redirection_url_for_login_including_return(request):
    """
    Function to create the redirection URL required to send the user to the login page and then return
    to the current page after successful login.
    """
    login_url = reverse("login")
    params = urlencode({"next": request.get_full_path()})
    return f"{login_url}?{params}"


def get_absolute_reverse_url(name):
    """
    Helper function to generate the entire full external address required for a user to change pages.
    """
    path = reverse(name)
    return (
        BASE_URL.rstrip("/") + "/" + path.lstrip("/")
    )  # Ensure correct '/' between URL and path
