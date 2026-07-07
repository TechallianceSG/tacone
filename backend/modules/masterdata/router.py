"""Masterdata router — entity, department, team CRUD + internal APIs."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from dependencies import get_current_user, require_permission
from modules.auth.models import error_response, paginated_response, success_response
from modules.masterdata.service import (
    active_entities,
    find_department,
    find_entity,
    find_team,
    get_active_departments,
    get_active_entities,
    get_active_teams,
    get_entity_by_code,
    load_customers,
    load_departments,
    load_entities,
    load_system_parameters,
    load_teams,
    load_vendors,
    next_id,
    now_iso,
    save_departments,
    save_entities,
    save_teams,
    validate_department_input,
    validate_entity_input,
    validate_team_input,
)

router = APIRouter()


# ── Helpers ──────────────────────────────────────────────────────────────

def _has_permission(user: dict, perm: str) -> bool:
    perms: list = user.get("permissions") or []
    roles: list = user.get("roles") or []
    return perm in perms or "system_admin" in roles


def _require_masterdata_access(user: dict) -> None:
    if not _has_permission(user, "masterdata.access"):
        raise HTTPException(status_code=403, detail="Forbidden")


def _require_masterdata_maintain(user: dict) -> None:
    if not _has_permission(user, "masterdata.maintain"):
        raise HTTPException(status_code=403, detail="Forbidden")


# ── Internal API (no auth — used by other modules in-process) ────────────

@router.get("/api/internal/entities/active")
async def internal_entities_active():
    """Return all active entities (used by auth, payroll, employees)."""
    return {"entities": get_active_entities()}


@router.get("/api/internal/entity/{entity_code}/active")
async def internal_entity_active(entity_code: str):
    """Check if entity is active (used by session validation)."""
    entity = get_entity_by_code(entity_code)
    return {"active": entity is not None, "entity": entity}


@router.get("/api/internal/departments")
async def internal_departments(entity_id: Optional[str] = Query(default=None)):
    """Return departments (used by auth, payroll, employees)."""
    deps = get_active_departments(entity_id)
    return {"departments": deps}


@router.get("/api/internal/teams")
async def internal_teams():
    """Return all active teams."""
    return {"teams": get_active_teams()}


# ── Entities ─────────────────────────────────────────────────────────────

@router.get("/api/masterdata/entities")
async def list_entities(user: dict = Depends(get_current_user)):
    """List all entities (filtered by user access)."""
    _require_masterdata_access(user)
    entity_id = str(user.get("entity_id") or user.get("linked_entity_id", ""))
    is_admin = _has_permission(user, "masterdata.admin")

    entities = load_entities()
    if not is_admin:
        entities = [e for e in entities if str(e.get("entity_id", "")) == entity_id]
    return {"entities": [e for e in entities if e.get("status") != "deleted"]}


@router.get("/api/masterdata/entities/{entity_id}")
async def get_entity(entity_id: str, user: dict = Depends(get_current_user)):
    """Get single entity."""
    _require_masterdata_access(user)
    entity = find_entity(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return {"entity": entity}


@router.post("/api/masterdata/entities")
async def create_entity(request: Request, user: dict = Depends(get_current_user)):
    """Create a new entity."""
    _require_masterdata_maintain(user)
    body = await request.json()
    entities = load_entities()

    form = {key: str(value) if not isinstance(value, (list, dict)) else "" for key, value in body.items()}
    values, errors = validate_entity_input(form, entities)
    if errors:
        return error_response("Validation failed", list(errors.values()))

    timestamp = now_iso()
    entity = {
        "entity_id": next_id(entities, "entity_id", "ENT-", 4),
        **values,
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    entities.append(entity)
    save_entities(entities)
    return success_response({"entity": entity, "entity_id": entity["entity_id"]})


@router.post("/api/masterdata/entities/{entity_id}")
async def update_entity(request: Request, entity_id: str, user: dict = Depends(get_current_user)):
    """Update an entity."""
    _require_masterdata_maintain(user)
    body = await request.json()
    entities = load_entities()

    index = next((i for i, e in enumerate(entities)
                  if str(e.get("entity_id", "")) == entity_id and e.get("status") != "deleted"), None)
    if index is None:
        raise HTTPException(status_code=404, detail="Entity not found")

    form = {key: str(value) if not isinstance(value, (list, dict)) else "" for key, value in body.items()}
    form["entity_id"] = entity_id
    values, errors = validate_entity_input(form, entities, entity_id)
    if errors:
        return error_response("Validation failed", list(errors.values()))

    entities[index] = {
        **entities[index],
        **values,
        "entity_id": entities[index].get("entity_id"),
        "updated_at": now_iso(),
    }
    save_entities(entities)
    return success_response({"entity": entities[index]})


@router.delete("/api/masterdata/entities/{entity_id}")
async def delete_entity(entity_id: str, user: dict = Depends(get_current_user)):
    """Deactivate an entity (soft delete)."""
    _require_masterdata_maintain(user)
    entities = load_entities()

    index = next((i for i, e in enumerate(entities)
                  if str(e.get("entity_id", "")) == entity_id and e.get("status") != "deleted"), None)
    if index is None:
        raise HTTPException(status_code=404, detail="Entity not found")

    entities[index]["status"] = "deleted"
    entities[index]["updated_at"] = now_iso()
    save_entities(entities)
    return success_response({"message": f"Entity {entity_id} deactivated"})


# ── Departments ──────────────────────────────────────────────────────────

@router.get("/api/masterdata/departments")
async def list_departments(
    entity_id: Optional[str] = Query(default=None),
    user: dict = Depends(get_current_user),
):
    """List departments."""
    _require_masterdata_access(user)
    deps = load_departments()
    deps = [d for d in deps if d.get("status") != "deleted"]
    if entity_id:
        deps = [d for d in deps if str(d.get("entity_id", "")) == entity_id]
    return {"departments": deps}


@router.get("/api/masterdata/departments/{department_id}")
async def get_department(department_id: str, user: dict = Depends(get_current_user)):
    """Get single department."""
    _require_masterdata_access(user)
    dept = find_department(department_id)
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    return {"department": dept}


@router.post("/api/masterdata/departments")
async def create_department(request: Request, user: dict = Depends(get_current_user)):
    """Create a department."""
    _require_masterdata_maintain(user)
    body = await request.json()
    departments = load_departments()

    form = {key: str(value) if not isinstance(value, (list, dict)) else "" for key, value in body.items()}
    values, errors = validate_department_input(form, departments)
    if errors:
        return error_response("Validation failed", list(errors.values()))

    timestamp = now_iso()
    department = {
        "department_id": next_id(departments, "department_id", "DEP-", 4),
        **values,
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    departments.append(department)
    save_departments(departments)
    return success_response({"department": department, "department_id": department["department_id"]})


@router.post("/api/masterdata/departments/{department_id}")
async def update_department(request: Request, department_id: str, user: dict = Depends(get_current_user)):
    """Update a department."""
    _require_masterdata_maintain(user)
    body = await request.json()
    departments = load_departments()

    index = next((i for i, d in enumerate(departments)
                  if str(d.get("department_id", "")) == department_id and d.get("status") != "deleted"), None)
    if index is None:
        raise HTTPException(status_code=404, detail="Department not found")

    form = {key: str(value) if not isinstance(value, (list, dict)) else "" for key, value in body.items()}
    values, errors = validate_department_input(form, departments, department_id)
    if errors:
        return error_response("Validation failed", list(errors.values()))

    departments[index] = {
        **departments[index],
        **values,
        "department_id": departments[index].get("department_id"),
        "updated_at": now_iso(),
    }
    save_departments(departments)
    return success_response({"department": departments[index]})


@router.delete("/api/masterdata/departments/{department_id}")
async def delete_department(department_id: str, user: dict = Depends(get_current_user)):
    """Deactivate a department."""
    _require_masterdata_maintain(user)
    departments = load_departments()

    index = next((i for i, d in enumerate(departments)
                  if str(d.get("department_id", "")) == department_id and d.get("status") != "deleted"), None)
    if index is None:
        raise HTTPException(status_code=404, detail="Department not found")

    departments[index]["status"] = "deleted"
    departments[index]["updated_at"] = now_iso()
    save_departments(departments)
    return success_response({"message": f"Department {department_id} deactivated"})


# ── Teams ────────────────────────────────────────────────────────────────

@router.get("/api/masterdata/teams")
async def list_teams(
    department_id: Optional[str] = Query(default=None),
    user: dict = Depends(get_current_user),
):
    """List teams."""
    _require_masterdata_access(user)
    teams = load_teams()
    teams = [t for t in teams if t.get("status") != "deleted"]
    if department_id:
        teams = [t for t in teams if str(t.get("department_id", "")) == department_id]
    return {"teams": teams}


@router.get("/api/masterdata/teams/{team_id}")
async def get_team(team_id: str, user: dict = Depends(get_current_user)):
    """Get single team."""
    _require_masterdata_access(user)
    team = find_team(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return {"team": team}


@router.post("/api/masterdata/teams")
async def create_team(request: Request, user: dict = Depends(get_current_user)):
    """Create a team."""
    _require_masterdata_maintain(user)
    body = await request.json()
    teams = load_teams()

    form = {key: str(value) if not isinstance(value, (list, dict)) else "" for key, value in body.items()}
    values, errors = validate_team_input(form, teams)
    if errors:
        return error_response("Validation failed", list(errors.values()))

    timestamp = now_iso()
    team = {
        "team_id": next_id(teams, "team_id", "TEAM-", 4),
        **values,
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    teams.append(team)
    save_teams(teams)
    return success_response({"team": team, "team_id": team["team_id"]})


@router.post("/api/masterdata/teams/{team_id}")
async def update_team(request: Request, team_id: str, user: dict = Depends(get_current_user)):
    """Update a team."""
    _require_masterdata_maintain(user)
    body = await request.json()
    teams = load_teams()

    index = next((i for i, t in enumerate(teams)
                  if str(t.get("team_id", "")) == team_id and t.get("status") != "deleted"), None)
    if index is None:
        raise HTTPException(status_code=404, detail="Team not found")

    form = {key: str(value) if not isinstance(value, (list, dict)) else "" for key, value in body.items()}
    values, errors = validate_team_input(form, teams, team_id)
    if errors:
        return error_response("Validation failed", list(errors.values()))

    teams[index] = {
        **teams[index],
        **values,
        "team_id": teams[index].get("team_id"),
        "updated_at": now_iso(),
    }
    save_teams(teams)
    return success_response({"team": teams[index]})


@router.delete("/api/masterdata/teams/{team_id}")
async def delete_team(team_id: str, user: dict = Depends(get_current_user)):
    """Deactivate a team."""
    _require_masterdata_maintain(user)
    teams = load_teams()

    index = next((i for i, t in enumerate(teams)
                  if str(t.get("team_id", "")) == team_id and t.get("status") != "deleted"), None)
    if index is None:
        raise HTTPException(status_code=404, detail="Team not found")

    teams[index]["status"] = "deleted"
    teams[index]["updated_at"] = now_iso()
    save_teams(teams)
    return success_response({"message": f"Team {team_id} deactivated"})


# ── System Parameters (email settings) ───────────────────────────────────

@router.get("/api/master-data/system-parameters/outbound-email-onboarding")
async def get_email_settings():
    """Return outbound email settings."""
    params = load_system_parameters()
    email_param = next(
        (p for p in params if p.get("parameter_id") == "outbound_email_onboarding"),
        None,
    )
    if email_param:
        return success_response(email_param)
    raise HTTPException(status_code=404, detail="Email settings not found")
