"""
TACAI Shared API Response Utilities
===================================
Standardised JSON response helpers for all TACAI Python standard-library modules.
Ensures consistent API response format across all backend services.

Response format:
    Success:        {"success": true, "data": ...}
    Paginated list: {"success": true, "data": [...], "pagination": {...}}
    Error:          {"success": false, "error": "...", "errors": [...]}

Usage (in each module's app.py):

    from api_utils import (
        send_json, success, error, paginated,
        parse_json_body, get_query_params, get_query_param,
    )

    class MyHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            params = get_query_params(self)
            page = int(params.get("page", "1"))
            page_size = int(params.get("page_size", "20"))
            # ...
            paginated(self, data, page, page_size, total)

        def do_POST(self):
            body = parse_json_body(self)
            if not body:
                return error(self, "Invalid JSON", 400)
            # ...
            success(self, {"id": new_id}, 201)
"""

from __future__ import annotations

import json
from http import HTTPStatus
from typing import Any
from urllib.parse import parse_qs, urlparse


# ── Core JSON response sender ────────────────────────────────

def send_json(handler, payload: dict, status: int = 200) -> None:
    """Send a JSON response with standard headers (CORS + security)."""
    from cors_middleware import add_cors_headers
    body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    handler.send_response(status)
    add_cors_headers(handler)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


# ── Success responses ─────────────────────────────────────────

def success(handler, data: Any = None, status: int = 200) -> None:
    """Send a standard success response."""
    payload: dict = {"success": True}
    if data is not None:
        payload["data"] = data
    send_json(handler, payload, status)


def paginated(handler, data: list, page: int, page_size: int, total: int, total_all: int | None = None, filtered: bool | None = None) -> None:
    """Send a standard paginated list response."""
    payload = {
        "success": True,
        "data": data,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
        },
    }
    if total_all is not None:
        payload["pagination"]["total_all"] = total_all
    if filtered is not None:
        payload["pagination"]["filtered"] = filtered
    send_json(handler, payload, 200)


# ── Error responses ───────────────────────────────────────────

def error(handler, message: str, status: int = 400, errors: list[str] | None = None) -> None:
    """Send a standard error response."""
    payload: dict = {"success": False, "error": message}
    if errors:
        payload["errors"] = errors
    send_json(handler, payload, status)


def not_found(handler, message: str = "Resource not found") -> None:
    """Send a 404 not-found response."""
    error(handler, message, 404)


def unauthorized(handler, message: str = "Authentication required") -> None:
    """Send a 401 unauthorized response."""
    error(handler, message, 401)


def forbidden(handler, message: str = "Permission denied") -> None:
    """Send a 403 forbidden response."""
    error(handler, message, 403)


def bad_request(handler, message: str = "Bad request", errors: list[str] | None = None) -> None:
    """Send a 400 bad-request response."""
    error(handler, message, 400, errors)


def server_error(handler, message: str = "Internal server error") -> None:
    """Send a 500 internal-server-error response."""
    error(handler, message, 500)


# ── Request parsing helpers ───────────────────────────────────

def parse_json_body(handler, max_bytes: int | None = None) -> dict | None:
    """Parse JSON request body. Returns None on failure.

    Args:
        handler: The HTTP request handler instance.
        max_bytes: Maximum allowed body size in bytes (default: 2MB).
                   Set to 0 for no limit (import endpoints, etc.).
    """
    if max_bytes is None:
        max_bytes = 2 * 1024 * 1024  # 2MB default
    try:
        content_length = int(handler.headers.get("Content-Length", "0"))
        if content_length == 0:
            return {}
        if max_bytes > 0 and content_length > max_bytes:
            return None  # Rejected — body too large
        raw = handler.rfile.read(content_length)
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError, OSError):
        return None


def get_query_params(handler) -> dict[str, list[str]]:
    """Parse query string parameters. Returns {key: [values]} dict."""
    parsed = urlparse(handler.path)
    return parse_qs(parsed.query)


def get_query_param(handler, key: str, default: str = "") -> str:
    """Get a single query parameter value."""
    parsed = urlparse(handler.path)
    params = parse_qs(parsed.query)
    values = params.get(key, [])
    return values[0] if values else default
