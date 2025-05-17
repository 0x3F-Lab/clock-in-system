import logging
import api.exceptions as err

from django.urls import reverse
from django.contrib import messages
from django.contrib.sitemaps import Sitemap
from django.shortcuts import render, redirect
from django.core.exceptions import ValidationError
from django.template.response import TemplateResponse
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods
from auth_app.models import User, Store, Notification
from auth_app.utils import (
    manager_required,
    employee_required,
    get_user_associated_stores_from_session,
    get_default_page_context,
)
from auth_app.forms import (
    LoginForm,
    ManualClockingForm,
    AccountSetupForm,
    NotificationForm,
)
from api.utils import get_distance_from_lat_lon_in_m
from api.controllers import handle_clock_in, handle_clock_out
from clock_in_system.settings import STATIC_URL, BASE_URL, STATIC_CACHE_VER

logger = logging.getLogger("auth_app")


@require_GET
def logout(request):
    request.session.flush()  # Clear all session data
    messages.success(request, "Successfully logged out.")
    return redirect("home")


@require_http_methods(["GET", "POST"])
def login(request):
    if request.method == "POST":
        form = LoginForm(request.POST)

        if form.is_valid():
            email = form.cleaned_data.get("email")
            password = form.cleaned_data.get("password")
            next_url = request.POST.get("next", None) or request.GET.get("next", None)

            try:
                user = User.objects.get(email=email)  # Look up the user by email
            except User.DoesNotExist:
                messages.error(request, "Invalid credentials.")
                return render(request, "auth_app/login.html", {"form": form})

            # Ensure user can log into their account
            if not user.is_active:
                messages.error(
                    request,
                    "Cannot log into a deactivated account. Please contact a store manager.",
                )
                return render(request, "auth_app/login.html", {"form": form})

            elif not user.is_setup:
                messages.error(request, "Please setup your account to login.")
                return redirect(
                    f"{reverse('account_setup')}{f'?next={next_url}' if next_url else ''}"
                )

            # Check password
            elif user.check_password(password):
                # Log the user in by setting session data
                request.session["user_id"] = user.id
                request.session["is_manager"] = user.is_manager
                request.session["name"] = user.first_name

                if next_url:
                    return redirect(next_url)
                else:
                    return redirect("home")  # fallback after login

            else:
                # Return error (no need to render here, use final render at end)
                messages.error(request, "Invalid Credentials.")

        else:
            messages.error(request, "Failed to login. Please correct the errors.")

    else:
        form = LoginForm()

    # Go back home if they're already logged in
    user_id = request.session.get("user_id")
    if user_id:
        return redirect("home")

    return render(request, "auth_app/login.html", {"form": form})


