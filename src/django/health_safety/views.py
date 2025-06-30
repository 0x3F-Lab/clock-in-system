import logging
import api.exceptions as err

from rest_framework import status
from django.urls import reverse
from django.contrib import messages
from django.shortcuts import render, redirect
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods
from auth_app.models import User
from auth_app.utils import (
    manager_required,
    employee_required,
    get_default_page_context,
)


logger = logging.getLogger("health_safety")


@employee_required
@ensure_csrf_cookie
@require_GET
def employee_health_dashboard(request):
    try:
        context, user = get_default_page_context(request)
    except User.DoesNotExist:
        logger.critical(
            "Failed to load user ID {}'s associated stores. Flushed their session.".format(
                request.session.get("user_id", None)
            )
        )
        messages.error(
            request,
            "Failed to get your account's associated stores. Your session has been reset. Contact an admin for support.",
        )
        return redirect("home")

    return render(request, "health_safety/health_safety_dash.html", context)


@manager_required
@ensure_csrf_cookie
@require_GET
def manager_health_dashboard(request):
    try:
        context, user = get_default_page_context(request)
    except User.DoesNotExist:
        logger.critical(
            "Failed to load user ID {}'s associated stores. Flushed their session.".format(
                request.session.get("user_id", None)
            )
        )
        messages.error(
            request,
            "Failed to get your account's associated stores. Your session has been reset. Contact an admin for support.",
        )
        return redirect("home")

    return render(request, "health_safety/health_safety_manager_dash.html", context)
