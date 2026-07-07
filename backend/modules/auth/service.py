"""TACAI Auth Service — business logic extracted from user_admin/app.py.

All functions that previously made HTTP calls to other services now use
direct database reads (since all tables are in the same PostgreSQL instance)
or will import from other service modules once they're migrated.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from shared import db_utils as _db

# ── Constants ────────────────────────────────────────────────────────────

SESSION_COOKIE = "tacai_session_id"
SESSION_TIMEOUT_MINUTES = 480  # 8 hours
PASSWORD_ITERATIONS = 120_000
MAX_FAILED_LOGINS = 5
USER_TYPES = {"employee", "admin", "external", "system"}

# ── Permission definitions (seeded on first run) ─────────────────────────

PERMISSION_DEFINITIONS: list[tuple[str, str, str]] = [
    ("dashboard.view", "Dashboard", "View dashboard"),
    ("employee_management.access", "Employee Management", "Access employee management"),
    ("employee_management.edit", "Employee Management", "Edit employees"),
    ("user_management.manage_users", "User Management", "Manage users"),
    ("masterdata.access", "Master Data", "Access master data"),
    ("masterdata.view", "Master Data", "View master data"),
    ("masterdata.maintain", "Master Data", "Maintain master data"),
    ("masterdata.admin", "Master Data", "Administer master data"),
    ("datadict.access", "Data Dictionary", "Access data dictionary"),
    ("tacaimsg.access", "Message Center", "Access message center"),
    ("tacaimsg.view", "Message Center", "View messages"),
    ("tacaimsg.workflow", "Message Center", "Manage workflows"),
    ("tacaimsg.admin", "Message Center", "Administer message center"),
    ("tacaimsg.delegate", "Message Center", "Manage delegations"),
    ("tacaimsg.approve", "Message Center", "Approve workflows"),
    ("tacaimsg.audit.view", "Message Center", "View audit logs"),
    ("tacaipay_jp.access", "Payroll JP", "Access JP payroll"),
    ("tacaipay_jp.view", "Payroll JP", "View JP payroll"),
    ("tacaipay_jp.manage", "Payroll JP", "Manage JP payroll"),
    ("tacaipay_jp.calculate", "Payroll JP", "Calculate JP payroll"),
    ("tacaipay_jp.approve", "Payroll JP", "Approve JP payroll"),
    ("tacaipay_sg.access", "Payroll SG", "Access SG payroll"),
    ("tacaipay_sg.view", "Payroll SG", "View SG payroll"),
    ("tacaipay_sg.manage", "Payroll SG", "Manage SG payroll"),
    ("tacaipay_sg.calculate", "Payroll SG", "Calculate SG payroll"),
    ("tacaipay_sg.approve", "Payroll SG", "Approve SG payroll"),
    ("payroll.access", "Payroll", "Access payroll"),
    ("client_revenue.customer_master.view", "Customer Master", "View customers"),
    ("client_revenue.customer_master.maintain", "Customer Master", "Maintain customers"),
    ("invoice.access", "Invoice", "Access invoice"),
    ("invoice.maintain", "Invoice", "Maintain invoices"),
    ("invoice.view", "Invoice", "View invoices"),
    ("invoice.approve", "Invoice", "Approve invoices"),
    ("invoice.send", "Invoice", "Send invoices"),
    ("invoice.payment", "Invoice", "Manage payments"),
]


# ── Helpers ──────────────────────────────────────────────────────────────

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def next_id(records: list[dict], field: str, prefix: str, width: int) -> str:
    max_num = 0
    for r in records:
        val = str(r.get(field, ""))
        if val.startswith(prefix):
            try:
                num = int(val[len(prefix):])
                max_num = max(max_num, num)
            except ValueError:
                pass
    return f"{prefix}{max_num + 1:0{width}d}"


def get_nested(record: dict, path: str, default: Any = "") -> Any:
    current: Any = record
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def entity_code_key(value: Any) -> str:
    return str(value or "").strip().casefold()


# ── Data Loading (ua_* tables via db_utils) ──────────────────────────────

def load_users() -> list[dict[str, Any]]:
    rows = _db.load_table("ua_users")
    return rows if rows else []


def save_users(records: list[dict[str, Any]]) -> None:
    _db.save_table("ua_users", records)


def load_roles() -> list[dict[str, Any]]:
    rows = _db.load_table("ua_roles")
    return rows if rows else []


def load_permissions() -> list[dict[str, Any]]:
    rows = _db.load_table("ua_permissions")
    return rows if rows else []


def load_user_role_mappings() -> list[dict[str, Any]]:
    rows = _db.load_table("ua_user_role_mapping")
    return rows if rows else []


def save_user_role_mappings(records: list[dict[str, Any]]) -> None:
    _db.save_table("ua_user_role_mapping", records)


def load_role_permission_mappings() -> list[dict[str, Any]]:
    rows = _db.load_table("ua_role_permission_mapping")
    return rows if rows else []


def save_role_permission_mappings(records: list[dict[str, Any]]) -> None:
    _db.save_table("ua_role_permission_mapping", records)


def load_user_entity_mappings() -> list[dict[str, Any]]:
    rows = _db.load_table("ua_user_entity_mapping")
    return rows if rows else []


def save_user_entity_mappings(records: list[dict[str, Any]]) -> None:
    _db.save_table("ua_user_entity_mapping", records)


def load_sessions() -> list[dict[str, Any]]:
    rows = _db.load_table("ua_user_sessions")
    return rows if rows else []


def save_sessions(records: list[dict[str, Any]]) -> None:
    _db.save_table("ua_user_sessions", records)


def load_audit_logs() -> list[dict[str, Any]]:
    rows = _db.load_table("ua_user_audit_logs")
    return rows if rows else []


def save_audit_logs(records: list[dict[str, Any]]) -> None:
    _db.save_table("ua_user_audit_logs", records)


# ── Cross-module data access (direct DB reads — was HTTP calls) ──────────

def load_masterdata_entities() -> list[dict[str, Any]]:
    """Read md_entities directly (was HTTP call to masterdata service)."""
    try:
        rows = _db.load_table("md_entities")
        return rows if rows else []
    except Exception:
        return []


def load_masterdata_departments() -> list[dict[str, Any]]:
    """Read md_departments directly (was HTTP call to masterdata service)."""
    try:
        rows = _db.load_table("md_departments")
        return rows if rows else []
    except Exception:
        return []


def load_employeeadmin_employees() -> list[dict[str, Any]]:
    """Read emp_employees directly (was HTTP call to employee_admin service)."""
    try:
        rows = _db.load_table("emp_employees")
        return rows if rows else []
    except Exception:
        return []


def load_employeeadmin_employee_by_id(employee_id: str) -> dict[str, Any] | None:
    """Read single employee directly from emp_employees."""
    try:
        rows = _db.load_table("emp_employees", where={"employee_id": employee_id})
        return rows[0] if rows else None
    except Exception:
        return None


def load_employeeadmin_employees_by_ids(employee_ids: list[str]) -> list[dict[str, Any]]:
    """Batch-read employees from emp_employees."""
    if not employee_ids:
        return []
    try:
        all_rows = _db.load_table("emp_employees")
        id_set = set(employee_ids)
        return [r for r in (all_rows or []) if str(r.get("employee_id", "")) in id_set]
    except Exception:
        return []


# ── Password ─────────────────────────────────────────────────────────────

def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), PASSWORD_ITERATIONS,
    )
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt, expected_hex = encoded_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_text)
    except (ValueError, TypeError):
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations,
    ).hex()
    return hmac.compare_digest(digest, expected_hex)


def password_policy_errors(password: str) -> list[str]:
    errors: list[str] = []
    if len(password) < 6:
        errors.append("Password must be at least 6 characters")
    if len(password) > 128:
        errors.append("Password must be at most 128 characters")
    if not any(c.isupper() for c in password):
        errors.append("Password must contain at least one uppercase letter")
    if not any(c.islower() for c in password):
        errors.append("Password must contain at least one lowercase letter")
    if not any(c.isdigit() for c in password):
        errors.append("Password must contain at least one number")
    return errors


# ── Lookups ──────────────────────────────────────────────────────────────

def find_user_by_email(email: str) -> dict[str, Any] | None:
    email_normalized = email.strip().lower()
    for user in load_users():
        if str(user.get("email", "")).strip().lower() == email_normalized and user.get("status") != "deleted":
            return user
    return None


def find_user_by_id(user_id: str) -> dict[str, Any] | None:
    for user in load_users():
        if user.get("user_id") == user_id and user.get("status") != "deleted":
            return user
    return None


def find_role_by_key(role_key: str) -> dict[str, Any] | None:
    for role in load_roles():
        if role.get("role_key") == role_key and role.get("active", True):
            return role
    return None


# ── Entities ─────────────────────────────────────────────────────────────

def active_masterdata_entities() -> list[dict[str, Any]]:
    return [e for e in load_masterdata_entities() if str(e.get("status", "active")) == "active"]


def find_active_entity_by_code(entity_code: str) -> dict[str, Any] | None:
    target = entity_code_key(entity_code)
    if not target:
        return None
    for entity in active_masterdata_entities():
        if entity_code_key(entity.get("entity_code")) == target:
            return entity
    return None


def find_active_entity_by_id(entity_id: str) -> dict[str, Any] | None:
    target = str(entity_id or "").strip()
    if not target:
        return None
    for entity in active_masterdata_entities():
        if str(entity.get("entity_id", "")) == target:
            return entity
    return None


def entity_context_from_record(entity: dict[str, Any]) -> dict[str, str]:
    return {
        "entity_id": str(entity.get("entity_id", "")),
        "entity_code": str(entity.get("entity_code", "")),
        "entity_name_en": str(entity.get("entity_name_en", "")),
        "entity_name_ja": str(entity.get("entity_name_ja", "")),
        "entity_name_zh": str(entity.get("entity_name_zh") or entity.get("entity_name_en", "")),
    }


def entity_context_from_session(session: dict[str, Any] | None) -> dict[str, str]:
    if not session:
        return {}
    entity_id = str(session.get("entity_id", "")).strip()
    entity_code = str(session.get("entity_code", "")).strip()
    if not entity_id or not entity_code:
        return {}
    return {
        "entity_id": entity_id,
        "entity_code": entity_code,
        "entity_name_en": str(session.get("entity_name_en", "")),
        "entity_name_ja": str(session.get("entity_name_ja", "")),
        "entity_name_zh": str(session.get("entity_name_zh", "")),
    }


def session_has_active_entity(session: dict[str, Any]) -> bool:
    context = entity_context_from_session(session)
    if not context:
        return False
    entity = find_active_entity_by_code(context.get("entity_code", ""))
    return bool(entity and str(entity.get("entity_id", "")) == context.get("entity_id"))


def active_masterdata_departments() -> list[dict[str, Any]]:
    return [d for d in load_masterdata_departments() if str(d.get("status", "active")) == "active"]


def find_active_department_by_id(department_id: str) -> dict[str, Any] | None:
    target = str(department_id or "").strip()
    if not target:
        return None
    for dept in active_masterdata_departments():
        if str(dept.get("department_id", "")) == target:
            return dept
    return None


# ── Employee Context ─────────────────────────────────────────────────────

def employee_number_from_record(employee: dict[str, Any]) -> str:
    return str(employee.get("employee_number") or employee.get("employee_no") or employee.get("employee_id") or "").strip()


def employee_entity_id(employee: dict[str, Any]) -> str:
    return str(get_nested(employee, "employment.entity_id", "") or employee.get("entity_id") or "").strip()


def employee_display_name(employee: dict[str, Any]) -> str:
    return str(get_nested(employee, "profile.name.display_name", "") or employee.get("display_name") or "").strip()


def employee_email_addr(employee: dict[str, Any]) -> str:
    return str(get_nested(employee, "profile.email", "") or employee.get("email") or "").strip()


def employee_department_id(employee: dict[str, Any]) -> str:
    return str(get_nested(employee, "employment.department_id", "") or employee.get("department") or "").strip()


def employee_status(employee: dict[str, Any]) -> str:
    return str(get_nested(employee, "employment.status", "") or employee.get("status") or "").strip()


def employee_context_from_employee(employee: dict[str, Any]) -> dict[str, str]:
    entity = find_active_entity_by_id(employee_entity_id(employee)) or {}
    dept_id = employee_department_id(employee)
    dept = find_active_department_by_id(dept_id) or {}
    dept_name = str(dept.get("department_name_en") or dept.get("department_name_ja") or dept.get("department_name_zh") or dept_id)
    return {
        "employee_id": str(employee.get("employee_id", "")),
        "employee_no": employee_number_from_record(employee),
        "employee_number": employee_number_from_record(employee),
        "employee_name": employee_display_name(employee),
        "display_name": employee_display_name(employee),
        "email": employee_email_addr(employee),
        "entity_id": employee_entity_id(employee),
        "entity_code": str(entity.get("entity_code", "")),
        "entity_name": str(entity.get("entity_name_en") or entity.get("entity_name_ja") or entity.get("entity_name_zh") or ""),
        "department": dept_id,
        "department_id": dept_id,
        "department_code": str(dept.get("department_code", "")),
        "department_name": dept_name,
        "employment_status": employee_status(employee),
    }


def employee_link_snapshot(employee_id: str) -> dict[str, str]:
    emp = load_employeeadmin_employee_by_id(employee_id)
    if emp and not bool(get_nested(emp, "metadata.deleted", False)):
        return employee_context_from_employee(emp)
    return {}


def find_employee_by_number(employee_number: str) -> dict[str, Any] | None:
    """Find employee by employee_number in emp_employees (was HTTP call)."""
    target = str(employee_number or "").strip().lower()
    if not target:
        return None
    try:
        all_rows = _db.load_table("emp_employees")
        for emp in (all_rows or []):
            if not bool(get_nested(emp, "metadata.deleted", False)):
                if employee_number_from_record(emp).lower() == target:
                    return emp
    except Exception:
        pass
    return None


def find_employee_by_id(employee_id: str) -> dict[str, Any] | None:
    """Find employee by employee_id in emp_employees (was HTTP call)."""
    emp = load_employeeadmin_employee_by_id(employee_id)
    if emp and not bool(get_nested(emp, "metadata.deleted", False)):
        return emp
    return None


# ── Employee Link Enrichment ─────────────────────────────────────────────

def enrich_user_employee_link(data: dict[str, Any]) -> dict[str, Any]:
    """Resolve linked_employee_number/ID to full employee context.

    Formerly made HTTP calls to employee_admin and masterdata.
    """
    enriched = dict(data)
    linked_employee_number = str(enriched.get("linked_employee_number", "") or "").strip()
    linked_employee_id = str(enriched.get("linked_employee_id", "") or "").strip()

    employee: dict[str, Any] | None = None
    resolution_error = ""

    if linked_employee_number:
        employee = find_employee_by_number(linked_employee_number)
        if not employee:
            resolution_error = "not_found"
        linked_employee_id = str(employee.get("employee_id", "") if employee else "")

    if not employee and linked_employee_id:
        employee = find_employee_by_id(linked_employee_id)
        if not employee:
            linked_employee_id = ""

    if resolution_error:
        enriched["_linked_employee_resolution_error"] = resolution_error

    if not employee and not linked_employee_id:
        enriched.update({
            "linked_employee_id": "", "linked_employee_no": "",
            "linked_employee_name": "", "linked_entity_id": "",
            "linked_entity_code": "", "linked_entity_name": "",
            "linked_department_id": "", "linked_department_code": "",
            "linked_department_name": "",
        })
        return enriched

    snapshot = employee_context_from_employee(employee) if employee else employee_link_snapshot(linked_employee_id)
    enriched.update({
        "linked_employee_id": snapshot.get("employee_id", linked_employee_id),
        "linked_employee_no": snapshot.get("employee_no", ""),
        "linked_employee_name": snapshot.get("employee_name", ""),
        "linked_entity_id": snapshot.get("entity_id", ""),
        "linked_entity_code": snapshot.get("entity_code", ""),
        "linked_entity_name": snapshot.get("entity_name", ""),
        "linked_department_id": snapshot.get("department_id", ""),
        "linked_department_code": snapshot.get("department_code", ""),
        "linked_department_name": snapshot.get("department_name", ""),
    })
    if snapshot.get("department") and not enriched.get("department"):
        enriched["department"] = snapshot["department"]
    return enriched


# ── Roles & Permissions ──────────────────────────────────────────────────

def active_user_role_keys(user_id: str) -> list[str]:
    roles_by_id = {r.get("role_id"): r for r in load_roles() if r.get("active", True)}
    keys: list[str] = []
    for mapping in load_user_role_mappings():
        if mapping.get("user_id") == user_id and mapping.get("active", True):
            role = roles_by_id.get(mapping.get("role_id"))
            if role:
                keys.append(str(role.get("role_key")))
    return sorted(set(keys))


def is_system_admin_user(user_id: str) -> bool:
    return "system_admin" in active_user_role_keys(user_id)


def effective_permissions(user_id: str) -> list[str]:
    role_keys = active_user_role_keys(user_id)
    permission_by_id = {p.get("permission_id"): p for p in load_permissions()}
    if "system_admin" in role_keys:
        configured = {str(p.get("permission_key")) for p in permission_by_id.values() if p.get("active", True)}
        seeded = {p[0] for p in PERMISSION_DEFINITIONS}
        return sorted(configured | seeded)
    effective: set[str] = set()
    roles = {r.get("role_id"): r for r in load_roles()}
    for mapping in load_role_permission_mappings():
        if not mapping.get("active", True):
            continue
        role = roles.get(mapping.get("role_id"))
        if not role or role.get("role_key") not in role_keys:
            continue
        perm = permission_by_id.get(mapping.get("permission_id"))
        if perm:
            effective.add(str(perm.get("permission_key")))
    return sorted(effective)


# ── User Context ─────────────────────────────────────────────────────────

def user_context(user: dict[str, Any], session: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build enriched user context with roles, permissions, employee link, entity."""
    user_id = str(user.get("user_id", ""))
    employee_ctx = employee_link_snapshot(str(user.get("linked_employee_id", "")))

    # Entity context: prefer session entity over employee entity
    entity_ctx = entity_context_from_session(session)
    if not entity_ctx.get("entity_id") and employee_ctx.get("entity_id"):
        entity_ctx = {
            "entity_id": employee_ctx.get("entity_id", ""),
            "entity_code": employee_ctx.get("entity_code", ""),
            "entity_name_en": employee_ctx.get("entity_name", ""),
            "entity_name_ja": "",
            "entity_name_zh": employee_ctx.get("entity_name", ""),
        }

    # Resolve language labels for entity name
    entity_name = (
        entity_ctx.get("entity_name_en")
        or entity_ctx.get("entity_name_zh")
        or entity_ctx.get("entity_name_ja")
        or ""
    )

    context: dict[str, Any] = {
        "user_id": user_id,
        "username": user.get("username", ""),
        "display_name": user.get("display_name", ""),
        "email": user.get("email", ""),
        "user_type": user.get("user_type", "admin"),
        "linked_employee_id": user.get("linked_employee_id", ""),
        "employee_id": employee_ctx.get("employee_id", user.get("linked_employee_id", "")),
        "employee_no": employee_ctx.get("employee_no", user.get("linked_employee_no", "")),
        "employee_number": employee_ctx.get("employee_number", user.get("linked_employee_no", "")),
        "employee_name": employee_ctx.get("employee_name", user.get("linked_employee_name", "")),
        "department": employee_ctx.get("department", user.get("department", "")),
        "department_id": employee_ctx.get("department_id", user.get("linked_department_id", "")),
        "department_code": employee_ctx.get("department_code", user.get("linked_department_code", "")),
        "department_name": employee_ctx.get("department_name", user.get("linked_department_name", "")),
        "entity_id": entity_ctx.get("entity_id", user.get("linked_entity_id", "")),
        "entity_code": entity_ctx.get("entity_code", user.get("linked_entity_code", "")),
        "entity_name": entity_name or user.get("linked_entity_name", ""),
        "entity": {
            "entity_id": entity_ctx.get("entity_id", ""),
            "entity_code": entity_ctx.get("entity_code", ""),
            "entity_name_en": entity_ctx.get("entity_name_en", ""),
            "entity_name_ja": entity_ctx.get("entity_name_ja", ""),
            "entity_name_zh": entity_ctx.get("entity_name_zh", ""),
        },
        "employment_status": employee_ctx.get("employment_status", ""),
        "roles": active_user_role_keys(user_id),
        "permissions": effective_permissions(user_id),
    }
    return context