@require_http_methods(["GET", "POST"])
def setup_account(request):
    if request.method == "POST":
        form = AccountSetupForm(request.POST)

        if form.is_valid():
            email = form.cleaned_data.get("email")
            password = form.cleaned_data.get("password")
            first_name = form.cleaned_data.get("first_name")
            last_name = form.cleaned_data.get("last_name")
            phone = form.cleaned_data.get("phone_number") or None
            dob = form.cleaned_data.get("birth_date") or None

            try:
                user = User.objects.get(email=email)  # Look up the user by email

                if not user.is_active:
                    messages.error(
                        request,
                        "Cannot setup an inactive account. Please contact a store manager.",
                    )
                    return render(
                        request, "auth_app/account_setup.html", {"form": form}
                    )

                # Set password
                user.set_password(raw_password=password)

                # Set the values
                user.first_name = first_name
                user.last_name = last_name

                if phone:
                    user.phone_number = phone

                if dob:
                    user.birth_date = dob

                # Ensure user account cannot be setup again
                user.is_setup = True

                # Save user object
                user.save()
                messages.success(request, "Successfully setup employee account.")

                logger.info(
                    f"Employee ID {user.id} ({user.first_name} {user.last_name}) SETUP their USER account."
                )
                logger.debug(
                    f"[UPDATE: USER (ID: {user.id})] [ACC SETUP] Name: {user.first_name} {user.last_name} -- Email: {user.email} -- Phone: {user.phone_number} -- DOB: {user.birth_date} -- PIN: {user.pin} -- MANAGER: {user.is_manager}"
                )

            except User.DoesNotExist:
                messages.error(request, "Invalid account email.")
                return render(request, "auth_app/account_setup.html", {"form": form})
            except ValidationError as e:
                messages.error(request, "Invalid data while saving the account.")
                logger.warning(
                    f"Failed to setup account with email {email} ({first_name} {last_name}) due to a database validation error, producing the error: {e}"
                )
                return render(request, "auth_app/account_setup.html", {"form": form})
            except Exception as e:
                messages.error(
                    request,
                    "Failed to setup account due to internal server error. Please try again later.",
                )
                logger.critical(
                    f"Failed to setup account with email {email} ({first_name} {last_name}), producing the error: {e}"
                )
                return render(request, "auth_app/account_setup.html", {"form": form})

            # Log the user in by setting session data
            request.session["user_id"] = user.id
            request.session["is_manager"] = user.is_manager
            request.session["name"] = user.first_name

            next_url = request.POST.get("next", None) or request.GET.get("next", None)
            if next_url:
                return redirect(next_url)
            else:
                return redirect("home")  # fallback after login

        else:
            messages.error(
                request, "Failed to setup employee account. Please correct the errors."
            )

    else:
        form = AccountSetupForm()

    # Go back home if they're already logged in -> means they're account is setup (dont need to actually check)
    user_id = request.session.get("user_id")
    if user_id:
        return redirect("home")

    return render(request, "auth_app/account_setup.html", {"form": form})


@ensure_csrf_cookie
@require_http_methods(["GET", "POST"])
def manual_clocking(request):
    if request.method == "POST":
        form = ManualClockingForm(request.POST)

        if form.is_valid():
            store_pin = form.cleaned_data.get("store_pin")
            employee_pin = form.cleaned_data.get("employee_pin")
            deliveries = form.cleaned_data.get("deliveries")
            latitude = form.cleaned_data.get("latitude")
            longitude = form.cleaned_data.get("longitude")

            # Ensure a value is returned
            if deliveries is None:
                deliveries = 0

            # Get user and store
            try:
                user = User.objects.get(pin=employee_pin)
                store = Store.objects.get(store_pin=store_pin)
            except (User.DoesNotExist, Store.DoesNotExist):
                messages.error(request, "Invalid PIN combination.")
                return render(request, "auth_app/manual_clocking.html", {"form": form})

            # Ensure user is assigned to the store
            if not user.is_associated_with_store(store=store):
                messages.error(
                    request, "The employee is not associated with the store."
                )
                return render(request, "auth_app/manual_clocking.html", {"form": form})

            # Ensure user is within range of the store's acceptable range
            dist = get_distance_from_lat_lon_in_m(
                lat1=store.location_latitude,
                lon1=store.location_longitude,
                lat2=latitude,
                lon2=longitude,
            )
            if dist > store.allowable_clocking_dist_m:
                messages.error(request, "Cannot clock in/out too far from the store.")
                return render(request, "auth_app/manual_clocking.html", {"form": form})

            # Clock the user in/out
            try:
                if user.is_clocked_in(store=store):
                    activity = handle_clock_out(
                        employee_id=user.id,
                        deliveries=deliveries,
                        store_id=store.id,
                        manual=True,
                    )
                    messages.success(request, "Successfully clocked out.")
                else:
                    activity = handle_clock_in(
                        employee_id=user.id, store_id=store.id, manual=True
                    )
                    messages.success(request, "Successfully clocked in.")
            except err.NotAssociatedWithStoreError:
                messages.error(
                    request, "Cannot clock in/out to a non-associated store."
                )
                return render(request, "auth_app/manual_clocking.html", {"form": form})
            except err.InactiveUserError:
                messages.error(request, "Cannot clock in/out an inactive account.")
                return render(request, "auth_app/manual_clocking.html", {"form": form})
            except err.StartingShiftTooSoonError:
                messages.error(request, "Cannot clock in too soon after clocking out.")
                return render(request, "auth_app/manual_clocking.html", {"form": form})
            except err.ClockingOutTooSoonError:
                messages.error(request, "Cannot clock out too soon after clocking in.")
                return render(request, "auth_app/manual_clocking.html", {"form": form})
            except err.InactiveStoreError:
                messages.error(request, "Cannot clock in/out to an inactive store.")
                return render(request, "auth_app/manual_clocking.html", {"form": form})
            except err.NoActiveClockingRecordError:
                messages.error(
                    request,
                    "Could not clock out user due to bugged user state. State has been reset, please retry.",
                )
                return render(request, "auth_app/manual_clocking.html", {"form": form})
            except Exception as e:
                logger.warning(
                    f"Failed to manually clock in/out employee with PIN {employee_pin} (ID: {user.id}) for store PIN {store_pin} (Code: {store.code}) due to the error: {e}"
                )
                messages.error(
                    request,
                    "Could not manually clock in/out user due to internal errors. Please retry.",
                )
                return render(request, "auth_app/manual_clocking.html", {"form": form})

            # Reset the form
            return render(
                request,
                "auth_app/manual_clocking.html",
                {"form": ManualClockingForm(), "activity": activity},
            )

        else:
            messages.error(
                request, "Failed to clock in/out. Please correct the errors."
            )

    # GET REQUEST (load the page)
    else:
        form = ManualClockingForm()

    return render(request, "auth_app/manual_clocking.html", {"form": form})


