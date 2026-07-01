#!/usr/bin/env python3
"""Shared authentication utilities for all TACAI backend services.

Every internal service that needs session validation MUST use the single
function `validate_session()` defined here.  Do NOT copy-paste HTTP calls
to user_admin — that leads to inconsistent response parsing and drift.

Usage::

    from auth_utils import validate_session, require_auth

    def do_GET(self):
        user = validate_session(self.headers.get("Cookie", ""))
        if not user:
            self.send_json(401, {"error": "Unauthorized"})
            return
        # … proceed with authenticated user …
"""

from __future__ import annotations

import json
import os
import sys as _sys
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

# ── Configuration ──────────────────────────────────────────────────────────

SESSION_COOKIE = "tacai_session_id"

# User_admin internal base URL — read from env, fall back to 127.0.0.1:3001
_USER_ADMIN_HOST = os.environ.get("TACAI_INTERNAL_HOST", "127.0.0.1").strip() or "127.0.0.1"
_AUTH_PORT = int(os.environ.get("AUTH_PORT", "3001"))
USER_ADMIN_INTERNAL_BASE_URL = os.environ.get(
    "USER_ADMIN_INTERNAL_BASE_URL",
    f"http://{_USER_ADMIN_HOST}:{_AUTH_PORT}"
).rstrip("/")

VALIDATE_SESSION_URL = f"{USER_ADMIN_INTERNAL_BASE_URL}/api/validate-session"
CHECK_PERMISSION_URL = f"{USER_ADMIN_INTERNAL_BASE_URL}/api/check-permission"
REQUEST_TIMEOUT = 5  # seconds — internal service calls should be fast


# ── Public API ──────────────────────────────────────────────────────────────

def validate_session(
    cookie_header: str | None = None,
    *,
    session_id: str | None = None,
) -> dict[str, Any] | None:
    """Validate a session against user_admin.

    Accepts either a raw Cookie header string OR an explicit session_id.
    Returns the ``user`` dict (with roles & permissions already resolved) on
    success, or ``None`` if the session is invalid / expired / missing.

    The returned dict includes these keys added by user_admin:
      - user_id, username, email, display_name, user_type
      - roles: list[str]          (e.g. ['system_admin', 'hr_manager'])
      - permissions: list[str]    (e.g. ['employee_management.access', …])
      - entity: dict              (active entity context)
      - entity_id, entity_code, entity_name
    """
    sid = session_id or _extract_session_id(cookie_header)
    if not sid:
        return None

    try:
        req = Request(
            VALIDATE_SESSION_URL,
            data=json.dumps({"session_id": sid}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (OSError, URLError, json.JSONDecodeError, ValueError):
        return None

    # ══════════════════════════════════════════════════════════════════════
    # Standard response format (from user_admin handle_api_validate_session):
    #   {"valid": bool, "user": {...}|null, "session": {...}|null}
    #
    # The user dict returned by user_context() ALREADY includes:
    #   - resolved roles (via active_user_role_keys)
    #   - resolved permissions (via effective_permissions)
    #   - entity context (entity_id, entity_code, entity_name, entity dict)
    # ══════════════════════════════════════════════════════════════════════
    if data.get("valid") and isinstance(data.get("user"), dict):
        user = data["user"]
        # Attach session metadata for services that need it
        if isinstance(data.get("session"), dict):
            user["_session"] = data["session"]
        return user
    return None


def has_permission(user: dict[str, Any] | None, permission_key: str) -> bool:
    """Check if the given user has a specific permission.

    The user MUST come from ``validate_session()`` — its ``permissions``
    list is already resolved by user_admin.
    """
    if not user:
        return False
    perms: list[str] = user.get("permissions") or []
    return permission_key in perms


def is_system_admin(user: dict[str, Any] | None) -> bool:
    """Check if the user has the system_admin role."""
    if not user:
        return False
    roles: list[str] = user.get("roles") or []
    return "system_admin" in roles


def has_entity_context(user: dict[str, Any] | None) -> bool:
    """Check that the user has an active entity context in their session."""
    if not user:
        return False
    return bool(user.get("entity_id") and user.get("entity_code"))


def current_entity_label(user: dict[str, Any] | None, lang: str = "zh") -> str:
    """Return a human-readable entity label: CODE - Name."""
    if not user:
        return ""
    code = user.get("entity_code", "")
    name = user.get("entity_name", "")
    return f"{code} - {name}" if name else code


# ── Internal helpers ────────────────────────────────────────────────────────

def _extract_session_id(cookie_header: str | None) -> str:
    """Extract tacai_session_id from a raw Cookie header string."""
    if not cookie_header:
        return ""
    cookie = SimpleCookie(cookie_header)
    morsel = cookie.get(SESSION_COOKIE)
    return morsel.value.strip() if morsel and morsel.value else ""