# ── Entity Assignment ────────────────────────────────────────────────────

def user_entity_assignments(user_id: str) -> list[dict[str, Any]]:
    return [m for m in load_user_entity_mappings() if m.get("user_id") == user_id and m.get("active", True)]


def user_has_entity(user_id: str, entity_code: str) -> bool:
    target = entity_code_key(entity_code)
    return any(entity_code_key(m.get("entity_code")) == target for m in user_entity_assignments(user_id))


def validate_login_entity(entity_code: str) -> tuple[dict[str, str] | None, str | None]:
    """Validate entity_code for login. Returns (entity_context, error_message).

    Login is simple: the user picks an entity from the dropdown (populated from
    /api/public/entities which only returns active entities), enters credentials,
    and logs in. No user-entity assignment check — that's an authorization concern
    handled at the module/permission level, not at login.
    """
    normalized = str(entity_code or "").strip()
    if not normalized:
        return None, "Entity code is required"
    entity = find_active_entity_by_code(normalized)
    if not entity:
        return None, "Invalid entity code"
    return entity_context_from_record(entity), None


def _ensure_entity_mapping(user_id: str, entity_id: str, entity_code: str, entity_name: str) -> None:
    """Create entity mapping if it doesn't already exist."""
    mappings = load_user_entity_mappings()
    for m in mappings:
        if m.get("user_id") == user_id and m.get("entity_id") == entity_id:
            if not m.get("active", True):
                m["active"] = True
                m["is_default"] = True
                save_user_entity_mappings(mappings)
            return
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    mappings.append({
        "mapping_id": next_id(mappings, "mapping_id", "UEM-", 4),
        "user_id": user_id,
        "entity_id": entity_id,
        "entity_code": entity_code,
        "entity_name_en": entity_name,
        "entity_name_ja": "",
        "entity_name_zh": entity_name,
        "is_default": True,
        "active": True,
        "assigned_at": now,
        "assigned_by": "auto",
    })
    save_user_entity_mappings(mappings)


