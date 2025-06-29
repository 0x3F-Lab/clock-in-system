import re
import markdown
import api.exceptions as err

from bleach import clean
from functools import wraps
from rest_framework import status
from datetime import date, datetime
from django.shortcuts import redirect
from django.http import JsonResponse
from django.urls import reverse
from django.contrib import messages
from django.utils.http import urlencode
from django.utils.timezone import now, localtime, is_aware
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
                status=status.HTTP_401_UNAUTHORIZED,
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
                status=status.HTTP_401_UNAUTHORIZED,
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


def get_user_associated_stores_full_info(user: User) -> dict:
    """
    Get the user's associated stores and return all possible info about the store.
    SHOULD ONLY BE USED IN MANAGER PAGES.
    Args:
      user (User): The User object of the user to get the associated stores for.
    """

    stores = user.get_associated_stores(show_inactive=user.is_manager)

    if len(stores) < 1 or not stores:
        return {}

    store_data = {}
    for store in stores:
        store_data[store.id] = {
            "name": store.name,
            "code": store.code,
            "loc_street": store.location_street,
            "loc_lat": float(store.location_latitude),
            "loc_long": float(store.location_longitude),
            "clocking_dist": int(store.allowable_clocking_dist_m),
            "pin": store.store_pin,
            "is_active": store.is_active,
            "is_clocking_enabled": store.is_clocking_enabled,
            "is_health_safety_enabled": store.is_health_safety_enabled,
        }

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
    unread_notifs = employee.get_unread_notifications().select_related("sender")

    if include_notifications:
        unread_notifications = []
        for notif in unread_notifs:
            unread_notifications.append(
                {
                    "id": notif.id,
                    "title": notif.title,
                    "message": add_placeholder_text(
                        string=notif.message, user_obj=employee
                    ),
                    "type": notif.notification_type,
                    "sender": get_notification_sender_name(notif=notif),
                    "receiver": get_notification_receiver_name(
                        notif=notif, is_received=True
                    ),
                    "created_at": notif.created_at,
                    "expires_on": notif.expires_on,
                    "store": notif.store.code if notif.store else None,
                }
            )

        read_notifications = []
        read_notifs = employee.get_read_notifications().select_related("sender")
        for notif in read_notifs:
            read_notifications.append(
                {
                    "id": notif.id,
                    "title": notif.title,
                    "message": add_placeholder_text(
                        string=notif.message, user_obj=employee
                    ),
                    "type": notif.notification_type,
                    "sender": get_notification_sender_name(notif=notif),
                    "receiver": get_notification_receiver_name(
                        notif=notif, is_received=True
                    ),
                    "created_at": notif.created_at,
                    "expires_on": notif.expires_on,
                    "store": notif.store.code if notif.store else None,
                }
            )

        sent_notifications = []
        sent_notifs = employee.get_sent_notifications()
        for notif in sent_notifs:
            sent_notifications.append(
                {
                    "id": notif.id,
                    "title": notif.title,
                    "message": add_placeholder_text(
                        string=notif.message, user_obj=employee
                    ),
                    "type": notif.notification_type,
                    "receiver": get_notification_receiver_name(
                        notif=notif, is_received=False
                    ),
                    "created_at": notif.created_at,
                    "expires_on": notif.expires_on,
                    "store": notif.store.code if notif.store else None,
                }
            )

        return {
            "user_id": employee_id,
            "user_name": employee.first_name,
            "associated_stores": store_data,
            "notifications": {
                "unread": unread_notifications,
                "read": read_notifications,
                "read_count": read_notifs.count(),
                "sent": sent_notifications,
                "sent_count": sent_notifs.count(),
            },
            "notification_count": unread_notifs.count(),
        }, employee

    # Else, dont include notifications (SAVES WORK)
    return {
        "user_id": employee_id,
        "user_name": employee.first_name,
        "associated_stores": store_data,
        "notification_count": unread_notifs.count(),
    }, employee


def get_notification_sender_name(notif: Notification) -> str:
    """
    Get the notification sender or replace it with an appropriate string for
    certain cases.
    A Notification object must be given.
    """
    if notif.notification_type == Notification.Type.AUTOMATIC_ALERT:
        return "SYSTEM"
    elif (
        notif.notification_type == Notification.Type.SYSTEM_ALERT
        or notif.notification_type == Notification.Type.ADMIN_NOTE
    ):
        return "ADMIN"
    elif not notif.sender:
        return "ADMIN"
    elif notif.sender.is_hidden:
        return "ADMIN"
    elif notif.sender.is_manager:
        return f"{notif.sender.first_name} {notif.sender.last_name} [Manager]"
    else:
        return f"{notif.sender.first_name} {notif.sender.last_name}"


