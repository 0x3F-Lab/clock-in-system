import logging
from django.http import JsonResponse
from django.middleware.csrf import CsrfViewMiddleware

logger = logging.getLogger("middleware")


def get_client_ip(request):
    return request.META.get("REMOTE_ADDR")


class SessionExpiryLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Capture whether the session is new or previously existed
        had_session_key = request.session.session_key is not None

        response = self.get_response(request)

        # If they had a session but now it’s gone
        if had_session_key and not request.session.session_key:
            logger.info(
                f"[SESSION] Session expired for user ID {request.session.get('user_id')} ({request.session.get('name')}) >> IP: {get_client_ip(request)}"
            )

        return response


class CustomCSRFMiddleware(CsrfViewMiddleware):
    def _reject(self, request, reason):
        logger.warning(f"[CSRF] CSRF failure: {reason} >> IP: {get_client_ip(request)}")
        return JsonResponse(
            {"Error": "Session expired or CSRF token invalid"}, status=403
        )
