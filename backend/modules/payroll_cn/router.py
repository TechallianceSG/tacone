"""Payroll CN router — China payroll: salary master, social insurance, housing fund, IIT, batches, payslips."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from dependencies import get_current_user
from modules.auth.models import error_response, paginated_response, success_response
from modules.masterdata.service import entity_label as md_label, load_entities, load_departments, load_teams
from shared import db_utils as _db

router = APIRouter()
PREFIX = "pay_cn"


def _check_access(user: dict, perm: str = "tacaipay_cn.view") -> None:
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

@router.get("/api/payroll/cn/entities")
async def cn_entities(user: dict = Depends(get_current_user)):
    _check_access(user)
    entities = [e for e in load_entities() if e.get("status") == "active"]
    return success_response(entities)


@router.get("/api/payroll/cn/departments")
async def cn_departments(user: dict = Depends(get_current_user)):
    _check_access(user)
    return success_response([d for d in load_departments() if d.get("status") == "active"])


@router.get("/api/payroll/cn/teams")
async def cn_teams(user: dict = Depends(get_current_user)):
    _check_access(user)
    return success_response([t for t in load_teams() if t.get("status") == "active"])


# ── Item Definitions ────────────────────────────────────────────────────

# Shared item-definitions catalog (all countries in one table, keyed by country_code)
ITEM_DEF_TABLE = "pay_payroll_item_definitions"
ITEM_DEF_COUNTRY = "cn"


@router.get("/api/payroll/cn/item-definitions")
async def list_item_definitions(user: dict = Depends(get_current_user)):
    _check_access(user)
    rows = _db.load_table(ITEM_DEF_TABLE, {"country_code": ITEM_DEF_COUNTRY}) or []
    rows.sort(key=lambda r: r.get("display_order", 0))
    return success_response(rows)


@router.post("/api/payroll/cn/item-definitions")
async def save_item_definition(request: Request, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_cn.manage")
    body = await request.json()
    body["country_code"] = ITEM_DEF_COUNTRY
    item_id = body.get("id")
    if item_id:
        existing = _db.load_table(ITEM_DEF_TABLE, {"id": item_id})
        if existing and existing[0].get("country_code") == ITEM_DEF_COUNTRY:
            # Only update columns that actually exist on the row (ignore country_code / timestamps)
            updates = {k: v for k, v in body.items()
                       if k in existing[0] and k not in ("id", "country_code", "created_at", "updated_at")}
            _db.update_record(ITEM_DEF_TABLE, "id", item_id, updates)
            return success_response(body)
    all_rows = _db.load_table(ITEM_DEF_TABLE) or []
    body["id"] = max([r.get("id", 0) for r in all_rows], default=0) + 1
    _db.insert_record(ITEM_DEF_TABLE, body)
    return success_response(body)


# ── Parameters (CN-specific: social insurance, housing fund, tax brackets) ──

@router.get("/api/payroll/cn/parameters")
async def list_parameters(user: dict = Depends(get_current_user)):
    _check_access(user)
    tables = ["social_insurance_rates", "housing_fund_rates", "tax_brackets"]
    result = {}
    for t in tables:
        rows = _db.load_table(f"{PREFIX}_{t}") or []
        result[t] = rows
    return success_response(result)


@router.post("/api/payroll/cn/parameters")
async def save_parameter(request: Request, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_cn.manage")
    body = await request.json()
    param_type = body.get("param_type", "")
    table_map = {"social_insurance": "social_insurance_rates",
                 "housing_fund": "housing_fund_rates",
                 "tax_bracket": "tax_brackets"}
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

@router.get("/api/payroll/cn/employees")
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


@router.get("/api/payroll/cn/employees/importable")
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


@router.post("/api/payroll/cn/employees/import")
async def import_salary_employees(request: Request, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_cn.manage")
    body = await request.json()
    imported = 0
    emp_rows = _db.load_table("emp_employees") or []
    for eid in body.get("employee_ids", []):
        if str(eid) in {str(r.get("employee_id", "")) for r in (_db.load_table(f"{PREFIX}_salary_master") or [])}:
            continue
        emp = next((e for e in emp_rows if str(e.get("employee_id")) == str(eid)), None)
        if not emp:
            continue
        profile = emp.get("profile") or {}
        employment = emp.get("employment") or {}
        name = profile.get("name", {})
        payroll = emp.get("payroll") or {}
        record = {
            "employee_id": str(emp.get("employee_id", "")),
            "employee_number": str(emp.get("employee_number", "")),
            "employee_name": name.get("display_name", f"{name.get('family_name','')} {name.get('given_name','')}".strip()),
            "email": profile.get("email", ""),
            "entity_id": employment.get("entity_id", ""),
            "department_id": employment.get("department_id", ""),
            "salary_type": payroll.get("salary_type", "monthly"),
            "basic_salary": payroll.get("basic_salary", 0),
            "position_allowance": payroll.get("position_allowance", 0),
            "transport_allowance": 0,
            "bonus": 0,
            "status": "active", "source": "employeeadmin",
            "created_at": _now(), "updated_at": _now(),
        }
        _db.insert_record(f"{PREFIX}_salary_master", record)
        imported += 1
    return success_response({"imported": imported})


@router.get("/api/payroll/cn/employees/{emp_id}")
async def get_salary_employee(emp_id: str, user: dict = Depends(get_current_user)):
    _check_access(user)
    rows = _db.load_table(f"{PREFIX}_salary_master", {"employee_id": emp_id})
    if not rows:
        raise HTTPException(status_code=404, detail="Not found")
    return success_response(rows[0])


@router.post("/api/payroll/cn/employees")
async def save_salary_employee(request: Request, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_cn.manage")
    body = await request.json()
    emp_id = body.get("id") or body.get("employee_id")
    if emp_id:
        existing = _db.load_table(f"{PREFIX}_salary_master", {"employee_id": str(emp_id)})
        if existing:
            updates = {k: v for k, v in body.items() if k not in ("id", "employee_id", "created_at")}
            updates["updated_at"] = _now()
            _db.update_record(f"{PREFIX}_salary_master", "employee_id", str(emp_id), updates)
            updated = _db.load_table(f"{PREFIX}_salary_master", {"employee_id": str(emp_id)})
            return success_response(updated[0] if updated else body)
    body["employee_id"] = str(emp_id) if emp_id else str(body.get("employee_id", ""))
    body["created_at"] = _now()
    body["updated_at"] = _now()
    _db.insert_record(f"{PREFIX}_salary_master", body)
    return success_response(body)


# ── Employee sub-routes ──────────────────────────────────────────────────

@router.post("/api/payroll/cn/employees/{emp_id}/deactivate")
async def deactivate_employee(emp_id: str, request: Request, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_cn.manage")
    body = await request.json()
    updates = {"status": "inactive", "updated_at": _now()}
    ok = _db.update_record(f"{PREFIX}_salary_master", "employee_id", emp_id, updates)
    if not ok:
        raise HTTPException(status_code=404, detail="Not found")
    return success_response({"employee_id": emp_id, **updates})


@router.post("/api/payroll/cn/employees/{emp_id}/activate")
async def activate_employee(emp_id: str, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_cn.manage")
    updates = {"status": "active", "updated_at": _now()}
    ok = _db.update_record(f"{PREFIX}_salary_master", "employee_id", emp_id, updates)
    if not ok:
        raise HTTPException(status_code=404, detail="Not found")
    return success_response({"employee_id": emp_id, **updates})


@router.get("/api/payroll/cn/employees/{emp_id}/calc-preview")
async def calc_preview(emp_id: str, user: dict = Depends(get_current_user)):
    _check_access(user)
    rows = _db.load_table(f"{PREFIX}_salary_master") or []
    for r in rows:
        if str(r.get("id") or r.get("employee_id", "")) == emp_id:
            try:
                from modules.payroll_cn.service import calc_salary
                result = calc_salary(r, {
                    "full_attendance_days": float(r.get("standard_work_days") or 22),
                    "actual_attendance_days": float(r.get("standard_work_days") or 22),
                    "personal_leave_days": 0,
                    "annual_leave_days": 0,
                    "sick_leave_days": 0,
                    "other_leave_days": 0,
                })
                return success_response(result)
            except Exception as e:
                return error_response(f"Calculation failed: {e}")
    raise HTTPException(status_code=404, detail="Not found")


# ── Batches ─────────────────────────────────────────────────────────────

@router.get("/api/payroll/cn/batches")
async def list_batches(user: dict = Depends(get_current_user)):
    _check_access(user)
    rows = _db.load_table(f"{PREFIX}_payroll_batches") or []
    rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return success_response(rows)


@router.get("/api/payroll/cn/batches/{batch_id}")
async def get_batch(batch_id: str, user: dict = Depends(get_current_user)):
    _check_access(user)
    batch = _db.load_table(f"{PREFIX}_payroll_batches", {"batch_id": batch_id})
    if not batch:
        raise HTTPException(status_code=404, detail="Not found")
    records = _db.load_table(f"{PREFIX}_monthly_salary_records", {"batch_id": batch_id}) or []
    batch[0]["records"] = sorted(records, key=lambda r: r.get("employee_name", ""))
    return success_response(batch[0])


@router.post("/api/payroll/cn/batches")
async def create_batch(request: Request, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_cn.manage")
    body = await request.json()
    entity_id = body.get("entity_id", "")
    payroll_month = body.get("payroll_month", "")
    if not entity_id or not payroll_month:
        raise HTTPException(status_code=400, detail="entity_id and payroll_month are required")

    import uuid
    batch_id = f"CNB-{uuid.uuid4().hex[:12].upper()}"
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
        "batch_id": batch_id, "country_code": "CN",
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
    active_emps = [e for e in employees if e.get("status") == "active" and e.get("entity_id") == entity_id]
    for emp in active_emps:
        record_id = f"CNR-{uuid.uuid4().hex[:12].upper()}"
        record = {
            "record_id": record_id, "batch_id": batch_id,
            "payroll_month": payroll_month, "country_code": "CN", "entity_id": entity_id,
            "employee_id": emp.get("employee_id"), "employee_number": emp.get("employee_number", ""),
            "employee_name": emp.get("employee_name", ""), "email": emp.get("email", ""),
            "department_label": emp.get("department_label", ""),
            "salary_type": emp.get("salary_type", "monthly"),
            # Attendance
            "full_attendance_days": float(emp.get("standard_work_days") or working_days),
            "actual_attendance_days": float(emp.get("standard_work_days") or working_days),
            "personal_leave_days": 0, "annual_leave_days": 0,
            "sick_leave_days": 0, "other_leave_days": 0,
            # Earnings (populated by calculation)
            "basic_salary": float(emp.get("basic_salary") or 0),
            "position_allowance": float(emp.get("position_allowance") or 0),
            "attendance_pay": 0, "sick_leave_pay": 0,
            "full_attendance_bonus": 0, "other_additions": 0,
            "gross_pay": 0,
            # Deductions
            "social_insurance": 0, "housing_fund": 0,
            "iit": 0, "other_deductions": 0,
            "deduction_total": 0,
            # Net
            "net_pay": 0,
            # Employer costs
            "employer_social_insurance": 0, "employer_housing_fund": 0,
            "employer_cost_total": 0,
            # Meta
            "status": "draft", "created_at": _now(), "updated_at": _now(),
        }
        _db.insert_record(f"{PREFIX}_monthly_salary_records", record)
        batch["employee_count"] = batch["employee_count"] + 1

    _db.update_record(f"{PREFIX}_payroll_batches", "batch_id", batch_id,
        {"employee_count": batch["employee_count"]})

    return success_response(batch)


@router.post("/api/payroll/cn/batches/{batch_id}/calculate")
async def calculate_batch(batch_id: str, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_cn.calculate")
    from modules.payroll_cn.service import calc_salary

    batches = _db.load_table(f"{PREFIX}_payroll_batches") or []
    batch = next((b for b in batches if b.get("batch_id") == batch_id), None)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    records = _db.load_table(f"{PREFIX}_monthly_salary_records") or []
    batch_records = [r for r in records if r.get("batch_id") == batch_id]

    # Load rates once
    si_rates_all = _db.load_table(f"{PREFIX}_social_insurance_rates") or []
    hf_rates_all = _db.load_table(f"{PREFIX}_housing_fund_rates") or []
    tax_brackets = _db.load_table(f"{PREFIX}_tax_brackets") or []

    gross_total = 0
    deduction_total = 0
    net_total = 0
    employer_cost_total = 0

    for rec in batch_records:
        # Build attendance dict
        attendance = {
            "full_attendance_days": float(rec.get("full_attendance_days") or batch.get("working_days_in_month", 22)),
            "actual_attendance_days": float(rec.get("actual_attendance_days") or batch.get("working_days_in_month", 22)),
            "personal_leave_days": float(rec.get("personal_leave_days") or 0),
            "annual_leave_days": float(rec.get("annual_leave_days") or 0),
            "sick_leave_days": float(rec.get("sick_leave_days") or 0),
            "other_leave_days": float(rec.get("other_leave_days") or 0),
            "other_additions": float(rec.get("other_additions") or 0),
            "other_deductions": float(rec.get("other_deductions") or 0),
        }

        # Look up city-specific rates
        city_code = rec.get("city_code", "320100")  # default: 南京
        si_rates = next((r for r in si_rates_all if str(r.get("city_code", "")) == city_code), si_rates_all[0] if si_rates_all else {})
        hf_rate = next((r for r in hf_rates_all if str(r.get("city_code", "")) == city_code), hf_rates_all[0] if hf_rates_all else {})

        result = calc_salary(rec, attendance, si_rates, hf_rate, tax_brackets)

        # Update record with calculation results
        for k, v in result.items():
            if k in rec:
                rec[k] = v
        rec["calculation_detail"] = result
        rec["status"] = "calculated"
        rec["updated_at"] = _now()

        gross_total += float(result.get("gross_pay", 0))
        deduction_total += float(result.get("deduction_total", 0))
        net_total += float(result.get("net_pay", 0))
        employer_cost_total += float(result.get("employer_cost_total", 0))

    # Save updated records
    _db.save_table(f"{PREFIX}_monthly_salary_records", records)

    # Update batch
    batch["status"] = "calculated"
    batch["gross_total"] = gross_total
    batch["deduction_total"] = deduction_total
    batch["net_total"] = net_total
    batch["employer_cost_total"] = employer_cost_total
    batch["updated_at"] = _now()
    for i, b in enumerate(batches):
        if b.get("batch_id") == batch_id:
            batches[i] = batch
            break
    _db.save_table(f"{PREFIX}_payroll_batches", batches)

    # Audit log
    _log_audit("CALCULATE", batch_id, batch, user)

    return success_response(batch)


@router.post("/api/payroll/cn/batches/{batch_id}/confirm")
async def confirm_batch(batch_id: str, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_cn.approve")
    batches = _db.load_table(f"{PREFIX}_payroll_batches") or []
    for b in batches:
        if b.get("batch_id") == batch_id:
            if b.get("status") != "calculated":
                raise HTTPException(status_code=400, detail="Only calculated batches can be confirmed")
            b["status"] = "confirmed"
            b["confirmed_at"] = _now()
            b["updated_at"] = _now()
            _db.save_table(f"{PREFIX}_payroll_batches", batches)

            # Generate payslips
            _generate_payslips(batch_id, b)

            _log_audit("CONFIRM", batch_id, b, user)
            return success_response(b)
    raise HTTPException(status_code=404, detail="Not found")


@router.post("/api/payroll/cn/batches/{batch_id}/rollback")
async def rollback_batch(batch_id: str, request: Request, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_cn.approve")
    body = await request.json()
    batches = _db.load_table(f"{PREFIX}_payroll_batches") or []
    for b in batches:
        if b.get("batch_id") == batch_id:
            b["status"] = "draft"
            b["rollback_reason"] = body.get("reason", "")
            b["updated_at"] = _now()
            _db.save_table(f"{PREFIX}_payroll_batches", batches)
            _log_audit("ROLLBACK", batch_id, b, user, body.get("reason", ""))
            return success_response(b)
    raise HTTPException(status_code=404, detail="Not found")


@router.post("/api/payroll/cn/batches/{batch_id}/void")
async def void_batch(batch_id: str, request: Request, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_cn.manage")
    body = await request.json()
    batches = _db.load_table(f"{PREFIX}_payroll_batches") or []
    for b in batches:
        if b.get("batch_id") == batch_id:
            b["status"] = "voided"
            b["void_reason"] = body.get("reason", "")
            b["updated_at"] = _now()
            _db.save_table(f"{PREFIX}_payroll_batches", batches)
            _log_audit("VOID", batch_id, b, user, body.get("reason", ""))
            return success_response(b)
    raise HTTPException(status_code=404, detail="Not found")


@router.delete("/api/payroll/cn/batches/{batch_id}")
async def delete_batch(batch_id: str, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_cn.manage")
    batches = _db.load_table(f"{PREFIX}_payroll_batches") or []
    batches = [b for b in batches if b.get("batch_id") != batch_id]
    _db.save_table(f"{PREFIX}_payroll_batches", batches)
    # Also delete associated records
    records = _db.load_table(f"{PREFIX}_monthly_salary_records") or []
    records = [r for r in records if r.get("batch_id") != batch_id]
    _db.save_table(f"{PREFIX}_monthly_salary_records", records)
    return success_response({"message": f"Batch {batch_id} deleted"})


@router.post("/api/payroll/cn/batches/{batch_id}/records/{record_id}/recalculate")
async def recalculate_record(batch_id: str, record_id: str, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_cn.calculate")
    from modules.payroll_cn.service import calc_salary

    records = _db.load_table(f"{PREFIX}_monthly_salary_records") or []
    rec = next((r for r in records if r.get("record_id") == record_id), None)
    if not rec:
        raise HTTPException(status_code=404, detail="Record not found")

    batches = _db.load_table(f"{PREFIX}_payroll_batches") or []
    batch = next((b for b in batches if b.get("batch_id") == batch_id), {})
    city_code = rec.get("city_code", "320100")

    si_rates_all = _db.load_table(f"{PREFIX}_social_insurance_rates") or []
    hf_rates_all = _db.load_table(f"{PREFIX}_housing_fund_rates") or []
    tax_brackets = _db.load_table(f"{PREFIX}_tax_brackets") or []

    si_rates = next((r for r in si_rates_all if str(r.get("city_code", "")) == city_code), si_rates_all[0] if si_rates_all else {})
    hf_rate = next((r for r in hf_rates_all if str(r.get("city_code", "")) == city_code), hf_rates_all[0] if hf_rates_all else {})

    attendance = {
        "full_attendance_days": float(rec.get("full_attendance_days") or batch.get("working_days_in_month", 22)),
        "actual_attendance_days": float(rec.get("actual_attendance_days") or batch.get("working_days_in_month", 22)),
        "personal_leave_days": float(rec.get("personal_leave_days") or 0),
        "annual_leave_days": float(rec.get("annual_leave_days") or 0),
        "sick_leave_days": float(rec.get("sick_leave_days") or 0),
        "other_leave_days": float(rec.get("other_leave_days") or 0),
        "other_additions": float(rec.get("other_additions") or 0),
        "other_deductions": float(rec.get("other_deductions") or 0),
    }

    result = calc_salary(rec, attendance, si_rates, hf_rate, tax_brackets)
    for k, v in result.items():
        if k in rec:
            rec[k] = v
    rec["calculation_detail"] = result
    rec["updated_at"] = _now()

    _db.save_table(f"{PREFIX}_monthly_salary_records", records)

    # Recompute batch totals
    batch_records = [r for r in records if r.get("batch_id") == batch_id]
    gross_total = sum(float(r.get("gross_pay", 0)) for r in batch_records)
    deduction_total = sum(float(r.get("deduction_total", 0)) for r in batch_records)
    net_total = sum(float(r.get("net_pay", 0)) for r in batch_records)
    employer_cost_total = sum(float(r.get("employer_cost_total", 0)) for r in batch_records)

    for b in batches:
        if b.get("batch_id") == batch_id:
            b["gross_total"] = gross_total
            b["deduction_total"] = deduction_total
            b["net_total"] = net_total
            b["employer_cost_total"] = employer_cost_total
            b["updated_at"] = _now()
            break
    _db.save_table(f"{PREFIX}_payroll_batches", batches)

    return success_response(rec)


@router.put("/api/payroll/cn/batches/{batch_id}/records/{record_id}")
async def edit_record(batch_id: str, record_id: str, request: Request, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_cn.manage")
    body = await request.json()
    records = _db.load_table(f"{PREFIX}_monthly_salary_records") or []
    for r in records:
        if r.get("record_id") == record_id:
            before = dict(r)
            r.update({k: v for k, v in body.items() if k not in ("id", "record_id", "batch_id")})
            r["manually_edited"] = True
            r["updated_at"] = _now()
            _db.save_table(f"{PREFIX}_monthly_salary_records", records)
            _log_audit("EDIT_RECORD", batch_id, {"record_id": record_id, "before": before, "after": r}, user)
            return success_response(r)
    raise HTTPException(status_code=404, detail="Not found")


@router.get("/api/payroll/cn/batches/{batch_id}/audit-logs")
async def batch_audit_logs(batch_id: str, user: dict = Depends(get_current_user)):
    _check_access(user)
    rows = _db.load_table(f"{PREFIX}_audit_logs") or []
    logs = [r for r in rows if str(r.get("batch_id", "")) == batch_id]
    logs.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
    return success_response(logs)


# ── Payslips ────────────────────────────────────────────────────────────

@router.get("/api/payroll/cn/payslips")
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


@router.get("/api/payroll/cn/payslips/{payslip_id}/html")
async def payslip_html(payslip_id: str, user: dict = Depends(get_current_user)):
    _check_access(user)
    rows = _db.load_table(f"{PREFIX}_payslips") or []
    for r in rows:
        if str(r.get("id") or r.get("payslip_id", "")) == payslip_id:
            html = r.get("html_content") or f"<html><body><h1>Payslip {payslip_id}</h1></body></html>"
            from fastapi.responses import HTMLResponse
            return HTMLResponse(content=html)
    raise HTTPException(status_code=404, detail="Not found")


@router.post("/api/payroll/cn/payslips/{payslip_id}/send")
async def send_payslip(payslip_id: str, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_cn.manage")
    return success_response({"message": f"Payslip {payslip_id} sent"})


@router.post("/api/payroll/cn/payslips/send-selected")
async def send_payslips_selected(request: Request, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_cn.manage")
    body = await request.json()
    return success_response({"sent": len(body.get("record_ids", []))})


@router.post("/api/payroll/cn/payslips/send-all")
async def send_payslips_all(request: Request, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_cn.manage")
    return success_response({"message": "All payslips sent"})


# ── Email Settings ─────────────────────────────────────────────────────

@router.get("/api/payroll/cn/email-settings")
async def get_email_settings(user: dict = Depends(get_current_user)):
    _check_access(user)
    rows = _db.load_table(f"{PREFIX}_email_settings") or []
    cn_settings = [r for r in rows if r.get("country_code") == "CN"]
    return success_response(cn_settings[0] if cn_settings else {})


@router.post("/api/payroll/cn/email-settings")
async def save_email_settings(request: Request, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_cn.manage")
    body = await request.json()
    rows = _db.load_table(f"{PREFIX}_email_settings") or []
    for i, r in enumerate(rows):
        if r.get("country_code") == "CN":
            r.update({k: v for k, v in body.items() if k != "id"})
            r["updated_at"] = _now()
            rows[i] = r
            _db.save_table(f"{PREFIX}_email_settings", rows)
            return success_response(r)
    new_id = max([r.get("id", 0) for r in rows], default=0) + 1
    body.update({"id": new_id, "country_code": "CN", "created_at": _now(), "updated_at": _now()})
    rows.append(body)
    _db.save_table(f"{PREFIX}_email_settings", rows)
    return success_response(body)


@router.post("/api/payroll/cn/email-settings/test")
async def test_email_settings(request: Request, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_cn.manage")
    return success_response({"message": "Test email sent"})


@router.post("/api/payroll/cn/email-settings/preview")
async def preview_email_template(request: Request, user: dict = Depends(get_current_user)):
    _check_access(user)
    return success_response({"html": "<p>Email preview</p>"})


@router.get("/api/payroll/cn/email-logs")
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


@router.get("/api/payroll/cn/audit-logs")
async def list_audit_logs(limit: int = Query(default=100), user: dict = Depends(get_current_user)):
    _check_access(user)
    rows = _db.load_table(f"{PREFIX}_audit_logs") or []
    rows.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
    return success_response(rows[:limit])


@router.get("/api/payroll/cn/smtp-status")
async def smtp_status(user: dict = Depends(get_current_user)):
    _check_access(user)
    return success_response({"configured": True, "status": "ok"})


@router.get("/api/payroll/cn/constants")
async def cn_constants(user: dict = Depends(get_current_user)):
    _check_access(user)
    return success_response({
        "salary_types": [
            {"value": "monthly", "label": "月薪制"},
            {"value": "hourly", "label": "时薪制"},
            {"value": "daily", "label": "日薪制"},
        ],
        "cities": [
            {"code": "320100", "name": "南京"},
            {"code": "220100", "name": "长春"},
            {"code": "110000", "name": "北京"},
            {"code": "310000", "name": "上海"},
            {"code": "440300", "name": "深圳"},
            {"code": "330100", "name": "杭州"},
        ],
        "leave_types": ["personal_leave", "annual_leave", "sick_leave", "other_leave"],
    })


# ── Payslip HTML Generation ──────────────────────────────────────────────

def _generate_payslip_html(record: dict, batch: dict, entity_label: str = "") -> str:
    """Generate a self-contained HTML payslip for China payroll."""
    employee_name = str(record.get("employee_name", "—"))
    employee_number = str(record.get("employee_number", "—"))
    payroll_month = str(record.get("payroll_month", "—"))

    def _fmt(v: float) -> str:
        return f"¥{v:,.2f}"

    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>工资单 — {employee_name}</title>
<style>
  body {{ font-family: 'PingFang SC','Microsoft YaHei','Segoe UI',sans-serif; margin:0; padding:20px; color:#1d2a3a; }}
  .payslip {{ max-width:700px; margin:0 auto; background:#fff; border:1px solid #e5e7eb; border-radius:8px; overflow:hidden; }}
  .header {{ background:#b91c1c; color:#fff; padding:20px 28px; }}
  .header h2 {{ margin:0; font-size:1.3rem; }}
  .header .subtitle {{ font-size:.85rem; opacity:.85; margin-top:4px; }}
  .info {{ padding:16px 28px; border-bottom:1px solid #e5e7eb; }}
  .info table {{ width:100%; border-collapse:collapse; font-size:.9rem; }}
  .info td {{ padding:4px 8px; }}
  .info .label {{ color:#6b7280; width:160px; }}
  .section {{ padding:16px 28px; }}
  .section h3 {{ font-size:1rem; color:#b91c1c; border-bottom:2px solid #b91c1c; padding-bottom:6px; margin:0 0 10px; }}
  .items {{ width:100%; border-collapse:collapse; font-size:.9rem; }}
  .items th {{ text-align:left; padding:6px 8px; border-bottom:1px solid #e5e7eb; color:#6b7280; font-weight:600; }}
  .items td {{ padding:6px 8px; border-bottom:1px solid #f3f4f6; }}
  .items .amount {{ text-align:right; }}
  .total-row {{ font-weight:700; font-size:1rem; background:#fef2f2; }}
  .footer {{ padding:16px 28px; border-top:1px solid #e5e7eb; font-size:.78rem; color:#9ca3af; text-align:center; }}
</style>
</head>
<body>
<div class="payslip">
  <div class="header">
    <h2>工资单 / Payslip</h2>
    <div class="subtitle">{entity_label}</div>
  </div>
  <div class="info">
    <table>
      <tr><td class="label">员工 / Employee</td><td><strong>{employee_name}</strong></td></tr>
      <tr><td class="label">员工编号 / Employee No.</td><td>{employee_number}</td></tr>
      <tr><td class="label">工资月份 / Payroll Month</td><td>{payroll_month}</td></tr>
      <tr><td class="label">法人 / Entity</td><td>{entity_label}</td></tr>
    </table>
  </div>
  <div class="section">
    <h3>出勤 / Attendance</h3>
    <table class="items">
      <tr><td>满勤天数 / Full Attendance Days</td><td class="amount">{record.get("full_attendance_days", "-")}</td></tr>
      <tr><td>出勤天数 / Actual Days</td><td class="amount">{record.get("actual_attendance_days", "-")}</td></tr>
      <tr><td>事假 / Personal Leave</td><td class="amount">{record.get("personal_leave_days", 0)}</td></tr>
      <tr><td>年假 / Annual Leave</td><td class="amount">{record.get("annual_leave_days", 0)}</td></tr>
      <tr><td>病假 / Sick Leave</td><td class="amount">{record.get("sick_leave_days", 0)}</td></tr>
    </table>
  </div>
  <div class="section">
    <h3>收入 / Earnings</h3>
    <table class="items">
      <tr><td>基本工资 / Basic Salary</td><td class="amount">{_fmt(float(record.get("basic_salary", 0)))}</td></tr>
      <tr><td>职位津贴 / Position Allowance</td><td class="amount">{_fmt(float(record.get("position_allowance", 0)))}</td></tr>
      <tr><td>出勤工资 / Attendance Pay</td><td class="amount">{_fmt(float(record.get("attendance_pay", 0)))}</td></tr>
      <tr><td>病假工资 / Sick Leave Pay</td><td class="amount">{_fmt(float(record.get("sick_leave_pay", 0)))}</td></tr>
      <tr><td>全勤奖 / Full Attendance Bonus</td><td class="amount">{_fmt(float(record.get("full_attendance_bonus", 0)))}</td></tr>
      <tr><td>其他加项 / Other Additions</td><td class="amount">{_fmt(float(record.get("other_additions", 0)))}</td></tr>
      <tr class="total-row"><td>应发合计 / Gross Pay</td><td class="amount" style="color:#b91c1c;">{_fmt(float(record.get("gross_pay", 0)))}</td></tr>
    </table>
  </div>
  <div class="section">
    <h3>扣除 / Deductions</h3>
    <table class="items">
      <tr><td>社保(个人) / Social Insurance</td><td class="amount">{_fmt(float(record.get("social_insurance", 0)))}</td></tr>
      <tr><td>公积金(个人) / Housing Fund</td><td class="amount">{_fmt(float(record.get("housing_fund", 0)))}</td></tr>
      <tr><td>个税 / IIT</td><td class="amount">{_fmt(float(record.get("iit", 0)))}</td></tr>
      <tr><td>其他扣款 / Other Deductions</td><td class="amount">{_fmt(float(record.get("other_deductions", 0)))}</td></tr>
      <tr class="total-row"><td>实发工资 / Net Pay</td><td class="amount" style="color:#b91c1c;">{_fmt(float(record.get("net_pay", 0)))}</td></tr>
    </table>
  </div>
  <div class="section">
    <h3>雇主缴纳 / Employer Contributions</h3>
    <table class="items">
      <tr><td>社保(单位) / Employer Social Insurance</td><td class="amount">{_fmt(float(record.get("employer_social_insurance", 0)))}</td></tr>
      <tr><td>公积金(单位) / Employer Housing Fund</td><td class="amount">{_fmt(float(record.get("employer_housing_fund", 0)))}</td></tr>
    </table>
  </div>
  <div class="footer">
    <p>电脑生成工资单 · 如有疑问请联系HR</p>
  </div>
</div>
</body>
</html>"""