@employee_required
@ensure_csrf_cookie
@require_GET
def employee_dashboard(request):
    associated_stores = None
    try:
        associated_stores = get_user_associated_stores_from_session(request=request)
    except User.DoesNotExist:
        logger.critical(
            "Failed to load user ID {}'s associated stores. Flushed their session.".format(
                request.session.get("user_id", None)
            )
        )
        messages.error(
            request,
            "Failed to get your account's associated stores. Your session has been reset. Contact an admin for support.",
        )

    user_id = request.session.get("user_id", None)
    user = User.objects.get(id=user_id)
    info = {
        "user_first_name": user.first_name,
        "user_last_name": user.last_name,
        "user_is_hidden": user.is_hidden,
        "user_is_manager": user.is_manager,
        "user_associated_store_count": len(user.get_associated_stores()),
        "user_pin": user.pin,
        "user_email": user.email,
        "user_phone": user.phone_number or None,
        "user_dob": user.birth_date.strftime("%d/%m/%Y") if user.birth_date else None,
        "user_creation_date": (
            user.created_at.strftime("%d/%m/%Y") if user.created_at else None
        ),
        "user_updated_date": (
            user.updated_at.strftime("%d/%m/%Y") if user.updated_at else None
        ),
        "associated_stores": associated_stores,
    }

    return render(request, "auth_app/employee_dashboard.html", info)


@employee_required
@ensure_csrf_cookie
@require_http_methods(["GET", "POST"])
def notification_page(request):
    try:
        context, user = get_default_page_context(request)
    except User.DoesNotExist:
        logger.critical(
            "Failed to load user ID {}'s associated stores. Flushed their session.".format(
                request.session.get("user_id", None)
            )
        )
        messages.error(
            request,
            "Failed to get your account's associated stores. Your session has been reset. Contact an admin for support.",
        )
        return redirect("home")

    # POST REQUEST (form submission)
    if request.method == "POST":
        form = NotificationForm(request.POST, user=user)

        if form.is_valid():
            data = form.cleaned_data
            title = data["title"]
            message = data["message"]
            store = data.get("store")  # .get() as its optional
            recipient_group = data["recipient_group"]
            notification_type = data["notification_type"]

            if recipient_group == "all_users" and user.is_hidden:
                Notification.send_system_notification_to_all(
                    title=title, message=message, sender=user
                )

            elif recipient_group == "store_employees" and user.is_manager:
                Notification.send_to_store_users(
                    store=store,
                    title=title,
                    message=message,
                    notification_type=notification_type,
                    sender=user,
                )

            elif recipient_group == "store_managers":
                managers = store.get_store_managers()
                Notification.send_to_users(
                    users=managers,
                    title=title,
                    message=message,
                    notification_type=notification_type,
                    sender=user,
                )

            elif recipient_group == "site_admins":
                admins = User.objects.filter(is_active=True, is_hidden=True).distinct()
                Notification.send_to_users(
                    users=admins,
                    title=title,
                    message=message,
                    notification_type=notification_type,
                    sender=user,
                )

            else:
                messages.error(
                    request, "Failed to send notifications. Are you authorised?"
                )

            messages.success(request, "Successfully sent notifications.")
            return redirect("notification_page")

        else:
            messages.error(
                request, "Failed to send notifications. Please correct the errors."
            )

    # GET REQUEST (load the page)
    else:
        form = NotificationForm(user=user)
        logger.critical(context["notifications"])

    # Add the form to the context
    context["form"] = form

    return render(request, "auth_app/notification_page.html", context)


