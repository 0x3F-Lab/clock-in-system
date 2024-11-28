from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required


def login_view(request):
    return render(request, "auth_app/login.html")


def manager_login(request):
    # Redirect directly to the manager dashboard without authentication
    return redirect("manager_dashboard")


def manager_dashboard(request):
    # Render the manager dashboard directly
    return render(request, "auth_app/manager_dashboard.html")


def employee_login(request):
    # Redirect to employee page (skip login for now)
    return redirect("employee_dashboard")


def employee_dashboard(request):
    # Render employee dashboard
    return render(request, "auth_app/employee_dashboard.html")
