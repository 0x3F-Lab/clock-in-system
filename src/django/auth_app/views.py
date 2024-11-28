from django.shortcuts import render, redirect
from .models import User
from .forms import NewUserForm
from django.db import IntegrityError


def login_view(request):
    return render(request, "auth_app/login.html")


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
