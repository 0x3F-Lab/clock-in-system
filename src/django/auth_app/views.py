import logging
from auth_app.models import User
from auth_app.utils import manager_required
from django.contrib import messages
from django.shortcuts import render, redirect
from django.conf.urls import handler404
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods

logger = logging.getLogger("auth_app")


def page_not_found(request, exception):
    return render(request, "auth_app/404.html", status=404)


@require_http_methods(["GET", "POST"])
def manager_login(request):
    logger.debug(f"manager login user: {request.user}")
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
            logger
            return redirect("manager_dashboard")
        else:
            messages.error(request, "Invalid Details")

    return render(request, "auth_app/manager_login.html")


@require_GET
def logout_view(request):
    request.session.flush()  # Clear all session data
    return redirect("/")


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


# Set custom error page (page not found)
handler404 = page_not_found
