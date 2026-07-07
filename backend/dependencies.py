"""FastAPI dependency injection — auth, permissions, database.

Replaces auth_utils.py (which made HTTP calls to user_admin).
In the monolith, session validation is a direct function call.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import Cookie, Depends, HTTPException, Request, status


async def get_session_id(
    request: Request,
    tacai_session_id: Optional[str] = Cookie(default=None),
) -> str:
    """Extract session ID from cookie."""
    return tacai_session_id or ""


async def get_optional_user(
    request: Request,
    tacai_session_id: Optional[str] = Cookie(default=None),
) -> dict[str, Any] | None:
    """Like get_current_user, but returns None instead of raising 401.

    Use this for endpoints that work both with and without authentication,
    like /api/auth/session (which tells the SPA whether the user is logged in).
    """
    from modules.auth.service import validate_session_id, user_context as _user_context

    session_id = tacai_session_id or ""
    if not session_id:
        return None
    session, user = validate_session_id(session_id)
    if not user:
        return None
    ctx = _user_context(user, session)
    return ctx if ctx.get("entity_id") else None


async def get_current_user(
    request: Request,
    tacai_session_id: Optional[str] = Cookie(default=None),
) -> dict[str, Any]:
    """Validate session and return user dict with roles & permissions resolved.

    Returns dict with keys: user_id, username, email, display_name, user_type,
    roles (list[str]), permissions (list[str]), entity_id, entity_code, entity_name.
    Raises 401 if session is invalid/expired.
    """
    from modules.auth.service import validate_session_id, user_context as _user_context

    session_id = tacai_session_id or ""
    if not session_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    session, user = validate_session_id(session_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")

    ctx = _user_context(user, session)
    if not ctx.get("entity_id"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Entity context required")
    return ctx


class PermissionChecker:
    """Dependency factory for permission-based access control."""

    def __init__(self, permission: str):
        self._permission = permission

    async def __call__(self, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        from modules.auth.service import effective_permissions

        perms = effective_permissions(str(user.get("user_id", "")))
        roles: list[str] = user.get("roles") or []
        if self._permission not in perms and "system_admin" not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user


def require_permission(permission: str) -> PermissionChecker:
    """FastAPI dependency that checks the user has a specific permission.

    Usage:
        @router.get("/api/something")
        async def handler(user: dict = Depends(require_permission("module.access"))):
            ...
    """
    return PermissionChecker(permission)


async def get_db():
    """Yield a database connection from the pool.

    Not strictly needed since db_utils manages its own pool,
    but provides a consistent pattern for future use.
    """
    from shared import db_utils as _db

    if not _db.require_pg():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")
    yield
