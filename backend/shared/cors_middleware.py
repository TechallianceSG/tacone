"""
TACAI Shared CORS Middleware
============================
Drop-in CORS support for TACAI Python standard-library modules.

With the API Gateway pattern, Portal (:3000) is the single entry point.
Only Portal and the Vite dev server need CORS headers; internal services
are accessed exclusively by Portal via localhost.

Usage:

    from cors_middleware import add_cors_headers, handle_preflight

    class MyHandler(BaseHTTPRequestHandler):

        def do_OPTIONS(self):
            handle_preflight(self)

        def send_response(self, status):
            super().send_response(status)
            add_cors_headers(self)
"""

from http import HTTPStatus

# Allowed origins — Portal (gateway) + Vite dev server
ALLOWED_ORIGINS = {
    # Vite dev server
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    # Vite preview
    "http://localhost:4173",
    "http://127.0.0.1:4173",
    # Portal (serves built SPA in production)
    "http://localhost:3000",
    "http://127.0.0.1:3000",
}

# Add LAN IP origins if configured
import os as _os
_TACAI_PUBLIC_HOST = _os.environ.get("TACAI_PUBLIC_HOST", "").strip()
if _TACAI_PUBLIC_HOST and _TACAI_PUBLIC_HOST not in {"127.0.0.1", "localhost"}:
    ALLOWED_ORIGINS.add(f"http://{_TACAI_PUBLIC_HOST}:5173")
    ALLOWED_ORIGINS.add(f"http://{_TACAI_PUBLIC_HOST}:3000")


def add_cors_headers(handler) -> None:
    """Add CORS headers to the current response.
    Call this AFTER send_response() but BEFORE end_headers().
    """
    origin = handler.headers.get("Origin", "")
    allowed = origin if origin in ALLOWED_ORIGINS else (
        "http://localhost:5173"  # default
    )

    handler.send_header("Access-Control-Allow-Origin", allowed)
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, PATCH, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")
    handler.send_header("Access-Control-Allow-Credentials", "true")
    handler.send_header("Access-Control-Max-Age", "86400")


def handle_preflight(handler) -> None:
    """Handle OPTIONS preflight request.
    Call this at the top of do_OPTIONS().
    """
    handler.send_response(HTTPStatus.NO_CONTENT)
    add_cors_headers(handler)
    handler.end_headers()
