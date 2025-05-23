import api.exceptions as err

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
        referer = request.META.get("HTTP_REFERER")  # Previous page user was on

        # Redirect to login if they havent already
        if not user_id:
            url = create_redirection_url_for_login_including_return(request)
            messages.error(request, "Please login to access this page.")
            return redirect(url)

        # Get employee data to check state
        try:
            employee = User.objects.get(id=user_id)

            if not employee.is_active:
                request.session.flush()
                messages.error(
                    request,
                    "Your account is deactivated. Please contact a store manager.",
                )
                url = create_redirection_url_for_login_including_return(request)
                return redirect(url)
            elif not employee.is_setup:
                request.session.flush()
                messages.error(
                    request, "Your account is not setup. Please setup your account."
                )
                url = create_redirection_url_for_setup_including_return(request)
                return redirect(url)

        except User.DoesNotExist as e:
            request.session.flush()
            messages.error(
                request,
                "The account you have been authenticated with is bugged. Please login again.",
            )
            url = create_redirection_url_for_login_including_return(request)
            return redirect(url)

        if not employee.is_manager:
            messages.error(request, "You do not have permission to access this page.")

            # Sent user back to previous page if it was in the header
            if referer:
                return redirect(referer)
            else:
                return redirect("home")  # Fallback if no referer

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def api_manager_required(view_func):
    """
    Decorator to ensure the user is an authenticated manager.
    DOES NOT REDIRECT USER IF NOT AUTHENTICATED.
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
                    {
                        "Error": "Your account is deactivated. Please contact a store manager."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            elif not employee.is_setup:
                request.session.flush()
                return JsonResponse(
                    {"Error": "Your account is not setup. Please setup your account."},
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

        if not employee.is_manager:
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
            messages.error(request, "Please login to access this page.")
            return redirect(url)

        # Get employee data to check state
        try:
            employee = User.objects.get(id=user_id)

            if not employee.is_active:
                request.session.flush()
                messages.error(
                    request,
                    "Your account is deactivated. Please contact a store manager.",
                )
                url = create_redirection_url_for_login_including_return(request)
                return redirect(url)
            elif not employee.is_setup:
                request.session.flush()
                messages.error(
                    request, "Your account is not setup. Please setup your account."
                )
                url = create_redirection_url_for_setup_including_return(request)
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
                    {
                        "Error": "Your account is deactivated. Please contact a store manager."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            elif not employee.is_setup:
                request.session.flush()
                return JsonResponse(
                    {"Error": "Your account is not setup. Please setup your account."},
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


def create_redirection_url_for_setup_including_return(request):
    """
    Function to create the redirection URL required to send the user to the setup page and then return
    to the current page after successful account setup.
    """
    login_url = reverse("setup")
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


def get_user_associated_stores_from_session(request):
    # Get user's id
    employee_id = request.session.get("user_id")

    # Get employee data to check state
    try:
        employee = User.objects.get(id=employee_id)

    except User.DoesNotExist as e:
        request.session.flush()
        raise e

    stores = employee.get_associated_stores(show_inactive=employee.is_manager)

    if len(stores) < 1 or not stores:
        messages.error(
            request,
            "Your account has no associated stores. Please contact a store manager.",
        )

    store_data = {store.id: store.code for store in stores}
    return store_data
