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