@ensure_csrf_cookie
@require_GET
def home_directory(request):
    return render(request, "auth_app/home_directory.html")


@manager_required
@ensure_csrf_cookie
@require_GET
def manager_dashboard(request):
    return render(request, "auth_app/manager_dashboard.html")


@manager_required
@ensure_csrf_cookie
@require_GET
def manage_employee_details(request):
    associated_stores = None
    try:
        associated_stores = get_user_associated_stores_from_session(request=request)
    except User.DoesNotExist:
        logger.critical(
            "Failed to load user ID {}'s associated stores. Flushed their session.".format(
                request.session.get("user_id", None)
            )
        )
        messages.error(
            request,
            "Failed to get your account's associated stores. Your session has been reset. Contact an admin for support.",
        )

    return render(
        request,
        "auth_app/manage_employee_details.html",
        {"associated_stores": associated_stores},
    )


@manager_required
@ensure_csrf_cookie
@require_GET
def manage_shift_logs(request):
    associated_stores = None
    try:
        associated_stores = get_user_associated_stores_from_session(request=request)
    except User.DoesNotExist:
        logger.critical(
            "Failed to load user ID {}'s associated stores. Flushed their session.".format(
                request.session.get("user_id", None)
            )
        )
        messages.error(
            request,
            "Failed to get your account's associated stores. Your session has been reset. Contact an admin for support.",
        )

    return render(
        request, "auth_app/shift_logs.html", {"associated_stores": associated_stores}
    )


@manager_required
@ensure_csrf_cookie
@require_GET
def manage_account_summary(request):
    associated_stores = None
    try:
        associated_stores = get_user_associated_stores_from_session(request=request)
    except User.DoesNotExist:
        logger.critical(
            "Failed to load user ID {}'s associated stores. Flushed their session.".format(
                request.session.get("user_id", None)
            )
        )
        messages.error(
            request,
            "Failed to get your account's associated stores. Your session has been reset. Contact an admin for support.",
        )

    return render(
        request,
        "auth_app/account_summary.html",
        {"associated_stores": associated_stores},
    )


@require_GET
def offline(request):
    return render(request, "offline.html")


@require_GET
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def service_worker(request):
    context = {
        "STATIC_CACHE_VER": STATIC_CACHE_VER,
        "BASE_URL": BASE_URL,
        "STATIC_URL": STATIC_URL,
        "OFFLINE_URL": reverse("offline"),
    }

    return TemplateResponse(
        request, "sw.js", context, content_type="application/javascript"
    )


@require_GET
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def manifest(request):
    context = {
        "BASE_URL": BASE_URL,
        "STATIC_URL": STATIC_URL,
        "OFFLINE_URL": reverse("offline"),
    }

    return TemplateResponse(
        request, "manifest.json", context, content_type="application/manifest+json"
    )


@require_GET
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def robots(request):
    context = {"BASE_URL": BASE_URL, "SITEMAP_URL": reverse("sitemap")}

    return TemplateResponse(request, "robots.txt", context, content_type="text/plain")


class StaticViewSitemap(Sitemap):
    changefreq = "weekly"

    def items(self):
        return ["home", "manual_clocking", "login"]

    def location(self, item):
        return reverse(item)

    def priority(self, item):
        if item == "home":
            return 1.0
        elif item == "login":
            return 0.3
        elif item == "manual_clocking":
            return 0.7
        return 0.5
