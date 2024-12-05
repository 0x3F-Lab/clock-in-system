from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import api.controllers as controllers


@api_view(["POST"])
def clock_in(request):
    employee_id = request.data.get("employee_id", None)

    # Check for invalid ID first
    if employee_id is None:
        return Response(
            {"Error": "Employee ID not provided."}, status=status.HTTP_400_BAD_REQUEST
        )

    # Delegate to the controller function
    return controllers.handle_clock_in(employee_id)


@api_view(["POST"])
def clock_out(request):
    employee_id = request.data.get("employee_id", None)
    deliveries = max(
        int(request.data.get("deliveries", 0)), 0
    )  # Ensure it's an integer and above 0

    # Check for invalid ID first
    if employee_id is None:
        return Response(
            {"Error": "Employee ID not provided."}, status=status.HTTP_400_BAD_REQUEST
        )

    # Delegate to the controller function
    return controllers.handle_clock_out(employee_id, deliveries)
