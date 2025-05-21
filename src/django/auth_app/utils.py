import re
import markdown
import api.exceptions as err

from bleach import clean
from functools import wraps
from rest_framework import status
from django.shortcuts import redirect
from django.http import JsonResponse
from django.urls import reverse
from django.contrib import messages
from django.utils.http import urlencode
from auth_app.models import User, Notification
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


def get_default_page_context(request, include_notifications: bool = False):
    """
    Get the user's context and User object from their user_id stored in their session information.
    If the user is NOT LOGGED IN, it returns an empty context dict and None for the User object.

    Args:
      - request: The request made to the endpoint by the user.
      - include_notifications (bool) = False: Whether to include all the physical notifications instead of just the count.
    """
    # Get user's id
    employee_id = request.session.get("user_id", None)

    # If the user is NOT LOGGED IN -> return empty context and NULL user
    if employee_id is None:
        return {}, None

    # Get employee data to check state
    try:
        employee = User.objects.get(id=employee_id)

    except User.DoesNotExist as e:
        request.session.flush()
        raise e

    # Get associated stores
    stores = employee.get_associated_stores(show_inactive=employee.is_manager)
    if len(stores) < 1 or not stores:
        messages.error(
            request,
            "Your account has no associated stores. Please contact a store manager.",
        )
    store_data = {store.id: store.code for store in stores}

    # Get user's notifications
    notifs = employee.get_unread_notifications().select_related("sender")

    if include_notifications:
        notifications = []
        for notif in notifs:
            if notif.notification_type == Notification.Type.AUTOMATIC_ALERT:
                sender = "SYSTEM"
            elif (
                notif.notification_type == Notification.Type.SYSTEM_ALERT
                or notif.notification_type == Notification.Type.ADMIN_NOTE
            ) or not notif.sender:
                sender = "ADMIN"
            elif notif.sender.is_hidden:
                sender = "ADMIN"
            else:
                sender = f"{notif.sender.first_name} {notif.sender.last_name}"

            notifications.append(
                {
                    "id": notif.id,
                    "title": notif.title,
                    "message": notif.message,
                    "type": notif.notification_type,
                    "sender": sender,
                    "created_at": notif.created_at,
                    "expires_on": notif.expires_on,
                    "store": notif.store.code if notif.store else None,
                    "store_broadcast": notif.broadcast_to_store,
                }
            )

        return {
            "user_id": employee_id,
            "user_name": employee.first_name,
            "associated_stores": store_data,
            "notifications": notifications,
            "notification_count": notifs.count(),
        }, employee

    # Else, dont include notifications (SAVES WORK)
    return {
        "user_id": employee_id,
        "user_name": employee.first_name,
        "associated_stores": store_data,
        "notification_count": notifs.count(),
    }, employee


def sanitise_plain_text(value: str) -> str:
    return clean(value, tags=[], strip=True).strip()


def sanitise_markdown_message_text(value: str) -> str:
    """
    USED FOR NOTIFICATION MESSAGES!!
    Sanitises and formats markdown-like text such that:
    - Each line becomes a <p>...</p>
    - Single newlines become a <br> inside a <p>...</p> block
    - Double newlines are made into seperate <p>...</p> structures
    """
    if not value:
        return ""

    # Render markdown to HTML
    html = markdown.markdown(
        value.strip(),
        extensions=[
            "markdown.extensions.extra",
            "markdown.extensions.sane_lists",
            "markdown.extensions.nl2br",
        ],
    )

    # Sanitise rendered HTML (allow only formatting tags)
    safe_html = clean(
        html,
        tags=[
            "b",
            "strong",
            "i",
            "em",
            "u",
            "p",
            "blockquote",
            "code",
            "ul",
            "ol",
            "li",
            "br",
            "del",
            "strike",
        ],
        attributes={},
        strip=True,
    )

    # Remove leading/trailing <br> tags
    safe_html = re.sub(r"^(<br\s*/?>)+", "", safe_html)
    safe_html = re.sub(r"(<br\s*/?>)+$", "", safe_html)
    # Remove leading/trailing empty <p> tags (including whitespace inside)
    safe_html = re.sub(r"^(<p>\s*</p>)+", "", safe_html)
    safe_html = re.sub(r"(<p>\s*</p>)+$", "", safe_html)
    # Remove unneeded new lines and carriage returns after the fact (anything left over)
    safe_html = re.sub(r"\s*[\r\n]+\s*", "", safe_html)

    return safe_html


def sanitise_markdown_title_text(value: str) -> str:
    """
    Function to sanitise and apply markdown conversions to notification titles.
    """
    # Remove unneeded new lines and carriage returns
    value = re.sub(r"\s*[\r\n]+\s*", "", value)

    # Render markdown to HTML
    html = markdown.markdown(value.strip(), extensions=["markdown.extensions.extra"])

    # Sanitise rendered HTML (allow only formatting tags)
    return clean(
        html,
        tags=["b", "strong", "i", "em", "u", "code", "del", "strike"],
        attributes={},
        strip=True,
    )
