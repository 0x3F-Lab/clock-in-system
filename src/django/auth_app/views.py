from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.utils.timezone import now
from django.shortcuts import render, redirect
from .models import User, Activity
from .serializers import ActivitySerializer
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


@api_view(["POST"])
def clock_in(request):
    user_id = request.data.get("user_id")
    try:
        user = User.objects.get(id=user_id)

        # Ensure user is not already clocked in
        if user.clocked_in:
            return Response(
                {"error": "User is already clocked in."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Mark user as clocked in and create a new Activity
        user.clocked_in = True
        user.save()

        activity = Activity.objects.create(
            employee_id=user,
            login_time=now(),
        )
        return Response(
            ActivitySerializer(activity).data, status=status.HTTP_201_CREATED
        )

    except User.DoesNotExist:
        return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)


@api_view(["POST"])
def clock_out(request):
    user_id = request.data.get("user_id")
    try:
        user = User.objects.get(id=user_id)

        # Ensure user is clocked in
        if not user.clocked_in:
            return Response(
                {"error": "User is not clocked in."}, status=status.HTTP_400_BAD_REQUEST
            )

        # Find the user's last activity
        activity = Activity.objects.filter(
            employee_id=user, logout_time__isnull=True
        ).last()
        if not activity:
            return Response(
                {"error": "No active clock-in record found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Mark user as clocked out and update the Activity
        user.clocked_in = False
        user.save()

        activity.logout_time = now()
        activity.save()

        return Response(ActivitySerializer(activity).data, status=status.HTTP_200_OK)

    except User.DoesNotExist:
        return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)
