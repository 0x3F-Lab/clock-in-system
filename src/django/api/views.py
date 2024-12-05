import logging
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import api.controllers as controllers


logger = logging.getLogger("api")


@api_view(["GET"])
def list_users_name_view(request):
    """
    API view to fetch a list of users with their IDs and full names.
    """
    try:
        # Extract query parameters from the request, with defaults
        only_active = request.query_params.get("only_active", "true").lower() == "true"
        ignore_managers = (
            request.query_params.get("ignore_managers", "false").lower() == "true"
        )
        order = request.query_params.get("order", "true").lower() == "true"
        order_by_first_name = (
            request.query_params.get("order_by_first_name", "true").lower() == "true"
        )
        ignore_clocked_in = (
            request.query_params.get("ignore_clocked_in", "false").lower() == "true"
        )

        # Call the controller function
        users_list = controllers.list_users_name(
            only_active=only_active,
            ignore_managers=ignore_managers,
            order=order,
            order_by_first_name=order_by_first_name,
            ignore_clocked_in=ignore_clocked_in,
        )

        if users_list is None:
            # If no users are found, return 404 not found
            return Response(
                {"Error": "No users found matching the given criteria."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Return the list of users in the response
        return Response(users_list, status=status.HTTP_200_OK)

    except Exception as e:
        # Handle any unexpected exceptions
        logger.error(f"Failed to list all users, resulting in the error: {str(e)}")
        return Response(
            {"Error": "Internal error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


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
