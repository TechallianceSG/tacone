"""Employees router — CRUD, import, internal API for other modules."""

from __future__ import annotations

import io
import re
import csv as _csv
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File

from dependencies import get_current_user
from modules.auth.models import error_response, paginated_response, success_response
from modules.masterdata.service import entity_label, department_label, team_label

router = APIRouter()
TABLE = "emp_employees"
from shared import db_utils as _db


def _require_access(user: dict) -> None:
    perms: list = user.get("permissions") or []
    if "employee_management.access" not in perms and "system_admin" not in user.get("roles", []):
        raise HTTPException(status_code=403, detail="Forbidden")


def _unflatten(body: dict) -> dict:
    result: dict = {}
    for key, value in body.items():
        if '.' not in key:
            result[key] = value
        else:
            parts = key.split('.')
            cur = result
            for part in parts[:-1]:
                if part not in cur:
                    cur[part] = {}
                cur = cur[part]
            cur[parts[-1]] = value
    return result


# ── Internal API ────────────────────────────────────────────────────────

@router.get("/api/internal/employees")
async def internal_list(
    employee_ids: Optional[str] = Query(default=None),
    employee_number: Optional[str] = Query(default=None),
    include_payroll: bool = Query(default=False),
):
    rows = _db.load_table(TABLE) or []
    rows = [r for r in rows if not (r.get("metadata") or {}).get("deleted", False)]
    if employee_ids:
        id_set = set(i.strip() for i in employee_ids.split(",") if i.strip())
        rows = [r for r in rows if str(r.get("employee_id", "")) in id_set]
    if employee_number:
        rows = [r for r in rows if str(r.get("employee_number", "")).startswith(employee_number)]
    if not include_payroll:
        for r in rows:
            r.pop("payroll", None)
    return {"employees": rows}


@router.get("/api/internal/employees/{employee_id}")
async def internal_get(employee_id: str, include_payroll: bool = Query(default=False)):
    rows = _db.load_table(TABLE, where={"employee_id": employee_id})
    if not rows:
        raise HTTPException(status_code=404, detail="Not found")
    emp = rows[0]
    if not include_payroll:
        emp.pop("payroll", None)
    return {"employee": emp, "success": True}


# ── Public API ───────────────────────────────────────────────────────────

