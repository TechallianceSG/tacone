"""Masterdata service — entity, department, team, customer, vendor CRUD.

All data access is via shared/db_utils.py.
Previously masterdata/app.py (4864 lines); now stripped to core business logic.
HTML page rendering dropped — Vue 3 SPA handles the UI.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from shared import db_utils as _db

# ── Helpers ──────────────────────────────────────────────────────────────

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


# ── Data Loading ─────────────────────────────────────────────────────────

def load_entities() -> list[dict[str, Any]]:
    rows = _db.load_table("md_entities")
    return rows if rows else []


def save_entities(records: list[dict[str, Any]]) -> None:
    _db.save_table("md_entities", records)


def load_departments() -> list[dict[str, Any]]:
    rows = _db.load_table("md_departments")
    return rows if rows else []


def save_departments(records: list[dict[str, Any]]) -> None:
    _db.save_table("md_departments", records)


def load_teams() -> list[dict[str, Any]]:
    rows = _db.load_table("md_teams")
    return rows if rows else []


def save_teams(records: list[dict[str, Any]]) -> None:
    _db.save_table("md_teams", records)


def load_customers() -> list[dict[str, Any]]:
    rows = _db.load_table("md_customers")
    return rows if rows else []


def save_customers(records: list[dict[str, Any]]) -> None:
    _db.save_table("md_customers", records)


def load_vendors() -> list[dict[str, Any]]:
    rows = _db.load_table("md_vendors")
    return rows if rows else []


def save_vendors(records: list[dict[str, Any]]) -> None:
    _db.save_table("md_vendors", records)


def load_system_parameters() -> list[dict[str, Any]]:
    rows = _db.load_table("md_system_parameters")
    return rows if rows else []


def save_system_parameters(records: list[dict[str, Any]]) -> None:
    _db.save_table("md_system_parameters", records)


# ── Entity Queries ───────────────────────────────────────────────────────

def active_entities() -> list[dict[str, Any]]:
    return [e for e in load_entities() if str(e.get("status", "active")) == "active"]


def find_entity(entity_id: str) -> Optional[dict[str, Any]]:
    for e in load_entities():
        if str(e.get("entity_id", "")) == entity_id and e.get("status") != "deleted":
            return e
    return None


def find_department(department_id: str) -> Optional[dict[str, Any]]:
    for d in load_departments():
        if str(d.get("department_id", "")) == department_id and d.get("status") != "deleted":
            return d
    return None


def find_team(team_id: str) -> Optional[dict[str, Any]]:
    for t in load_teams():
        if str(t.get("team_id", "")) == team_id and t.get("status") != "deleted":
            return t
    return None


def entity_label(entity_id: str) -> str:
    """Return human-readable entity label: CODE - NAME."""
    e = find_entity(entity_id)
    if not e:
        return entity_id
    code = e.get("entity_code", "")
    name = e.get("entity_name_en") or e.get("entity_name_zh") or e.get("entity_name_ja") or ""
    return f"{code} - {name}" if name else code


def department_label(department_id: str) -> str:
    d = find_department(department_id)
    if not d:
        return department_id
    code = d.get("department_code", "")
    name = d.get("department_name_en") or d.get("department_name_zh") or d.get("department_name_ja") or ""
    return f"{code} - {name}" if name else code


def team_label(team_id: str) -> str:
    t = find_team(team_id)
    if not t:
        return team_id
    code = t.get("team_code", "")
    name = t.get("team_name_en") or t.get("team_name_zh") or t.get("team_name_ja") or ""
    return f"{code} - {name}" if name else code


# ── Public API (used by other modules) ───────────────────────────────────

def get_active_entities() -> list[dict]:
    """Return all active entities (replaces /api/internal/entities/active)."""
    return active_entities()


def get_active_departments(entity_id: Optional[str] = None) -> list[dict]:
    """Return departments, optionally filtered by entity_id."""
    deps = [d for d in load_departments() if str(d.get("status", "active")) == "active"]
    if entity_id:
        deps = [d for d in deps if str(d.get("entity_id", "")) == entity_id]
    return deps


def get_active_teams() -> list[dict]:
    """Return all teams."""
    return [t for t in load_teams() if str(t.get("status", "active")) == "active"]


def get_entity_by_code(entity_code: str) -> Optional[dict]:
    """Find active entity by code."""
    target = str(entity_code or "").strip().casefold()
    for e in active_entities():
        if str(e.get("entity_code", "")).strip().casefold() == target:
            return e
    return None


# ── Validation ───────────────────────────────────────────────────────────

def validate_entity_input(form: dict, existing: list[dict],
                          entity_id: Optional[str] = None) -> tuple[dict, dict]:
    """Validate entity create/update input. Returns (values, errors)."""
    errors: dict = {}
    values: dict = {}

    code = str(form.get("entity_code", "")).strip()
    if not code:
        errors["entity_code"] = "Entity code is required"
    elif code and not code.isascii():
        errors["entity_code"] = "Entity code must be ASCII"
    else:
        for e in existing:
            if e.get("status") == "deleted":
                continue
            if str(e.get("entity_code", "")) == code and str(e.get("entity_id", "")) != (entity_id or ""):
                errors["entity_code"] = "Entity code already exists"
                break
    values["entity_code"] = code

    name = str(form.get("entity_name_en", "")).strip()
    if not name:
        errors["entity_name_en"] = "Entity name (EN) is required"
    values["entity_name_en"] = name
    values["entity_name_ja"] = str(form.get("entity_name_ja", "")).strip()
    values["entity_name_zh"] = str(form.get("entity_name_zh", "")).strip()
    values["country"] = str(form.get("country", "")).strip()
    values["status"] = str(form.get("status", "active")).strip()
    values["currency"] = str(form.get("currency", "JPY")).strip()

    return values, errors


def validate_department_input(form: dict, existing: list[dict],
                              department_id: Optional[str] = None) -> tuple[dict, dict]:
    """Validate department create/update input."""
    errors: dict = {}
    values: dict = {}

    code = str(form.get("department_code", "")).strip()
    if not code:
        errors["department_code"] = "Department code is required"
    else:
        for d in existing:
            if d.get("status") == "deleted":
                continue
            if str(d.get("department_code", "")) == code and str(d.get("department_id", "")) != (department_id or ""):
                if str(d.get("entity_id", "")) == str(form.get("entity_id", "")):
                    errors["department_code"] = "Department code already exists for this entity"
                    break
    values["department_code"] = code

    name = str(form.get("department_name_en", "")).strip()
    if not name:
        errors["department_name_en"] = "Department name (EN) is required"
    values["department_name_en"] = name
    values["department_name_ja"] = str(form.get("department_name_ja", "")).strip()
    values["department_name_zh"] = str(form.get("department_name_zh", "")).strip()
    values["entity_id"] = str(form.get("entity_id", "")).strip()
    values["status"] = str(form.get("status", "active")).strip()

    return values, errors


def validate_team_input(form: dict, existing: list[dict],
                        team_id: Optional[str] = None) -> tuple[dict, dict]:
    """Validate team create/update input."""
    errors: dict = {}
    values: dict = {}

    code = str(form.get("team_code", "")).strip()
    if not code:
        errors["team_code"] = "Team code is required"
    else:
        for t in existing:
            if t.get("status") == "deleted":
                continue
            if str(t.get("team_code", "")) == code and str(t.get("team_id", "")) != (team_id or ""):
                if str(t.get("department_id", "")) == str(form.get("department_id", "")):
                    errors["team_code"] = "Team code already exists for this department"
                    break
    values["team_code"] = code

    name = str(form.get("team_name_en", "")).strip()
    if not name:
        errors["team_name_en"] = "Team name (EN) is required"
    values["team_name_en"] = name
    values["team_name_ja"] = str(form.get("team_name_ja", "")).strip()
    values["team_name_zh"] = str(form.get("team_name_zh", "")).strip()
    values["department_id"] = str(form.get("department_id", "")).strip()
    values["status"] = str(form.get("status", "active")).strip()

    return values, errors
