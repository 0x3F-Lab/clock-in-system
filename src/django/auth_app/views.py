import logging
from auth_app.models import User
from auth_app.utils import manager_required, employee_required
from auth_app.forms import LoginForm
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

            # Check password and if the user is a manager
            if user.check_password(password) and user.is_manager:
                # Log the user in by setting session data
                request.session["user_id"] = user.id
                request.session["is_manager"] = user.is_manager
                request.session["name"] = user.first_name

                next_url = request.GET.get("next") or request.POST.get("next")
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


@employee_required
@ensure_csrf_cookie
@require_http_methods(["GET", "POST"])
def dashboard(request):
    return render(request, "auth_app/employee_dashboard_v2.html")


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


@ensure_csrf_cookie
@require_GET
def employee_dashboard(request):
    # Render employee dashboard
    return render(request, "auth_app/employee_dashboard.html")


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