@router.get("/api/employees")
async def list_employees(
    q: Optional[str] = Query(default=None),
    entity_id: Optional[str] = Query(default=None),
    department_id: Optional[str] = Query(default=None),
    team_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    show_resigned: bool = Query(default=False),
    employment_type: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    _require_access(user)
    all_rows = _db.load_table(TABLE) or []
    all_rows = [r for r in all_rows if not (r.get("metadata") or {}).get("deleted", False)]
    total_all = len(all_rows)

    q_lower = (q or "").strip().lower()
    filtered = []
    for emp in all_rows:
        profile = emp.get("profile") or {}
        employment = emp.get("employment") or {}
        if q_lower:
            name = (profile.get("name") or {}).get("display_name", "")
            email = profile.get("email", "")
            emp_no = str(emp.get("employee_number", "")).lower()
            search = f"{name} {email} {emp_no}".lower()
            if q_lower not in search:
                continue
        if entity_id and employment.get("entity_id", "") != entity_id:
            continue
        if department_id and employment.get("department_id", "") != department_id:
            continue
        if team_id and employment.get("team_id", "") != team_id:
            continue
        emp_status = (employment.get("status") or "").lower()
        if status and emp_status != status.lower():
            continue
        if not show_resigned and emp_status == "resigned":
            continue
        if employment_type:
            et = employment.get("employment_type", "")
            if et.lower() != employment_type.lower():
                continue
        filtered.append(emp)

    is_filtered = bool(q_lower or entity_id or department_id or team_id or status or employment_type)
    total = len(filtered)
    start = (page - 1) * page_size
    paged = filtered[start:start + page_size]

    for emp in paged:
        ed = emp.get("employment") or {}
        eid = ed.get("entity_id", "")
        if eid:
            ed["entity_label"] = entity_label(eid)
        did = ed.get("department_id", "")
        if did:
            ed["department_label"] = department_label(did)
        tid = ed.get("team_id", "")
        if tid:
            ed["team_label"] = team_label(tid)

    return paginated_response(paged, page, page_size, total, total_all, is_filtered)


@router.get("/api/employees/{employee_id}")
async def get_employee(employee_id: str, user: dict = Depends(get_current_user)):
    _require_access(user)
    rows = _db.load_table(TABLE, where={"employee_id": employee_id})
    if not rows:
        raise HTTPException(status_code=404, detail="Not found")
    return success_response(rows[0])


@router.post("/api/employees")
async def create_employee(request: Request, user: dict = Depends(get_current_user)):
    _require_access(user)
    body = _unflatten(await request.json())
    all_rows = _db.load_table(TABLE) or []
    max_n = 0
    for r in all_rows:
        m = re.match(r"^EMP-(\d+)$", str(r.get("employee_id", "")))
        if m:
            max_n = max(max_n, int(m.group(1)))
    new_id = f"EMP-{max_n + 1:04d}"
    now = datetime.now(timezone.utc).isoformat()
    emp = {
        "employee_id": new_id, "employee_number": body.get("employee_number") or new_id,
        "profile": body.get("profile", {}), "employment": body.get("employment", {}),
        "payroll": body.get("payroll", {}), "visa": body.get("visa", {}),
        "language_profile": body.get("language_profile", {}),
        "skills_profile": body.get("skills_profile", {}),
        "metadata": {"deleted": False, "created_at": now, "updated_at": now},
    }
    _db.insert_record(TABLE, emp)
    return success_response(emp)


@router.post("/api/employees/{employee_id}")
async def update_employee(request: Request, employee_id: str, user: dict = Depends(get_current_user)):
    _require_access(user)
    body = _unflatten(await request.json())
    rows = _db.load_table(TABLE, where={"employee_id": employee_id})
    if not rows:
        raise HTTPException(status_code=404, detail="Not found")
    target = rows[0]
    if (target.get("metadata") or {}).get("deleted"):
        raise HTTPException(status_code=409, detail="Deleted")
    now = datetime.now(timezone.utc).isoformat()
    for k, v in body.items():
        if k == "employee_id":
            continue
        if isinstance(v, dict) and isinstance(target.get(k), dict):
            target[k] = {**target[k], **v}
        else:
            target[k] = v
    target["metadata"] = {**(target.get("metadata") or {}), "updated_at": now}
    _db.update_record(TABLE, "employee_id", employee_id, target)
    return success_response(target)


@router.delete("/api/employees/{employee_id}")
async def delete_employee(employee_id: str, user: dict = Depends(get_current_user)):
    _require_access(user)
    rows = _db.load_table(TABLE, where={"employee_id": employee_id})
    if not rows:
        raise HTTPException(status_code=404, detail="Not found")
    now = datetime.now(timezone.utc).isoformat()
    _db.update_record(TABLE, "employee_id", employee_id, {"metadata": {"deleted": True, "updated_at": now}})
    return success_response({"message": f"Employee {employee_id} deleted"})


@router.post("/api/employees/import")
async def import_employees(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    _require_access(user)
    content = await file.read()
    reader = _csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    all_rows = _db.load_table(TABLE) or []
    now = datetime.now(timezone.utc).isoformat()
    imported = 0
    max_n = 0
    for r in all_rows:
        m = re.match(r"^EMP-(\d+)$", str(r.get("employee_id", "")))
        if m:
            max_n = max(max_n, int(m.group(1)))
    for row in reader:
        max_n += 1
        emp = {
            "employee_id": f"EMP-{max_n:04d}",
            "employee_number": row.get("employee_number", f"EMP-{max_n:04d}"),
            "profile": {"name": {"display_name": row.get("display_name", ""), "given_name": row.get("given_name", ""), "family_name": row.get("family_name", "")}, "email": row.get("email", "")},
            "employment": {"entity_id": row.get("entity_id", ""), "department_id": row.get("department_id", ""), "team_id": row.get("team_id", ""), "status": "active"},
            "metadata": {"deleted": False, "created_at": now, "updated_at": now},
        }
        _db.insert_record(TABLE, emp)
        imported += 1
    return success_response({"imported": imported})


@router.get("/api/employees/export-template")
async def export_template():
    """Export CSV template for employee import."""
    header = ["employee_number", "display_name", "given_name", "family_name", "email", "entity_id", "department_id", "team_id"]
    output = io.StringIO()
    writer = _csv.writer(output)
    writer.writerow(header)
    from fastapi.responses import Response
    return Response(content=output.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=employees-import-template.csv"})