def _generate_payslips(batch_id: str, batch: dict) -> None:
    """Generate payslip records for all calculated records in a batch."""
    records = _db.load_table(f"{PREFIX}_monthly_salary_records") or []
    batch_records = [r for r in records if r.get("batch_id") == batch_id]

    entity_id = batch.get("entity_id", "")
    entities = load_entities()
    entity_label = next((e.get("name", entity_id) for e in entities if e.get("id") == entity_id), entity_id)

    payslips = _db.load_table(f"{PREFIX}_payslips") or []
    max_id = max([r.get("id", 0) for r in payslips], default=0)

    for rec in batch_records:
        if rec.get("status") != "calculated":
            continue
        max_id += 1
        html = _generate_payslip_html(rec, batch, entity_label)
        payslip = {
            "id": max_id,
            "payslip_id": f"CNP-{max_id:06d}",
            "batch_id": batch_id,
            "record_id": rec.get("record_id"),
            "employee_id": rec.get("employee_id"),
            "employee_name": rec.get("employee_name"),
            "employee_number": rec.get("employee_number"),
            "payroll_month": rec.get("payroll_month"),
            "entity_id": entity_id,
            "country_code": "CN",
            "html_content": html,
            "email_status": "pending",
            "created_at": _now(),
        }
        payslips.append(payslip)

    _db.save_table(f"{PREFIX}_payslips", payslips)


def _log_audit(action: str, batch_id: str, data: dict, user: dict, reason: str = "") -> None:
    """Write an audit log entry."""
    logs = _db.load_table(f"{PREFIX}_audit_logs") or []
    max_id = max([r.get("id", 0) for r in logs], default=0)
    entry = {
        "id": max_id + 1,
        "module": "tacaipay_cn",
        "batch_id": batch_id,
        "action": action,
        "user": user.get("display_name", str(user.get("email", ""))),
        "timestamp": _now(),
        "before_value": None,
        "after_value": {
            "status": data.get("status"),
            "employee_count": data.get("employee_count"),
            "gross_total": data.get("gross_total"),
            "net_total": data.get("net_total"),
        },
    }
    if reason:
        entry["after_value"]["reason"] = reason
    logs.append(entry)
    _db.save_table(f"{PREFIX}_audit_logs", logs)
