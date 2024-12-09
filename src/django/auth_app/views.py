from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from auth_app.models import User, Activity
from django.db import IntegrityError
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required, user_passes_test


def login_view(request):
    return render(request, "auth_app/login.html")


def manager_login(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")
        user = authenticate(request, username=email, password=password)

        if user is not None and user.is_superuser:  # Check if the user is a superuser
            login(request, user)
            return redirect("manager_dashboard")
        else:
            messages.error(request, "Invalid credentials or insufficient permissions.")
    return render(request, "auth_app/manager_login.html")  # Render the login page


@login_required
@user_passes_test(lambda user: user.is_superuser)
def manager_dashboard(request):
    # Render the manager dashboard directly
    return render(request, "auth_app/manager_dashboard.html")


def employee_login(request):
    # Redirect to employee page (skip login for now)
    return redirect("employee_dashboard")


def employee_dashboard(request):
    # Render employee dashboard
    return render(request, "auth_app/employee_dashboard.html")
