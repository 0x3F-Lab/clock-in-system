from functools import wraps
from django.shortcuts import redirect
from django.http import JsonResponse
from rest_framework import status


def manager_required(view_func):
    """
    Decorator to ensure the user is an authenticated manager.
    """

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        user_id = request.session.get("user_id")
        is_manager = request.session.get("is_manager", False)
        if not user_id or not is_manager:
            return redirect("manager_login")  # Redirect to login if not a manager
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def api_manager_required(view_func):
    """
    Decorator to ensure the user is an authenticated manager.
    DOES NOT REDIRECT USER IF NOT AUTHENTICATED.
    """

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        user_id = request.session.get("user_id")
        is_manager = request.session.get("is_manager", False)
        if not user_id or not is_manager:
            return JsonResponse(
                {"Error": "You do not have permission to access this resource."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return view_func(request, *args, **kwargs)

    return _wrapped_view
