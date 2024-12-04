from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.utils.timezone import now
from django.shortcuts import render, redirect
from auth_app.models import User, Activity
from auth_app.serializers import ActivitySerializer


@api_view(["POST"])
def clock_in(request):
    employee_id = request.data.get("employee_id")
    try:
        employee = User.objects.get(id=employee_id)

        # Ensure employee is not already clocked in
        if employee.clocked_in:
            return Response(
                {"error": "Employee is already clocked in."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Mark employee as clocked in and create a new Activity
        employee.clocked_in = True
        employee.save()

        activity = Activity.objects.create(
            employee_id=employee,
            login_time=now(),
        )
        return Response(
            ActivitySerializer(activity).data, status=status.HTTP_201_CREATED
        )

    except User.DoesNotExist:
        return Response(
            {"error": "Employee not found."}, status=status.HTTP_404_NOT_FOUND
        )


@api_view(["POST"])
def clock_out(request):
    employee_id = request.data.get("employee_id")
    try:
        employee = User.objects.get(id=employee_id)

        # Ensure employee is clocked in
        if not employee.clocked_in:
            return Response(
                {"error": "Employee is not clocked in."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Find the employee's last activity
        activity = Activity.objects.filter(
            employee_id=employee, logout_time__isnull=True
        ).last()
        if not activity:
            return Response(
                {"error": "No active clock-in record found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Mark employee as clocked out and update the Activity
        employee.clocked_in = False
        employee.save()

        activity.logout_time = now()
        activity.save()

        return Response(ActivitySerializer(activity).data, status=status.HTTP_200_OK)

    except User.DoesNotExist:
        return Response(
            {"error": "Employee not found."}, status=status.HTTP_404_NOT_FOUND
        )
