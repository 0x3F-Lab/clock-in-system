from functools import wraps
from django.shortcuts import redirect


# def manager_required(view_func):
#     """
#     Decorator to ensure the user is an authenticated manager.
#     """

#     @wraps(view_func)
#     def _wrapped_view(request, *args, **kwargs):
#         user_id = request.session.get("user_id")
#         is_manager = request.session.get("is_manager", False)
#         print(f"Decorator check: user_id={user_id}, is_manager={is_manager}")  # Debug

#         if not user_id or not is_manager:
#             return redirect("manager_login")  # Redirect to login if not a manager
#         return view_func(request, *args, **kwargs)

#     return _wrapped_view


def manager_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # Check if the user is authenticated
        if not request.user.is_authenticated:
            return redirect("manager_login")  # Redirect to manager login page

        # Check if the user is a manager
        if not hasattr(request.user, "is_manager") or not request.user.is_manager:
            return redirect("manager_login")  # Redirect if not a manager

        return view_func(request, *args, **kwargs)

    return _wrapped_view