# ── Session Management ───────────────────────────────────────────────────

def validate_session_id(session_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Validate a session by ID. Returns (session, user) or (None, None)."""
    if not session_id:
        return None, None
    now = datetime.now(timezone.utc)
    rows = _db.load_table("ua_user_sessions", where={"session_id": session_id})
    session = rows[0] if rows else None
    if not session:
        return None, None
    if not session.get("active", True):
        return None, None
    expires_at = parse_iso(str(session.get("expires_at", "")))
    if not expires_at or expires_at <= now:
        return None, None
    user = find_user_by_id(str(session.get("user_id", "")))
    if not user or user.get("status") != "active" or user.get("account_locked"):
        return None, None
    if not session_has_active_entity(session):
        return None, None
    return session, user


def session_context(session: dict[str, Any] | None) -> dict[str, Any]:
    if not session:
        return {}
    return {
        "session_id": session.get("session_id", ""),
        "login_time": session.get("login_time", ""),
        "login_time_jst": _format_jst(session.get("login_time", "")),
        "expires_at": session.get("expires_at", ""),
        "ip_address": session.get("ip_address", ""),
        "entity": entity_context_from_session(session),
        "current_module_key": session.get("current_module_key", ""),
        "current_module_path": session.get("current_module_path", ""),
        "last_seen_at": session.get("last_seen_at", ""),
    }


def _format_jst(value: str) -> str:
    parsed = parse_iso(value)
    if not parsed:
        return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M JST")


def record_session_activity(session_id: str, module_key: str = "",
                            module_path: str = "", source: str = "api_call") -> None:
    """Update session last_seen_at and expiry."""
    sessions = load_sessions()
    for s in sessions:
        if s.get("session_id") == session_id and s.get("active", True):
            now = now_iso()
            s["last_seen_at"] = now
            s["last_activity_source"] = source
            if module_key:
                s["current_module_key"] = module_key
                s["current_module_path"] = module_path
                s["current_module_opened_at"] = now
            # Extend session expiry
            s["expires_at"] = (datetime.now(timezone.utc) + timedelta(minutes=SESSION_TIMEOUT_MINUTES)).isoformat()
            save_sessions(sessions)
            return


def session_cookie_header(session_id: str) -> str:
    return (
        f"{SESSION_COOKIE}={session_id}; "
        "Path=/; HttpOnly; SameSite=Lax; Max-Age=28800"
    )


def clear_session_cookie_header() -> str:
    return f"{SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"


# ── Audit ────────────────────────────────────────────────────────────────

def append_audit(module: str, record_id: str, user: str, action: str,
                 before: dict[str, Any] | None = None,
                 after: dict[str, Any] | None = None) -> None:
    logs = load_audit_logs()
    logs.append({
        "audit_id": next_id(logs, "audit_id", "AUD-", 6) if logs else "AUD-000001",
        "module": module,
        "record_id": record_id,
        "action": action,
        "user": user,
        "timestamp": now_iso(),
        "before_value": before or {},
        "after_value": after or {},
    })
    save_audit_logs(logs)


# ── Seed Data ────────────────────────────────────────────────────────────

def seed_roles_and_permissions() -> None:
    """Ensure base roles and permissions exist. Idempotent."""
    roles = load_roles()
    perms = load_permissions()
    role_perm_mappings = load_role_permission_mappings()

    # Seed permissions
    existing_keys = {str(p.get("permission_key")) for p in perms}
    for key, category, description in PERMISSION_DEFINITIONS:
        if key not in existing_keys:
            perms.append({
                "permission_id": next_id(perms, "permission_id", "PERM-", 4),
                "permission_key": key,
                "category": category,
                "description": description,
                "active": True,
                "created_at": now_iso(),
            })

    # Seed roles
    role_defs = [
        ("system_admin", "System Admin", "Full system access"),
        ("hr_manager", "HR Manager", "HR management access"),
        ("finance", "Finance", "Finance and invoice access"),
        ("manager", "Manager", "Team management access"),
        ("employee", "Employee", "Basic employee access"),
        ("remote_consultant", "Remote Consultant", "Remote consultant access"),
    ]
    existing_role_keys = {str(r.get("role_key")) for r in roles}
    for key, name, desc in role_defs:
        if key not in existing_role_keys:
            roles.append({
                "role_id": next_id(roles, "role_id", "ROLE-", 4),
                "role_key": key,
                "role_name_en": name,
                "role_name_ja": name,
                "role_name_zh": name,
                "description_en": desc,
                "active": True,
                "created_at": now_iso(),
            })

    save_perms = _db.save_table
    if perms:
        try:
            _db.save_table("ua_permissions", perms)
        except Exception:
            pass
    if roles:
        try:
            _db.save_table("ua_roles", roles)
        except Exception:
            pass

    # Assign all permissions to system_admin
    system_admin_role = next((r for r in roles if r.get("role_key") == "system_admin"), None)
    if system_admin_role:
        sa_role_id = system_admin_role["role_id"]
        existing_sa_perms = {
            str(m.get("permission_id"))
            for m in role_perm_mappings
            if m.get("role_id") == sa_role_id
        }
        for perm in perms:
            pid = perm["permission_id"]
            if pid not in existing_sa_perms:
                role_perm_mappings.append({
                    "mapping_id": next_id(role_perm_mappings, "mapping_id", "RPM-", 4),
                    "role_id": sa_role_id,
                    "permission_id": pid,
                    "active": True,
                    "assigned_at": now_iso(),
                })
        if role_perm_mappings:
            try:
                _db.save_table("ua_role_permission_mapping", role_perm_mappings)
            except Exception:
                pass


def seed_admin_user() -> None:
    """Ensure at least one system_admin user exists."""
    users = load_users()
    has_admin = any(
        u.get("status") == "active"
        and not u.get("account_locked")
        and "system_admin" in active_user_role_keys(str(u.get("user_id", "")))
        for u in users
    )
    if has_admin:
        return

    admin_email = "admin@tacai.com"
    admin = find_user_by_email(admin_email)
    timestamp = now_iso()

    if admin:
        admin["status"] = "active"
        admin["account_locked"] = False
        admin["failed_login_count"] = 0
        admin["user_type"] = "admin"
        admin["updated_at"] = timestamp
        admin["password_hash"] = hash_password("Admin123!")
        admin["password_last_changed"] = timestamp
        save_users(users)
        user_id = admin["user_id"]
    else:
        user_id = next_id(users, "user_id", "USR-", 4)
        users.append({
            "user_id": user_id,
            "username": "admin",
            "display_name": "System Administrator",
            "email": admin_email,
            "phone": "",
            "department": "",
            "position": "System Admin",
            "status": "active",
            "user_type": "admin",
            "password_hash": hash_password("Admin123!"),
            "password_last_changed": timestamp,
            "last_login": "",
            "failed_login_count": 0,
            "account_locked": False,
            "account_locked_date": "",
            "linked_employee_id": "",
            "linked_employee_no": "",
            "linked_employee_name": "",
            "linked_entity_id": "",
            "linked_entity_code": "",
            "linked_entity_name": "",
            "linked_department_id": "",
            "linked_department_code": "",
            "linked_department_name": "",
            "language_preference": "ja",
            "created_at": timestamp,
            "updated_at": timestamp,
            "deleted": False,
        })
        save_users(users)

    # Assign system_admin role
    system_admin_role = find_role_by_key("system_admin")
    if system_admin_role:
        mappings = load_user_role_mappings()
        already = any(
            m.get("user_id") == user_id and m.get("role_id") == system_admin_role["role_id"]
            for m in mappings
        )
        if not already:
            mappings.append({
                "mapping_id": next_id(mappings, "mapping_id", "URM-", 4),
                "user_id": user_id,
                "role_id": system_admin_role["role_id"],
                "active": True,
                "assigned_at": timestamp,
            })
            save_user_role_mappings(mappings)


# ── User CRUD Helpers ────────────────────────────────────────────────────

def user_persistable_data(data: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(data)
    cleaned.pop("linked_employee_number", None)
    cleaned.pop("_linked_employee_resolution_error", None)
    return cleaned


def validate_user_form(data: dict[str, Any], selected_role_ids: list[str],
                       current_user_id: str = "") -> list[str]:
    """Validate user creation/update data. Returns list of error messages."""
    errors: list[str] = []
    user_type = str(data.get("user_type", "admin") or "admin")
    linked_employee_id = str(data.get("linked_employee_id", "") or "").strip()
    linked_employee_number = str(data.get("linked_employee_number", "") or "").strip()
    resolution_error = str(data.get("_linked_employee_resolution_error", "") or "")

    if user_type not in USER_TYPES:
        errors.append("Invalid user type")
    if user_type == "employee" and not linked_employee_id and not linked_employee_number:
        errors.append("Employee-type users must be linked to an employee record")
    if resolution_error == "not_found":
        errors.append("Employee number not found")
    elif resolution_error == "ambiguous":
        errors.append("Employee number matches multiple employees")
    if linked_employee_id:
        emp = find_employee_by_id(linked_employee_id)
        if not emp:
            errors.append("Linked employee not found")
        else:
            status = employee_status(emp).strip().lower()
            if status and status not in {"active", "probation", "onboarding"}:
                errors.append("Linked employee is not active")
            for existing in load_users():
                if existing.get("status") == "deleted" or existing.get("deleted"):
                    continue
                if existing.get("user_id") == current_user_id:
                    continue
                if str(existing.get("status", "active")) != "active":
                    continue
                if str(existing.get("linked_employee_id", "") or "") == linked_employee_id:
                    errors.append("This employee is already linked to another active user")
                    break

    # Validate at least one role selected
    if not selected_role_ids:
        errors.append("At least one role must be selected")

    return errors


def would_leave_no_active_system_admin(target_user_id: str, new_role_ids: list[str],
                                       new_status: str | None = None) -> bool:
    """Check if the change would remove the last active system_admin."""
    system_admin_role_ids = {
        str(r.get("role_id"))
        for r in load_roles()
        if r.get("role_key") == "system_admin" and r.get("active", True)
    }
    if not system_admin_role_ids:
        return False
    count = 0
    for user in load_users():
        uid = str(user.get("user_id", ""))
        if user.get("status") == "deleted" or user.get("deleted"):
            continue
        status = new_status if uid == target_user_id and new_status else str(user.get("status", ""))
        if status != "active" or user.get("account_locked"):
            continue
        if uid == target_user_id and new_role_ids:
            role_ids = set(new_role_ids)
        else:
            role_ids = set(active_user_role_ids(uid))
        if role_ids & system_admin_role_ids:
            count += 1
    return count == 0


# ── Dashboard Stats ──────────────────────────────────────────────────────

def dashboard_stats() -> dict[str, Any]:
    users = load_users()
    active_users = [u for u in users if u.get("status") == "active" and not u.get("account_locked")]
    locked_users = [u for u in users if u.get("account_locked")]
    sessions = load_sessions()
    active_sessions = [s for s in sessions if s.get("active", True)]

    # Role distribution
    role_dist: dict[str, int] = {}
    for u in users:
        if u.get("status") == "active":
            for rk in active_user_role_keys(str(u.get("user_id", ""))):
                role_dist[rk] = role_dist.get(rk, 0) + 1

    # Recent logins
    recent_logins = sorted(
        [s for s in active_sessions if s.get("login_time")],
        key=lambda s: s.get("login_time", ""), reverse=True,
    )[:10]

    return {
        "total_users": len([u for u in users if u.get("status") != "deleted"]),
        "active_users": len(active_users),
        "locked_users": len(locked_users),
        "active_sessions": len(active_sessions),
        "role_distribution": role_dist,
        "recent_logins": [{
            "user_id": s.get("user_id", ""),
            "login_time": s.get("login_time", ""),
            "entity_code": s.get("entity_code", ""),
            "ip_address": s.get("ip_address", ""),
        } for s in recent_logins],
    }


# ── Login Rate Limiting ──────────────────────────────────────────────────

_login_attempts: dict[str, tuple[int, float]] = {}


def check_login_rate_limit(client_ip: str) -> tuple[bool, float]:
    """Returns (blocked, retry_after_seconds)."""
    import time as _time
    now = _time.monotonic()
    entry = _login_attempts.get(client_ip)
    if not entry:
        return False, 0
    count, first_time = entry
    if count < 5:
        return False, 0
    # Exponential backoff: 5s * 2^(count-5)
    delay = 5 * (2 ** (count - 5))
    elapsed = now - first_time
    if elapsed < delay:
        return True, delay - elapsed
    return False, 0


def record_login_rate_limit(client_ip: str) -> None:
    import time as _time
    now = _time.monotonic()
    entry = _login_attempts.get(client_ip)
    if not entry:
        _login_attempts[client_ip] = (1, now)
    else:
        count, first_time = entry
        _login_attempts[client_ip] = (count + 1, first_time)


def clear_login_rate_limit(client_ip: str) -> None:
    _login_attempts.pop(client_ip, None)
