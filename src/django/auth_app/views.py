import logging
from django.shortcuts import render, redirect
from auth_app.models import User, Activity
from django.db import IntegrityError
from django.contrib import messages
from auth_app.utils import manager_required
from django.contrib.auth.decorators import login_required

logger = logging.getLogger("auth_app")


def login_view(request):
    return render(request, "auth_app/login.html")


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


def logout_view(request):
    request.session.flush()  # Clear all session data
    return redirect("/")


# @manager_required
def manager_dashboard(request):
    user_id = request.session.get("user_id")
    user = User.objects.get(id=user_id)  # Retrieve the logged-in user's details
    return render(request, "auth_app/manager_dashboard.html", {"user": user})


def employee_login(request):
    # Redirect to employee page (skip login for now)
    return redirect("employee_dashboard")


def employee_dashboard(request):
    # Render employee dashboard
    return render(request, "auth_app/employee_dashboard.html")