def get_notification_receiver_name(
    notif: Notification, is_received: bool = True
) -> str:
    """
    Get the notification receiver or replace it with an appropriate string for
    certain cases depending if its a SENT or RECIEVED notification.
    Args:
      - notif (Notification): The notification object.
      - is_received (bool) = True: If the user has recieved this notification or has sent it.
    """
    if (
        notif.recipient_group == Notification.RecipientType.STORE_EMPLOYEES
        and notif.store
    ):
        return f"All Store Employees for store <code>{notif.store.code}</code>"
    elif (
        notif.recipient_group == Notification.RecipientType.STORE_MANAGERS
        and notif.store
    ):
        return f"All Store Managers for store <code>{notif.store.code}</code>"
    elif notif.recipient_group == Notification.RecipientType.ALL_USERS:
        return "All active users on the site"
    elif notif.recipient_group == Notification.RecipientType.ALL_MANAGERS:
        return "All active managers on the site"
    elif notif.recipient_group == Notification.RecipientType.SITE_ADMINS:
        return "All active site admins"
    elif notif.recipient_group == Notification.RecipientType.INDIVIDUAL:
        return "You only"

    # 'OTHER' option, etc.
    else:
        recipients = User.objects.filter(
            notification_receipts__notification=notif
        ).distinct()
        return f"{recipients.count()} Employees"


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
            "underline",
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
    if not value:
        return ""

    # Remove unneeded new lines and carriage returns
    value = re.sub(r"\s*[\r\n]+\s*", "", value)

    # Render markdown to HTML
    html = markdown.markdown(
        value.strip(), extensions=["markdown.extensions.extra", "underline"]
    )

    # Sanitise rendered HTML (allow only formatting tags)
    return clean(
        html,
        tags=["b", "strong", "i", "em", "u", "code", "del", "strike"],
        attributes={},
        strip=True,
    )


def add_placeholder_text(string: str, user_obj: User) -> str:
    """
    Function to replace all available placeholders with their respective strings.
    If no user object is given, then default values will replace the placeholders.
    Args:
      - string (str): The string text to replace placeholders with their respective text.
      - user_obj (User): The User object of the user the placeholders will be based upon. REQUIRED!

    Placeholders:
      - %user.first_name% => User's first name (Default='Employee')
      - %user.last_name% => User's last name (Default='')
      - %user.role% => 'Employee', 'Manager', 'Site Admin' based on user's permissions (Default='Employee')
      - %user.active_state% => 'ACTIVE' or 'INACTIVE' (Default='UNKNOWN')
      - %user.creation_date% => User's account creation date as DD/MM/YYYY (Default='UNKNOWN')
      - %user.birth_date% => User's birth date as DD/MM/YYYY or 'N/A' (Default='UNKNOWN')
      - %user.phone% => User's phone number or 'N/A' (Default='N/A')
      - %user.email% => User's email address (Default='UNKNOWN')
      - %user.clocked_in_global% => If user is clocked in to ANY store (Default='UNKNOWN')
      - %user.store_count% => Number of stores associated to the user (Default='0')
      - %user.unread_notifications_count% => Number of unread notifications for the user (Default='UNKNOWN')
      - %server.date% => Date of the server DD/MM/YYYY
      - %server.time% => Time of the server HH:MM
    """
    default_replace = False
    if user_obj is None or not isinstance(user_obj, User):
        default_replace = True

    def format_date(date_obj):
        if not date_obj:
            return "UNKNOWN"
        elif isinstance(date_obj, datetime):
            # Ensure it's timezone-aware before using localtime
            dt = localtime(date_obj) if is_aware(date_obj) else date_obj
            return dt.strftime("%d/%m/%Y")
        elif isinstance(date_obj, date):
            return date_obj.strftime("%d/%m/%Y")

        return "UNKNOWN"

    def get_user_role(user: User):
        if user.is_hidden:
            return "Site Admin"
        elif user.is_manager:
            return "Manager"
        return "Employee"

    placeholder_funcs = {
        "%user.first_name%": lambda: (
            "Employee" if default_replace else user_obj.first_name or "Employee"
        ),
        "%user.last_name%": lambda: "" if default_replace else user_obj.last_name or "",
        "%user.role%": lambda: (
            "Employee" if default_replace else get_user_role(user_obj)
        ),
        "%user.active_state%": lambda: (
            "UNKNOWN"
            if default_replace
            else ("ACTIVE" if user_obj.is_active else "INACTIVE")
        ),
        "%user.creation_date%": lambda: (
            "UNKNOWN" if default_replace else format_date(user_obj.created_at)
        ),
        "%user.birth_date%": lambda: (
            "UNKNOWN" if default_replace else format_date(user_obj.birth_date)
        ),
        "%user.phone%": lambda: (
            "N/A" if default_replace else (user_obj.phone_number or "N/A")
        ),
        "%user.email%": lambda: (
            "UNKNOWN" if default_replace else user_obj.email or "UNKNOWN"
        ),
        "%user.clocked_in_global%": lambda: (
            "UNKNOWN"
            if default_replace
            else ("Yes" if user_obj.is_clocked_in() else "No")
        ),
        "%user.store_count%": lambda: (
            "0" if default_replace else str(user_obj.get_associated_stores().count())
        ),
        "%user.unread_notifications_count%": lambda: (
            "UNKNOWN"
            if default_replace
            else str(user_obj.get_unread_notifications().count())
        ),
        "%server.date%": lambda: localtime(now()).strftime("%d/%m/%Y"),
        "%server.time%": lambda: localtime(now()).strftime("%H:%M"),
    }

    for placeholder, value_fn in placeholder_funcs.items():
        if placeholder in string:
            string = string.replace(placeholder, value_fn())

    return string
