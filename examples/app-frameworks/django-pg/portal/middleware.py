from django.conf import settings
from django.db import DatabaseError, connection
from django.http import JsonResponse
class PortalMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    def __call__(self, request):
        if request.method not in ("GET", "HEAD") and request.headers.get("Origin") != settings.APP_ORIGIN:
            response = JsonResponse({"error": "origin refused"}, status=403)
        else:
            response = self.get_response(request)
        response["Cache-Control"] = "no-store"
        response["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self'; base-uri 'none'; frame-ancestors 'none'"
        return response
    def process_exception(self, request, exception):
        if isinstance(exception, DatabaseError):
            connection.close()
            return JsonResponse({"error": "database unavailable; check saved data before retrying"}, status=503)
