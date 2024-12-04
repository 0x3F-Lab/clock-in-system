from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from auth_app.models import User, Activity
from auth_app.forms import NewUserForm
from django.db import IntegrityError


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


def user_list(request):
    users = User.objects.all()
    return render(request, "auth_app/user_list.html", {"users": users})


def create_user(request):
    if request.method == "POST":
        form = NewUserForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                return redirect("user_list")
            except IntegrityError as e:
                print(f"Database integrity error when adding new user: {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")

    else:
        form = NewUserForm()
    return render(request, "auth_app/create_user.html", {"form": form})
