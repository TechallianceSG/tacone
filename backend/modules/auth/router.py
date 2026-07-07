"""Auth module — FastAPI router for authentication, sessions, users, roles, permissions."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from dependencies import PermissionChecker, get_current_user, get_optional_user
from modules.auth.models import (
    ChangePasswordRequest,
    CreateUserRequest,
    UpdateRolePermissionsRequest,
    UpdateUserRequest,
    error_response,
    paginated_response,
    success_response,
)
from modules.auth.service import (
    MAX_FAILED_LOGINS,
    PERMISSION_DEFINITIONS,
    SESSION_TIMEOUT_MINUTES,
    active_user_role_keys,
    append_audit,
    check_login_rate_limit,
    clear_login_rate_limit,
    clear_session_cookie_header,
    dashboard_stats,
    effective_permissions,
    enrich_user_employee_link,
    find_user_by_email,
    find_user_by_id,
    hash_password,
    is_system_admin_user,
    load_audit_logs,
    load_permissions,
    load_roles,
    load_sessions,
    load_user_entity_mappings,
    load_user_role_mappings,
    load_users,
    next_id,
    now_iso,
    password_policy_errors,
    record_login_rate_limit,
    save_role_permission_mappings,
    save_sessions,
    save_user_entity_mappings,
    save_user_role_mappings,
    save_users,
    seed_admin_user,
    seed_roles_and_permissions,
    session_context,
    session_cookie_header,
    user_context,
    user_persistable_data,
    validate_login_entity,
    validate_session_id,
    validate_user_form,
    verify_password,
    would_leave_no_active_system_admin,
)

router = APIRouter()

# ── Startup ──────────────────────────────────────────────────────────────

# Ensure base data exists on first import
try:
    seed_roles_and_permissions()
    seed_admin_user()
except Exception:
    pass  # Tables may not exist yet on very first run


# ── Auth Endpoints ───────────────────────────────────────────────────────

@router.post("/api/auth/login")
async def login(request: Request, response: Response):
    """JSON login for Vue 3 SPA."""
    import json as _json
    body = await request.json()

    email = str(body.get("email", "")).strip().lower()
    password = str(body.get("password", ""))
    entity_code = str(body.get("entity_code", "")).strip()
    client_ip = request.client.host if request.client else "unknown"

    # Rate limiting
    blocked, retry_after = check_login_rate_limit(client_ip)
    if blocked:
        return error_response("Too many login attempts. Try again later.")

    user = find_user_by_email(email)
    if not user:
        record_login_rate_limit(client_ip)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if user.get("account_locked") or user.get("status") not in {"active"}:
        raise HTTPException(status_code=401, detail="Account locked or inactive")

    if not verify_password(password, str(user.get("password_hash", ""))):
        record_login_rate_limit(client_ip)
        # Track failed logins
        count = int(user.get("failed_login_count", 0)) + 1
        user["failed_login_count"] = count
        if count >= MAX_FAILED_LOGINS:
            user["account_locked"] = True
            user["account_locked_date"] = now_iso()
        save_users(load_users())  # Reload + save
        raise HTTPException(status_code=401, detail="Invalid credentials")

    entity_context, entity_error = validate_login_entity(entity_code)
    if entity_error or not entity_context:
        raise HTTPException(status_code=401, detail=entity_error or "Invalid entity")

    clear_login_rate_limit(client_ip)

    # Record successful login
    user["last_login"] = now_iso()
    user["failed_login_count"] = 0
    all_users = load_users()
    for u in all_users:
        if u.get("user_id") == user["user_id"]:
            u["last_login"] = now_iso()
            u["failed_login_count"] = 0
            break
    save_users(all_users)

    # Create session
    session_id = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=SESSION_TIMEOUT_MINUTES)
    sessions = load_sessions()
    sessions.append({
        "session_id": session_id,
        "user_id": user["user_id"],
        **entity_context,
        "login_time": now_iso(),
        "logout_time": "",
        "ip_address": request.client.host if request.client else "",
        "browser": request.headers.get("User-Agent", ""),
        "device": request.headers.get("User-Agent", ""),
        "active": True,
        "expires_at": expires_at.isoformat(),
        "current_module_key": "user_management",
        "current_module_path": "/",
        "current_module_opened_at": now_iso(),
        "last_seen_at": now_iso(),
        "last_activity_source": "api_login",
    })
    save_sessions(sessions)

    append_audit("user_management", str(user.get("user_id")), str(user.get("email")),
                 "user_login", {}, {"session_id": session_id, "entity": entity_context})

    full_user = user_context(user, sessions[-1])

    response.set_cookie(
        key="tacai_session_id",
        value=session_id,
        httponly=True,
        samesite="lax",
        max_age=SESSION_TIMEOUT_MINUTES * 60,
        path="/",
    )
    return {"authenticated": True, "user": full_user, "session_id": session_id}


@router.post("/api/auth/logout")
async def logout(request: Request, response: Response):
    """JSON logout."""
    session_id = request.cookies.get("tacai_session_id", "")
    sessions = load_sessions()
    for session in sessions:
        if session.get("session_id") == session_id and session.get("active", True):
            session["active"] = False
            session["logout_time"] = now_iso()
            append_audit("user_management", str(session.get("user_id")), "unknown",
                         "user_logout", {}, {"session_id": session_id})
            break
    save_sessions(sessions)
    response.set_cookie(
        key="tacai_session_id",
        value="",
        httponly=True,
        samesite="lax",
        max_age=0,
        path="/",
    )
    return success_response({"message": "Logged out"})


@router.get("/api/auth/session")
async def get_session(user: Optional[dict] = Depends(get_optional_user)):
    """Get current session info. Returns valid=true/false without throwing 401."""
    if user:
        return {"valid": True, "user": user}
    return {"valid": False, "user": None}


@router.get("/api/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    """Get current user context."""
    return success_response(user)


@router.post("/api/auth/change-password")
async def change_password(request: Request):
    """Change password for current user."""
    user = await get_current_user(request)
    body = await request.json()

    current_pw = str(body.get("current_password", ""))
    new_pw = str(body.get("new_password", ""))
    confirm_pw = str(body.get("confirm_password", ""))

    if new_pw != confirm_pw:
        return error_response("Passwords do not match")

    user_record = find_user_by_id(str(user.get("user_id", "")))
    if not user_record:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(current_pw, str(user_record.get("password_hash", ""))):
        return error_response("Current password is incorrect")

    errors = password_policy_errors(new_pw)
    if errors:
        return error_response("Password policy violation", errors)

    all_users = load_users()
    for u in all_users:
        if u.get("user_id") == user_record["user_id"]:
            u["password_hash"] = hash_password(new_pw)
            u["password_last_changed"] = now_iso()
            u["updated_at"] = now_iso()
            break
    save_users(all_users)

    append_audit("user_management", str(user.get("user_id")), str(user.get("email")),
                 "password_change", {}, {})
    return success_response({"message": "Password changed"})


# ── Public Endpoints ─────────────────────────────────────────────────────

@router.get("/api/public/entities")
async def public_entities():
    """Return active entities for login page entity selector.

    Response format matches old user_admin: {"entities": [...]} (no success/data wrapper).
    Frontend Login.vue expects `response.data.entities`.
    """
    from modules.auth.service import active_masterdata_entities
    entities = active_masterdata_entities()
    return {"entities": [
        {
            "entity_id": e.get("entity_id"),
            "entity_code": e.get("entity_code"),
            "entity_name_en": e.get("entity_name_en"),
            "entity_name_ja": e.get("entity_name_ja"),
            "entity_name_zh": e.get("entity_name_zh"),
            "country": e.get("country", ""),
        }
        for e in entities
    ]}


# ── Session Validation (internal, called by other services) ──────────────

@router.post("/api/validate-session")
async def api_validate_session(request: Request):
    """Validate session — used by frontend and other services."""
    body = await request.json()
    session_id = str(body.get("session_id", ""))

    session, user = validate_session_id(session_id)
    activity = session_context(session) if user else {}
    ctx = user_context(user, session) if user else None

    return {
        "valid": bool(user),
        "user": ctx,
        "session": activity,
    }


@router.post("/api/check-permission")
async def api_check_permission(request: Request):
    """Check if session has a specific permission."""
    body = await request.json()
    session_id = str(body.get("session_id", ""))
    permission_key = str(body.get("permission_key", ""))

    session, user = validate_session_id(session_id)
    allowed = bool(user and permission_key in effective_permissions(str(user.get("user_id", ""))))
    return {
        "allowed": allowed,
        "user_id": user.get("user_id") if user else "",
        "permission_key": permission_key,
    }


@router.post("/api/check-role")
async def api_check_role(request: Request):
    """Check if session has a specific role."""
    body = await request.json()
    session_id = str(body.get("session_id", ""))
    role_key = str(body.get("role_key", ""))

    session, user = validate_session_id(session_id)
    allowed = bool(user and role_key in active_user_role_keys(str(user.get("user_id", ""))))
    return {
        "allowed": allowed,
        "user_id": user.get("user_id") if user else "",
        "role_key": role_key,
    }


# ── Users CRUD ───────────────────────────────────────────────────────────

@router.get("/api/users")
async def list_users(
    q: str = Query(default=""),
    status: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(PermissionChecker("user_management.manage_users")),
):
    """List users with pagination."""
    all_rows = load_users()
    all_rows = [r for r in all_rows if not r.get("deleted") and r.get("status") != "deleted"]

    # Search filter
    if q:
        q_lower = q.lower()
        all_rows = [
            r for r in all_rows
            if q_lower in str(r.get("display_name", "")).lower()
            or q_lower in str(r.get("email", "")).lower()
            or q_lower in str(r.get("username", "")).lower()
            or q_lower in str(r.get("user_id", "")).lower()
        ]

    # Status filter
    if status:
        all_rows = [r for r in all_rows if r.get("status") == status]

    total = len(all_rows)
    start = (page - 1) * page_size
    paged = all_rows[start:start + page_size]

    # Enrich with role info
    result = []
    for u in paged:
        user_roles = active_user_role_keys(str(u.get("user_id", "")))
        result.append({
            "user_id": u.get("user_id"),
            "username": u.get("username"),
            "display_name": u.get("display_name"),
            "email": u.get("email"),
            "user_type": u.get("user_type"),
            "status": u.get("status"),
            "account_locked": u.get("account_locked"),
            "roles": user_roles,
            "linked_employee_id": u.get("linked_employee_id"),
            "linked_employee_name": u.get("linked_employee_name"),
            "linked_entity_code": u.get("linked_entity_code"),
            "created_at": u.get("created_at"),
            "last_login": u.get("last_login"),
        })

    return paginated_response(result, page, page_size, total)


@router.get("/api/users/{user_id}")
async def get_user(
    user_id: str,
    user: dict = Depends(PermissionChecker("user_management.manage_users")),
):
    """Get single user detail."""
    u = find_user_by_id(user_id)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")

    user_roles = active_user_role_keys(str(u.get("user_id", "")))
    # Get assigned role IDs
    role_ids = [
        m.get("role_id") for m in load_user_role_mappings()
        if m.get("user_id") == user_id and m.get("active", True)
    ]

    # Get entity assignments
    entity_mappings = [
        m for m in load_user_entity_mappings()
        if m.get("user_id") == user_id and m.get("active", True)
    ]

    return success_response({
        "user_id": u.get("user_id"),
        "username": u.get("username"),
        "display_name": u.get("display_name"),
        "email": u.get("email"),
        "phone": u.get("phone"),
        "department": u.get("department"),
        "position": u.get("position"),
        "user_type": u.get("user_type"),
        "status": u.get("status"),
        "account_locked": u.get("account_locked"),
        "linked_employee_id": u.get("linked_employee_id"),
        "linked_employee_no": u.get("linked_employee_no"),
        "linked_employee_name": u.get("linked_employee_name"),
        "linked_entity_id": u.get("linked_entity_id"),
        "linked_entity_code": u.get("linked_entity_code"),
        "linked_entity_name": u.get("linked_entity_name"),
        "linked_department_id": u.get("linked_department_id"),
        "linked_department_code": u.get("linked_department_code"),
        "linked_department_name": u.get("linked_department_name"),
        "language_preference": u.get("language_preference"),
        "roles": user_roles,
        "role_ids": role_ids,
        "entity_mappings": entity_mappings,
        "created_at": u.get("created_at"),
        "updated_at": u.get("updated_at"),
        "last_login": u.get("last_login"),
    })


@router.post("/api/users")
async def create_user(request: Request):
    """Create a new user."""
    actor = await get_current_user(request)
    actor_perms = effective_permissions(str(actor.get("user_id", "")))
    if "user_management.manage_users" not in actor_perms:
        raise HTTPException(status_code=403, detail="Forbidden")

    body = await request.json()

    # Build form-like data
    form_data: dict[str, Any] = {}
    for key, value in body.items():
        form_data[key] = value
    if "role_ids" not in form_data:
        form_data["role_ids"] = body.get("role_ids", [])

    enriched = enrich_user_employee_link(form_data)
    selected_role_ids = sorted(set(body.get("role_ids", [])))
    errors = validate_user_form(enriched, selected_role_ids)

    initial_password = str(body.get("initial_password", "") or body.get("password", ""))
    if not initial_password:
        errors.append("Password is required")
    errors.extend(password_policy_errors(initial_password))

    if errors:
        return error_response("Validation failed", errors)

    users = load_users()
    timestamp = now_iso()
    persist_data = user_persistable_data(enriched)

    new_user = {
        **persist_data,
        "user_id": next_id(users, "user_id", "USR-", 4),
        "password_hash": hash_password(initial_password),
        "password_last_changed": timestamp,
        "last_login": "",
        "failed_login_count": 0,
        "account_locked": persist_data.get("status") == "locked",
        "account_locked_date": timestamp if persist_data.get("status") == "locked" else "",
        "created_at": timestamp,
        "updated_at": timestamp,
        "deleted": False,
    }
    users.append(new_user)
    save_users(users)

    # Assign roles
    if selected_role_ids:
        mappings = load_user_role_mappings()
        for rid in selected_role_ids:
            mappings.append({
                "mapping_id": next_id(mappings, "mapping_id", "URM-", 4),
                "user_id": new_user["user_id"],
                "role_id": rid,
                "active": True,
                "assigned_at": timestamp,
            })
        save_user_role_mappings(mappings)

    append_audit("user_management", new_user["user_id"], str(actor.get("email")),
                 "user_create", {}, {"user_id": new_user["user_id"], "email": new_user.get("email")})

    return success_response({"user_id": new_user["user_id"]})


@router.post("/api/users/{user_id}")
async def update_user(request: Request, user_id: str):
    """Update an existing user."""
    actor = await get_current_user(request)
    actor_perms = effective_permissions(str(actor.get("user_id", "")))
    if "user_management.manage_users" not in actor_perms:
        raise HTTPException(status_code=403, detail="Forbidden")

    target = find_user_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    body = await request.json()

    # Build enriched form data
    enriched = enrich_user_employee_link({**target, **body})
    selected_role_ids = sorted(set(body.get("role_ids", []) or []))
    errors = validate_user_form(enriched, selected_role_ids, current_user_id=user_id)

    if errors:
        return error_response("Validation failed", errors)

    # Guard against removing last system admin
    new_status = body.get("status")
    if selected_role_ids and would_leave_no_active_system_admin(user_id, selected_role_ids, new_status):
        return error_response("Cannot remove the last active system administrator")

    users = load_users()
    timestamp = now_iso()
    for i, u in enumerate(users):
        if u.get("user_id") == user_id:
            persist_data = user_persistable_data(enriched)
            users[i] = {
                **u,
                **persist_data,
                "updated_at": timestamp,
                "deleted": False,
            }
            break
    save_users(users)

    # Update role assignments
    if selected_role_ids:
        old_mappings = load_user_role_mappings()
        new_mappings = [m for m in old_mappings if m.get("user_id") != user_id]
        for rid in selected_role_ids:
            new_mappings.append({
                "mapping_id": next_id(new_mappings, "mapping_id", "URM-", 4),
                "user_id": user_id,
                "role_id": rid,
                "active": True,
                "assigned_at": timestamp,
            })
        save_user_role_mappings(new_mappings)

    append_audit("user_management", user_id, str(actor.get("email")),
                 "user_update", {}, {"updated_fields": list(body.keys())})

    return success_response({"user_id": user_id})


@router.post("/api/users/{user_id}/deactivate")
async def deactivate_user(request: Request, user_id: str):
    """Deactivate a user."""
    actor = await get_current_user(request)
    actor_perms = effective_permissions(str(actor.get("user_id", "")))
    if "user_management.manage_users" not in actor_perms:
        raise HTTPException(status_code=403, detail="Forbidden")

    if would_leave_no_active_system_admin(user_id, [], "inactive"):
        return error_response("Cannot deactivate the last active system administrator")

    users = load_users()
    for u in users:
        if u.get("user_id") == user_id:
            u["status"] = "inactive"
            u["updated_at"] = now_iso()
            break
    save_users(users)

    # Invalidate all sessions for this user
    sessions = load_sessions()
    for s in sessions:
        if s.get("user_id") == user_id and s.get("active", True):
            s["active"] = False
            s["logout_time"] = now_iso()
    save_sessions(sessions)

    append_audit("user_management", user_id, str(actor.get("email")),
                 "user_deactivate", {}, {})
    return success_response({"message": f"User {user_id} deactivated"})


# ── Roles ────────────────────────────────────────────────────────────────

@router.get("/api/roles")
async def list_roles(user: dict = Depends(get_current_user)):
    """List all roles."""
    roles = load_roles()
    return success_response([{
        "role_id": r.get("role_id"),
        "role_key": r.get("role_key"),
        "role_name_en": r.get("role_name_en"),
        "role_name_ja": r.get("role_name_ja"),
        "role_name_zh": r.get("role_name_zh"),
        "description_en": r.get("description_en"),
        "active": r.get("active"),
    } for r in roles])


@router.get("/api/roles/{role_id}/permissions")
async def get_role_permissions(role_id: str, user: dict = Depends(get_current_user)):
    """Get role with assigned permissions."""
    role = next((r for r in load_roles() if r.get("role_id") == role_id), None)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    assigned_ids = {
        m.get("permission_id")
        for m in load_role_permission_mappings()
        if m.get("role_id") == role_id and m.get("active", True)
    }

    all_perms = load_permissions()
    return success_response({
        "role": role,
        "assigned_permission_ids": sorted(assigned_ids),
        "all_permissions": [{
            "permission_id": p.get("permission_id"),
            "permission_key": p.get("permission_key"),
            "category": p.get("category"),
            "description": p.get("description"),
            "active": p.get("active"),
        } for p in all_perms],
    })


@router.post("/api/roles/{role_id}/permissions")
async def update_role_permissions(request: Request, role_id: str):
    """Update role permissions."""
    actor = await get_current_user(request)
    actor_perms = effective_permissions(str(actor.get("user_id", "")))
    if "user_management.manage_users" not in actor_perms:
        raise HTTPException(status_code=403, detail="Forbidden")

    role = next((r for r in load_roles() if r.get("role_id") == role_id), None)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    body = await request.json()
    permission_ids = body.get("permission_ids", [])

    old_mappings = load_role_permission_mappings()
    new_mappings = [m for m in old_mappings if m.get("role_id") != role_id]
    timestamp = now_iso()
    for pid in permission_ids:
        new_mappings.append({
            "mapping_id": next_id(new_mappings, "mapping_id", "RPM-", 4),
            "role_id": role_id,
            "permission_id": pid,
            "active": True,
            "assigned_at": timestamp,
        })
    save_role_permission_mappings(new_mappings)

    append_audit("role_management", role_id, str(actor.get("email")),
                 "role_permissions_update", {}, {"permission_ids": permission_ids})
    return success_response({"message": "Permissions updated"})


# ── Permissions ──────────────────────────────────────────────────────────

@router.get("/api/permissions")
async def list_permissions(user: dict = Depends(get_current_user)):
    """List all permissions."""
    perms = load_permissions()
    return success_response([{
        "permission_id": p.get("permission_id"),
        "permission_key": p.get("permission_key"),
        "category": p.get("category"),
        "description": p.get("description"),
        "active": p.get("active"),
    } for p in perms])


# ── Audit Logs ───────────────────────────────────────────────────────────

@router.get("/api/audit-logs")
async def list_audit_logs(
    limit: int = Query(default=100, ge=1, le=1000),
    user: dict = Depends(PermissionChecker("user_management.manage_users")),
):
    """Return recent audit logs."""
    logs = load_audit_logs()
    logs = sorted(logs, key=lambda l: l.get("timestamp", ""), reverse=True)[:limit]
    return success_response(logs)


# ── Login Sessions ───────────────────────────────────────────────────────

@router.get("/api/login-sessions")
async def list_login_sessions(
    user: dict = Depends(PermissionChecker("user_management.manage_users")),
):
    """Return active login sessions with user info."""
    sessions = load_sessions()
    active = [s for s in sessions if s.get("active", True)]

    result = []
    for s in active:
        u = find_user_by_id(str(s.get("user_id", "")))
        result.append({
            "session_id": s.get("session_id"),
            "user_id": s.get("user_id"),
            "username": u.get("username") if u else "",
            "email": u.get("email") if u else "",
            "display_name": u.get("display_name") if u else "",
            "login_time": s.get("login_time"),
            "expires_at": s.get("expires_at"),
            "last_seen_at": s.get("last_seen_at"),
            "ip_address": s.get("ip_address"),
            "entity_code": s.get("entity_code"),
            "entity_name_en": s.get("entity_name_en"),
            "current_module_key": s.get("current_module_key"),
        })

    return success_response(result)


# ── Dashboard ─────────────────────────────────────────────────────────────

@router.get("/api/dashboard")
async def dashboard(user: dict = Depends(get_current_user)):
    """Return dashboard statistics."""
    stats = dashboard_stats()
    return success_response(stats)


# ── Internal API (no auth, used by other modules within the monolith) ────

@router.get("/api/internal/users")
async def internal_users(
    user_id: str = Query(default=""),
    role_key: str = Query(default=""),
    entity_id: str = Query(default=""),
):
    """Internal API: return users with optional filters. No auth required.

    Called by messaging module (replaces HTTP call to user_admin).
    """
    users = load_users()
    active_users = [u for u in users if u.get("status") == "active" and not u.get("account_locked")]

    if user_id:
        active_users = [u for u in active_users if u.get("user_id") == user_id]
    if entity_id:
        active_users = [u for u in active_users if u.get("linked_entity_id") == entity_id]
    if role_key:
        active_users = [u for u in active_users if role_key in active_user_role_keys(str(u.get("user_id", "")))]

    return success_response([{
        "user_id": u.get("user_id"),
        "username": u.get("username"),
        "display_name": u.get("display_name"),
        "email": u.get("email"),
        "user_type": u.get("user_type"),
        "linked_employee_id": u.get("linked_employee_id"),
        "linked_entity_id": u.get("linked_entity_id"),
        "linked_entity_code": u.get("linked_entity_code"),
        "entity_id": u.get("linked_entity_id"),
        "entity_code": u.get("linked_entity_code"),
        "roles": active_user_role_keys(str(u.get("user_id", ""))),
    } for u in active_users])
