import logging
from auth_app.models import User, Store, StoreUserAccess
from auth_app.utils import manager_required, employee_required
from auth_app.forms import LoginForm, ManualClockingForm
from api.controllers import handle_clock_in, handle_clock_out
from api.utils import get_distance_from_lat_lon_in_m
import api.exceptions as err
from django.contrib import messages
from django.shortcuts import render, redirect
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods

logger = logging.getLogger("auth_app")


@require_http_methods(["GET", "POST"])
def manager_login(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        try:
            user = User.objects.get(email=email)  # Look up the user by email
        except User.DoesNotExist:
            messages.error(request, "Invalid details.")
            return render(request, "auth_app/manager_login.html")

        # Check password and if the user is a manager
        if user.check_password(password) and user.is_manager:
            # Log the user in by setting session data
            request.session["user_id"] = user.id
            request.session["is_manager"] = user.is_manager
            return redirect("manager_dashboard")
        else:
            messages.error(request, "Invalid Details")

    return render(request, "auth_app/manager_login.html")


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

            try:
                user = User.objects.get(email=email)  # Look up the user by email
            except User.DoesNotExist:
                messages.error(request, "Invalid credentials.")
                return render(request, "auth_app/login.html", {"form": form})

            # Check password
            if user.check_password(password):
                # Log the user in by setting session data
                request.session["user_id"] = user.id
                request.session["is_manager"] = user.is_manager
                request.session["name"] = user.first_name

                next_url = request.POST.get("next", None) or request.GET.get(
                    "next", None
                )
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
                        employee_id=user.id, deliveries=deliveries, store_id=store.id
                    )
                    messages.success(request, "Successfully clocked out.")
                else:
                    activity = handle_clock_in(employee_id=user.id, store_id=store.id)
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

    else:
        form = ManualClockingForm()

    return render(request, "auth_app/manual_clocking.html", {"form": form})


@employee_required
@ensure_csrf_cookie
@require_http_methods(["GET", "POST"])
def employee_dashboard(request):
    return render(request, "auth_app/employee_dashboard.html")


@ensure_csrf_cookie
@require_GET
def home_directory(request):
    return render(request, "auth_app/home_directory.html")


@manager_required
@ensure_csrf_cookie
@require_GET
def manager_dashboard(request):
    user_id = request.session.get("user_id")
    user = User.objects.get(id=user_id)  # Retrieve the logged-in user's details
    return render(request, "auth_app/manager_dashboard.html", {"user": user})


@manager_required
@ensure_csrf_cookie
@require_GET
def manage_employee_details(request):
    return render(request, "auth_app/manage_employee_details.html")


@manager_required
@ensure_csrf_cookie
@require_GET
def manage_shift_logs(request):
    return render(request, "auth_app/shift_logs.html")
