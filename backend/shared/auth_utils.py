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
import time as _time
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

# Session cache TTL (seconds) — avoids redundant user_admin round-trips
SESSION_CACHE_TTL = int(os.environ.get("SESSION_CACHE_TTL", "30"))

# Circuit breaker: after N consecutive failures, short-circuit for M seconds
CIRCUIT_BREAKER_THRESHOLD = int(os.environ.get("AUTH_CB_THRESHOLD", "5"))
CIRCUIT_BREAKER_TIMEOUT = int(os.environ.get("AUTH_CB_TIMEOUT", "15"))


# ── Circuit breaker ──────────────────────────────────────────────────────

class _CircuitBreaker:
    """Simple circuit breaker: after threshold consecutive failures, open for timeout seconds.

    When open, validate_session() uses cached entries (even slightly stale ones)
    rather than failing all requests with 401.
    """

    def __init__(self, threshold: int = 5, timeout: int = 15):
        self._threshold = threshold
        self._timeout = timeout
        self._failures = 0
        self._last_failure_time = 0.0
        self._lock = None

    def _ensure_lock(self):
        if self._lock is None:
            import threading as _thr
            self._lock = _thr.Lock()

    @property
    def is_open(self) -> bool:
        self._ensure_lock()
        with self._lock:
            if self._failures < self._threshold:
                return False
            if _time.monotonic() - self._last_failure_time > self._timeout:
                # Half-open: allow one probe request
                self._failures = self._threshold - 1
                return False
            return True

    def record_success(self) -> None:
        self._ensure_lock()
        with self._lock:
            self._failures = 0

    def record_failure(self) -> None:
        self._ensure_lock()
        with self._lock:
            self._failures += 1
            self._last_failure_time = _time.monotonic()


_circuit_breaker = _CircuitBreaker(
    threshold=CIRCUIT_BREAKER_THRESHOLD,
    timeout=CIRCUIT_BREAKER_TIMEOUT,
)


# ── In-memory session cache ───────────────────────────────────────────────

class _SessionCache:
    """Thread-safe TTL cache for validated session user dicts.

    Reduces user_admin load by caching validation results for a short TTL.
    A dashboard loading 5 widgets with the same session cookie makes 1 HTTP
    call to user_admin instead of 5.
    """

    def __init__(self, ttl: int = 30):
        self._ttl = ttl
        self._store: dict[str, tuple[float, dict[str, Any]]] = {}
        self._lock = None  # lazy init for fork-safety

    def _ensure_lock(self):
        if self._lock is None:
            import threading as _thr
            self._lock = _thr.Lock()

    def get(self, session_id: str) -> dict[str, Any] | None:
        self._ensure_lock()
        with self._lock:
            entry = self._store.get(session_id)
            if entry is None:
                return None
            ts, user = entry
            if _time.monotonic() - ts > self._ttl:
                del self._store[session_id]
                return None
            return dict(user)  # shallow copy for caller safety

    def set(self, session_id: str, user: dict[str, Any]) -> None:
        self._ensure_lock()
        with self._lock:
            self._store[session_id] = (_time.monotonic(), dict(user))
            # Prune expired entries when cache grows beyond threshold
            if len(self._store) > 500:
                self._prune()

    def invalidate(self, session_id: str) -> None:
        self._ensure_lock()
        with self._lock:
            self._store.pop(session_id, None)

    def _prune(self) -> None:
        now = _time.monotonic()
        expired = [k for k, (ts, _) in self._store.items() if now - ts > self._ttl]
        for k in expired:
            del self._store[k]


_cache = _SessionCache(ttl=SESSION_CACHE_TTL)


def invalidate_session_cache(session_id: str) -> None:
    """Invalidate a cached session (call on logout / admin session kill)."""
    _cache.invalidate(session_id)


# ── Public API ──────────────────────────────────────────────────────────────

def validate_session(
    cookie_header: str | None = None,
    *,
    session_id: str | None = None,
) -> dict[str, Any] | None:
    """Validate a session against user_admin, with in-memory caching.

    Accepts either a raw Cookie header string OR an explicit session_id.
    Returns the ``user`` dict (with roles & permissions already resolved) on
    success, or ``None`` if the session is invalid / expired / missing.

    Cached for SESSION_CACHE_TTL seconds (default 30) to avoid redundant
    HTTP round-trips to user_admin for burst requests from the same session.

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

    # ── Check cache first (always) ──
    cached = _cache.get(sid)
    if cached is not None:
        return cached

    # ── Circuit breaker: if user_admin is down, don't pile on ──
    if _circuit_breaker.is_open:
        # Circuit open — user_admin is unhealthy. Cache miss = authentication
        # fails gracefully (single 401) rather than timeout-storming every request.
        return None

    # ── Cache miss + circuit closed → call user_admin ──
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
        _circuit_breaker.record_failure()
        # Fallback: return stale cache entry if available (extend grace window)
        stale = _cache.get(sid)  # may have been pruned already
        return stale

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
        # ── Store in cache + record success ──
        _cache.set(sid, user)
        _circuit_breaker.record_success()
        return user

    # Session explicitly invalid (expired, logged out, etc.) — not a failure
    _circuit_breaker.record_success()
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
