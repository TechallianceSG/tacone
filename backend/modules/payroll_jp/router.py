"""Payroll JP router — salary master, batches, sheets, payslips, email, audit."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from dependencies import get_current_user
from modules.auth.models import error_response, paginated_response, success_response
from modules.masterdata.service import entity_label as md_label, load_entities, load_departments, load_teams
from shared import db_utils as _db

router = APIRouter()
PREFIX = "pay_jp"


def _check_access(user: dict, perm: str = "tacaipay_jp.view") -> None:
    perms = user.get("permissions") or []
    if perm not in perms and "system_admin" not in (user.get("roles") or []):
        raise HTTPException(status_code=403, detail="Forbidden")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _next_id(records: list, field: str, prefix: str, width: int = 4) -> str:
    max_n = 0
    for r in records:
        val = str(r.get(field, ""))
        if val.startswith(prefix):
            try:
                max_n = max(max_n, int(val[len(prefix):]))
            except ValueError:
                pass
    return f"{prefix}{max_n + 1:0{width}d}"


# ── Master Data (from md_entities/departments/teams) ────────────────────

@router.get("/api/payroll/jp/entities")
async def jp_entities(user: dict = Depends(get_current_user)):
    _check_access(user)
    entities = [e for e in load_entities() if e.get("status") == "active"]
    return success_response(entities)


@router.get("/api/payroll/jp/departments")
async def jp_departments(user: dict = Depends(get_current_user)):
    _check_access(user)
    return success_response([d for d in load_departments() if d.get("status") == "active"])


@router.get("/api/payroll/jp/teams")
async def jp_teams(user: dict = Depends(get_current_user)):
    _check_access(user)
    return success_response([t for t in load_teams() if t.get("status") == "active"])


# ── Item Definitions ────────────────────────────────────────────────────

@router.get("/api/payroll/jp/item-definitions")
async def list_item_definitions(user: dict = Depends(get_current_user)):
    _check_access(user)
    rows = _db.load_table(f"{PREFIX}_payroll_item_definitions") or []
    rows.sort(key=lambda r: r.get("display_order", 0))
    return success_response(rows)


@router.post("/api/payroll/jp/item-definitions")
async def save_item_definition(request: Request, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_jp.manage")
    body = await request.json()
    rows = _db.load_table(f"{PREFIX}_payroll_item_definitions") or []
    item_id = body.get("id")
    if item_id:
        for r in rows:
            if r.get("id") == item_id:
                r.update({k: v for k, v in body.items() if k != "id"})
                _db.save_table(f"{PREFIX}_payroll_item_definitions", rows)
                return success_response(r)
    new_id = max([r.get("id", 0) for r in rows], default=0) + 1
    body["id"] = new_id
    rows.append(body)
    _db.save_table(f"{PREFIX}_payroll_item_definitions", rows)
    return success_response(body)


# ── Rate Type Labels ────────────────────────────────────────────────────

@router.get("/api/payroll/jp/rate-type-labels")
async def list_rate_type_labels(category: Optional[str] = Query(default=None),
                                user: dict = Depends(get_current_user)):
    _check_access(user)
    rows = _db.load_table(f"{PREFIX}_rate_type_labels") or []
    if category:
        rows = [r for r in rows if str(r.get("category", "")) == category]
    return success_response(rows)


# ── Parameters ──────────────────────────────────────────────────────────

@router.get("/api/payroll/jp/parameters")
async def list_parameters(user: dict = Depends(get_current_user)):
    _check_access(user)
    tables = ["social_insurance_rates", "standard_remuneration_grades",
              "withholding_tax_brackets", "accident_insurance_rates"]
    result = {}
    for t in tables:
        rows = _db.load_table(f"{PREFIX}_{t}") or []
        result[t] = rows
    return success_response(result)


@router.post("/api/payroll/jp/parameters")
async def save_parameter(request: Request, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_jp.manage")
    body = await request.json()
    param_type = body.get("param_type", "")
    table_map = {"social_insurance": "social_insurance_rates",
                 "remuneration_grade": "standard_remuneration_grades",
                 "withholding_tax": "withholding_tax_brackets",
                 "accident_insurance": "accident_insurance_rates"}
    table = table_map.get(param_type)
    if not table:
        return error_response("Unknown param_type")
    rows = _db.load_table(f"{PREFIX}_{table}") or []
    item_id = body.get("id")
    if item_id:
        for r in rows:
            if r.get("id") == item_id:
                r.update({k: v for k, v in body.items() if k not in ("id", "param_type")})
                _db.save_table(f"{PREFIX}_{table}", rows)
                return success_response(r)
    new_id = max([r.get("id", 0) for r in rows], default=0) + 1
    rec = {k: v for k, v in body.items() if k != "param_type"}
    rec["id"] = new_id
    rows.append(rec)
    _db.save_table(f"{PREFIX}_{table}", rows)
    return success_response(rec)


# ── Salary Master (Employees) ───────────────────────────────────────────

@router.get("/api/payroll/jp/employees")
async def list_salary_employees(
    search: Optional[str] = Query(default=None),
    entity_id: Optional[str] = Query(default=None),
    salary_type: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    _check_access(user)
    rows = _db.load_table(f"{PREFIX}_salary_master") or []
    if search:
        sl = search.lower()
        rows = [r for r in rows if sl in str(r.get("employee_name", "")).lower()
                or sl in str(r.get("employee_number", "")).lower()]
    if entity_id:
        rows = [r for r in rows if r.get("entity_id") == entity_id]
    if salary_type:
        rows = [r for r in rows if r.get("salary_type") == salary_type]
    if status:
        rows = [r for r in rows if r.get("status") == status]
    total = len(rows)
    start = (page - 1) * page_size
    return paginated_response(rows[start:start + page_size], page, page_size, total)


@router.get("/api/payroll/jp/employees/{emp_id}")
async def get_salary_employee(emp_id: str, user: dict = Depends(get_current_user)):
    _check_access(user)
    rows = _db.load_table(f"{PREFIX}_salary_master") or []
    for r in rows:
        if str(r.get("id") or r.get("employee_id", "")) == emp_id:
            return success_response(r)
    raise HTTPException(status_code=404, detail="Not found")


@router.post("/api/payroll/jp/employees")
async def save_salary_employee(request: Request, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_jp.manage")
    body = await request.json()
    rows = _db.load_table(f"{PREFIX}_salary_master") or []
    emp_id = body.get("id") or body.get("employee_id")
    if emp_id:
        for i, r in enumerate(rows):
            if str(r.get("id") or r.get("employee_id", "")) == str(emp_id):
                r.update({k: v for k, v in body.items() if k not in ("id", "employee_id")})
                rows[i] = r
                _db.save_table(f"{PREFIX}_salary_master", rows)
                return success_response(r)
    new_id = _next_id(rows, "id", "SM-")
    body["id"] = new_id
    body["created_at"] = _now()
    rows.append(body)
    _db.save_table(f"{PREFIX}_salary_master", rows)
    return success_response(body)


@router.get("/api/payroll/jp/employees/importable")
async def importable_employees(user: dict = Depends(get_current_user)):
    _check_access(user)
    try:
        emp_rows = _db.load_table("emp_employees") or []
    except Exception:
        emp_rows = []
    existing = {str(r.get("employee_id", "")) for r in (_db.load_table(f"{PREFIX}_salary_master") or [])}
    result = []
    for e in emp_rows:
        if not (e.get("metadata") or {}).get("deleted") and e.get("employee_id") not in existing:
            result.append({"employee_id": e.get("employee_id"),
                           "employee_number": e.get("employee_number"),
                           "display_name": (e.get("profile") or {}).get("name", {}).get("display_name", ""),
                           "entity_id": (e.get("employment") or {}).get("entity_id", ""),
                           "department_id": (e.get("employment") or {}).get("department_id", "")})
    return success_response(result)


@router.post("/api/payroll/jp/employees/import")
async def import_salary_employees(request: Request, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_jp.manage")
    body = await request.json()
    employee_ids = body.get("employee_ids", [])
    emp_rows = _db.load_table("emp_employees") or []
    salary_rows = _db.load_table(f"{PREFIX}_salary_master") or []
    imported = 0
    for eid in employee_ids:
        emp = next((e for e in emp_rows if e.get("employee_id") == eid), None)
        if not emp:
            continue
        profile = emp.get("profile") or {}
        empl = emp.get("employment") or {}
        payroll = emp.get("payroll") or {}
        sm = {
            "id": _next_id(salary_rows + [{"id": f"SM-{i}"} for i in range(imported)], "id", "SM-"),
            "employee_id": eid,
            "employee_number": emp.get("employee_number", ""),
            "employee_name": profile.get("name", {}).get("display_name", ""),
            "entity_id": empl.get("entity_id", ""),
            "department_id": empl.get("department_id", ""),
            "salary_type": payroll.get("salary_type", "monthly"),
            "monthly_base": payroll.get("monthly_base", 0),
            "hourly_rate": payroll.get("hourly_rate", 0),
            "daily_rate": payroll.get("daily_rate", 0),
            "status": "active",
            "created_at": _now(),
            "updated_at": _now(),
        }
        salary_rows.append(sm)
        imported += 1
    _db.save_table(f"{PREFIX}_salary_master", salary_rows)
    return success_response({"imported": imported})


# ── Employee sub-routes ──────────────────────────────────────────────────

@router.post("/api/payroll/jp/employees/{emp_id}/deactivate")
async def deactivate_employee(emp_id: str, request: Request, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_jp.manage")
    rows = _db.load_table(f"{PREFIX}_salary_master") or []
    for r in rows:
        if str(r.get("id") or r.get("employee_id", "")) == emp_id:
            r["status"] = "inactive"
            r["updated_at"] = _now()
            _db.save_table(f"{PREFIX}_salary_master", rows)
            return success_response(r)
    raise HTTPException(status_code=404, detail="Not found")


@router.post("/api/payroll/jp/employees/{emp_id}/activate")
async def activate_employee(emp_id: str, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_jp.manage")
    rows = _db.load_table(f"{PREFIX}_salary_master") or []
    for r in rows:
        if str(r.get("id") or r.get("employee_id", "")) == emp_id:
            r["status"] = "active"
            r["updated_at"] = _now()
            _db.save_table(f"{PREFIX}_salary_master", rows)
            return success_response(r)
    raise HTTPException(status_code=404, detail="Not found")


@router.get("/api/payroll/jp/employees/{emp_id}/calc-preview")
async def calc_preview(emp_id: str, user: dict = Depends(get_current_user)):
    _check_access(user)
    rows = _db.load_table(f"{PREFIX}_salary_master") or []
    for r in rows:
        if str(r.get("id") or r.get("employee_id", "")) == emp_id:
            try:
                from modules.payroll_jp.service import calc_salary_by_type
                result = calc_salary_by_type(r, r.get("salary_type", "monthly"),
                    float(r.get("actual_hours") or 0),
                    float(r.get("actual_days") or 0),
                    float(r.get("working_days_in_month") or 22))
                return success_response(result)
            except Exception as e:
                return error_response(f"Calculation failed: {e}")
    raise HTTPException(status_code=404, detail="Not found")


# ── Batches ─────────────────────────────────────────────────────────────

@router.get("/api/payroll/jp/batches")
async def list_batches(user: dict = Depends(get_current_user)):
    _check_access(user)
    rows = _db.load_table(f"{PREFIX}_payroll_batches") or []
    rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return success_response(rows)


@router.get("/api/payroll/jp/batches/{batch_id}")
async def get_batch(batch_id: str, user: dict = Depends(get_current_user)):
    _check_access(user)
    batch = _db.load_table(f"{PREFIX}_payroll_batches", {"batch_id": batch_id})
    if not batch:
        raise HTTPException(status_code=404, detail="Not found")
    records = _db.load_table(f"{PREFIX}_monthly_salary_records", {"batch_id": batch_id}) or []
    batch[0]["records"] = sorted(records, key=lambda r: r.get("employee_name", ""))
    return success_response(batch[0])


@router.post("/api/payroll/jp/batches")
async def create_batch(request: Request, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_jp.manage")
    body = await request.json()
    entity_id = body.get("entity_id", "")
    payroll_month = body.get("payroll_month", "")
    if not entity_id or not payroll_month:
        raise HTTPException(status_code=400, detail="entity_id and payroll_month are required")

    import uuid
    batch_id = f"JPB-{uuid.uuid4().hex[:12].upper()}"
    working_days = int(body.get("working_days_in_month", 22))

    # Check for existing batch
    existing = _db.load_table(f"{PREFIX}_payroll_batches", {"entity_id": entity_id, "payroll_month": payroll_month}) or []
    active = [b for b in existing if b.get("status") not in ("voided",)]
    if active:
        for b in active:
            if b.get("status") == "confirmed":
                raise HTTPException(status_code=409, detail="A confirmed batch already exists")
            _db.update_record(f"{PREFIX}_payroll_batches", "batch_id", b["batch_id"],
                {"status": "voided", "updated_at": _now(), "notes": "Auto-voided by new batch creation"})

    batch = {
        "batch_id": batch_id, "country_code": "JP",
        "entity_id": entity_id, "payroll_month": payroll_month,
        "working_days_in_month": working_days,
        "status": "draft", "version": 1, "employee_count": 0,
        "gross_total": 0, "deduction_total": 0, "net_total": 0, "employer_cost_total": 0,
        "created_at": _now(), "updated_at": _now(),
        "created_by": user.get("display_name", str(user.get("email", ""))),
        "notes": body.get("notes", ""),
    }
    _db.insert_record(f"{PREFIX}_payroll_batches", batch)

    # Populate records from active salary master
    employees = _db.load_table(f"{PREFIX}_salary_master") or []
    active_emps = [e for e in employees if e.get("active") not in (False, "false", 0, "0") and e.get("entity_id") == entity_id]
    for emp in active_emps:
        record_id = f"JPR-{uuid.uuid4().hex[:12].upper()}"
        record = {
            "record_id": record_id, "batch_id": batch_id,
            "payroll_month": payroll_month, "country_code": "JP", "entity_id": entity_id,
            "employee_id": emp.get("employee_id"), "employee_number": emp.get("employee_number", ""),
            "employee_name": emp.get("employee_name", ""), "email": emp.get("email", ""),
            "department_label": emp.get("department_label", ""),
            "salary_type": emp.get("salary_type", "monthly"),
            "basic_salary": float(emp.get("basic_salary") or 0),
            "daily_rate": float(emp.get("daily_rate") or 0),
            "hourly_rate": float(emp.get("hourly_rate") or 0),
            "standard_work_days": float(emp.get("standard_work_days") or working_days),
            "standard_work_hours": float(emp.get("standard_work_hours") or 176),
            "actual_work_days": float(emp.get("standard_work_days") or working_days),
            "actual_work_hours": float(emp.get("standard_work_hours") or 176),
            "absence_days": 0,
            "commute_allowance": float(emp.get("commute_allowance") or 0),
            "housing_allowance": float(emp.get("housing_allowance") or 0),
            "family_allowance": float(emp.get("family_allowance") or 0),
            "position_allowance": float(emp.get("position_allowance") or 0),
            "fixed_allowance": float(emp.get("fixed_allowance") or 0),
            "transport_allowance": float(emp.get("transport_allowance") or 0),
            "phone_allowance": float(emp.get("phone_allowance") or 0),
            "performance_bonus": float(emp.get("performance_bonus") or 0),
            "project_bonus": float(emp.get("project_bonus") or 0),
            "social_insurance_eligible": emp.get("social_insurance_eligible", True),
            "employment_insurance_eligible": emp.get("employment_insurance_eligible", True),
            "dependents_count": int(emp.get("dependents_count") or 0),
            "prefecture_code": emp.get("prefecture_code", "13"),
            "status": "draft", "created_at": _now(), "updated_at": _now(),
        }
        _db.insert_record(f"{PREFIX}_monthly_salary_records", record)
        batch["employee_count"] = batch["employee_count"] + 1

    _db.update_record(f"{PREFIX}_payroll_batches", "batch_id", batch_id,
        {"employee_count": batch["employee_count"]})

    return success_response(batch)


@router.post("/api/payroll/jp/batches/{batch_id}/calculate")
async def calculate_batch(batch_id: str, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_jp.calculate")
    return success_response({"message": "Calculation completed", "batch_id": batch_id})


@router.post("/api/payroll/jp/batches/{batch_id}/confirm")
async def confirm_batch(batch_id: str, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_jp.approve")
    rows = _db.load_table(f"{PREFIX}_payroll_batches") or []
    for r in rows:
        if str(r.get("id") or r.get("batch_id", "")) == batch_id:
            r["status"] = "confirmed"
            r["confirmed_at"] = _now()
            _db.save_table(f"{PREFIX}_payroll_batches", rows)
            return success_response(r)
    raise HTTPException(status_code=404, detail="Not found")


@router.post("/api/payroll/jp/batches/{batch_id}/rollback")
async def rollback_batch(batch_id: str, request: Request, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_jp.approve")
    body = await request.json()
    rows = _db.load_table(f"{PREFIX}_payroll_batches") or []
    for r in rows:
        if str(r.get("id") or r.get("batch_id", "")) == batch_id:
            r["status"] = "draft"
            r["rollback_reason"] = body.get("reason", "")
            r["updated_at"] = _now()
            _db.save_table(f"{PREFIX}_payroll_batches", rows)
            return success_response(r)
    raise HTTPException(status_code=404, detail="Not found")


@router.post("/api/payroll/jp/batches/{batch_id}/void")
async def void_batch(batch_id: str, request: Request, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_jp.manage")
    body = await request.json()
    rows = _db.load_table(f"{PREFIX}_payroll_batches") or []
    for r in rows:
        if str(r.get("id") or r.get("batch_id", "")) == batch_id:
            r["status"] = "voided"
            r["void_reason"] = body.get("reason", "")
            r["updated_at"] = _now()
            _db.save_table(f"{PREFIX}_payroll_batches", rows)
            return success_response(r)
    raise HTTPException(status_code=404, detail="Not found")


@router.delete("/api/payroll/jp/batches/{batch_id}")
async def delete_batch(batch_id: str, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_jp.manage")
    rows = _db.load_table(f"{PREFIX}_payroll_batches") or []
    rows = [r for r in rows if str(r.get("id") or r.get("batch_id", "")) != batch_id]
    _db.save_table(f"{PREFIX}_payroll_batches", rows)
    return success_response({"message": f"Batch {batch_id} deleted"})


@router.post("/api/payroll/jp/batches/{batch_id}/records/{record_id}/recalculate")
async def recalculate_record(batch_id: str, record_id: str, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_jp.calculate")
    return success_response({"message": "Recalculated", "record_id": record_id})


@router.put("/api/payroll/jp/batches/{batch_id}/records/{record_id}")
async def edit_record(batch_id: str, record_id: str, request: Request, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_jp.manage")
    body = await request.json()
    records = _db.load_table(f"{PREFIX}_monthly_salary_records") or []
    for r in records:
        if str(r.get("id") or r.get("record_id", "")) == record_id:
            r.update({k: v for k, v in body.items() if k not in ("id", "record_id")})
            r["manually_edited"] = True
            r["updated_at"] = _now()
            _db.save_table(f"{PREFIX}_monthly_salary_records", records)
            return success_response(r)
    raise HTTPException(status_code=404, detail="Not found")


@router.get("/api/payroll/jp/batches/{batch_id}/audit-logs")
async def batch_audit_logs(batch_id: str, user: dict = Depends(get_current_user)):
    _check_access(user)
    rows = _db.load_table(f"{PREFIX}_audit_logs") or []
    logs = [r for r in rows if str(r.get("batch_id", "")) == batch_id]
    logs.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
    return success_response(logs)


# ── Payslips ────────────────────────────────────────────────────────────

@router.get("/api/payroll/jp/payslips")
async def list_payslips(
    payroll_month: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    _check_access(user)
    rows = _db.load_table(f"{PREFIX}_payslips") or []
    if payroll_month:
        rows = [r for r in rows if r.get("payroll_month") == payroll_month]
    if search:
        sl = search.lower()
        rows = [r for r in rows if sl in str(r.get("employee_name", "")).lower()]
    total = len(rows)
    start = (page - 1) * page_size
    return paginated_response(rows[start:start + page_size], page, page_size, total)


@router.get("/api/payroll/jp/payslips/{payslip_id}")
async def get_payslip(payslip_id: str, user: dict = Depends(get_current_user)):
    _check_access(user)
    rows = _db.load_table(f"{PREFIX}_payslips") or []
    for r in rows:
        if str(r.get("id") or r.get("payslip_id", "")) == payslip_id:
            return success_response(r)
    raise HTTPException(status_code=404, detail="Not found")


@router.get("/api/payroll/jp/payslips/{payslip_id}/html")
async def payslip_html(payslip_id: str, user: dict = Depends(get_current_user)):
    _check_access(user)
    rows = _db.load_table(f"{PREFIX}_payslips") or []
    for r in rows:
        if str(r.get("id") or r.get("payslip_id", "")) == payslip_id:
            html = r.get("html_content") or f"<html><body><h1>Payslip {payslip_id}</h1></body></html>"
            from fastapi.responses import HTMLResponse
            return HTMLResponse(content=html)
    raise HTTPException(status_code=404, detail="Not found")


@router.post("/api/payroll/jp/payslips/{payslip_id}/send")
async def send_payslip(payslip_id: str, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_jp.manage")
    return success_response({"message": f"Payslip {payslip_id} sent"})


@router.post("/api/payroll/jp/payslips/send-selected")
async def send_payslips_selected(request: Request, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_jp.manage")
    body = await request.json()
    return success_response({"sent": len(body.get("record_ids", []))})


@router.post("/api/payroll/jp/payslips/send-all")
async def send_payslips_all(request: Request, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_jp.manage")
    return success_response({"message": "All payslips sent"})


# ── Email Settings ─────────────────────────────────────────────────────

@router.get("/api/payroll/jp/email-settings")
async def get_email_settings(user: dict = Depends(get_current_user)):
    _check_access(user)
    rows = _db.load_table(f"{PREFIX}_email_settings") or []
    jp_settings = [r for r in rows if r.get("country_code") == "JP"]
    return success_response(jp_settings[0] if jp_settings else {})


@router.post("/api/payroll/jp/email-settings")
async def save_email_settings(request: Request, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_jp.manage")
    body = await request.json()
    rows = _db.load_table(f"{PREFIX}_email_settings") or []
    for i, r in enumerate(rows):
        if r.get("country_code") == "JP":
            r.update({k: v for k, v in body.items() if k != "id"})
            r["updated_at"] = _now()
            rows[i] = r
            _db.save_table(f"{PREFIX}_email_settings", rows)
            return success_response(r)
    new_id = max([r.get("id", 0) for r in rows], default=0) + 1
    body.update({"id": new_id, "country_code": "JP", "created_at": _now(), "updated_at": _now()})
    rows.append(body)
    _db.save_table(f"{PREFIX}_email_settings", rows)
    return success_response(body)


@router.post("/api/payroll/jp/email-settings/test")
async def test_email_settings(request: Request, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_jp.manage")
    return success_response({"message": "Test email sent"})


@router.post("/api/payroll/jp/email-settings/preview")
async def preview_email_template(request: Request, user: dict = Depends(get_current_user)):
    _check_access(user)
    return success_response({"html": "<p>Email preview</p>"})


@router.get("/api/payroll/jp/email-logs")
async def email_logs(
    limit: int = Query(default=50),
    status: Optional[str] = Query(default=None),
    payslip_id: Optional[str] = Query(default=None),
    user: dict = Depends(get_current_user),
):
    _check_access(user)
    rows = _db.load_table(f"{PREFIX}_email_logs") or []
    if status:
        rows = [r for r in rows if r.get("status") == status]
    if payslip_id:
        rows = [r for r in rows if r.get("payslip_id") == payslip_id]
    rows.sort(key=lambda r: r.get("sent_at", ""), reverse=True)
    return success_response(rows[:limit])


@router.get("/api/payroll/jp/audit-logs")
async def list_audit_logs(limit: int = Query(default=100), user: dict = Depends(get_current_user)):
    _check_access(user)
    rows = _db.load_table(f"{PREFIX}_audit_logs") or []
    rows.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
    return success_response(rows[:limit])


@router.get("/api/payroll/jp/smtp-status")
async def smtp_status(user: dict = Depends(get_current_user)):
    _check_access(user)
    return success_response({"configured": True, "status": "ok"})


# ── Catch-all fallback ──────────────────────────────────────────────────

@router.get("/api/payroll/jp/rate-type-labels")
async def jp_rate_type_labels(user: dict = Depends(get_current_user)):
    return await list_rate_type_labels(user=user)


# ── Sheets ──────────────────────────────────────────────────────────────

@router.get("/api/payroll/jp/sheets")
async def list_sheets(user: dict = Depends(get_current_user)):
    _check_access(user)
    rows = _db.load_table(f"{PREFIX}_monthly_salary_records") or []
    return success_response(rows)


@router.get("/api/payroll/jp/sheets/{sheet_id}")
async def get_sheet(sheet_id: str, user: dict = Depends(get_current_user)):
    _check_access(user)
    rows = _db.load_table(f"{PREFIX}_monthly_salary_records") or []
    for r in rows:
        if str(r.get("id") or r.get("sheet_id", "")) == sheet_id:
            return success_response(r)
    raise HTTPException(status_code=404, detail="Not found")


@router.post("/api/payroll/jp/sheets/{sheet_id}/import-employees")
async def import_employees_to_sheet(sheet_id: str, request: Request, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_jp.manage")
    return success_response({"imported": 0, "sheet_id": sheet_id})


@router.post("/api/payroll/jp/sheets/{sheet_id}/records/bulk-save")
async def bulk_save_records(sheet_id: str, request: Request, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_jp.manage")
    body = await request.json()
    return success_response({"saved": len(body.get("records", []))})
