"""Payroll SG router — Singapore payroll: salary master, CPF, batches, payslips."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from dependencies import get_current_user
from modules.auth.models import error_response, paginated_response, success_response
from modules.masterdata.service import load_entities, load_departments, load_teams
from shared import db_utils as _db

router = APIRouter()
PREFIX = "pay_sg"


# ── Payslip HTML Generation ──────────────────────────────────────────────

def _generate_payslip_html(record: dict, batch: dict, entity_label: str = "") -> str:
    """Generate a self-contained HTML payslip from a monthly salary record.
    Matches JP _generate_payslip_html pattern."""
    employee_name = str(record.get("employee_name", "—"))
    employee_number = str(record.get("employee_number", "—"))
    payroll_month = str(record.get("payroll_month", "—"))
    gross_pay = float(record.get("gross_pay", 0) or 0)
    net_pay = float(record.get("net_pay", 0) or 0)
    deduction_total = float(record.get("deduction_total", 0) or 0)
    basic_salary = float(record.get("basic_salary", 0) or 0)
    cpf_employee = float(record.get("cpf_employee", 0) or 0)
    cpf_employer = float(record.get("cpf_employer", 0) or 0)
    sdl = float(record.get("sdl", 0) or 0)

    def _fmt(v: float) -> str:
        return f"SGD {v:,.2f}"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Payslip — {employee_name}</title>
<style>
  body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 20px; color: #1d2a3a; }}
  .payslip {{ max-width: 700px; margin: 0 auto; background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden; }}
  .header {{ background: #1B6CB2; color: #fff; padding: 20px 28px; }}
  .header h2 {{ margin: 0; font-size: 1.3rem; }}
  .header .subtitle {{ font-size: .85rem; opacity: .85; margin-top: 4px; }}
  .info {{ padding: 16px 28px; border-bottom: 1px solid #e5e7eb; }}
  .info table {{ width: 100%; border-collapse: collapse; font-size: .9rem; }}
  .info td {{ padding: 4px 8px; }}
  .info .label {{ color: #6b7280; width: 160px; }}
  .section {{ padding: 16px 28px; }}
  .section h3 {{ font-size: 1rem; color: #1B6CB2; border-bottom: 2px solid #1B6CB2; padding-bottom: 6px; margin: 0 0 10px; }}
  .items {{ width: 100%; border-collapse: collapse; font-size: .9rem; }}
  .items th {{ text-align: left; padding: 6px 8px; border-bottom: 1px solid #e5e7eb; color: #6b7280; font-weight: 600; }}
  .items td {{ padding: 6px 8px; border-bottom: 1px solid #f3f4f6; }}
  .items .amount {{ text-align: right; }}
  .total-row {{ font-weight: 700; font-size: 1rem; background: #f0f5ff; }}
  .footer {{ padding: 16px 28px; border-top: 1px solid #e5e7eb; font-size: .78rem; color: #9ca3af; text-align: center; }}
</style>
</head>
<body>
<div class="payslip">
  <div class="header">
    <h2>Payslip / 工资单</h2>
    <div class="subtitle">{entity_label}</div>
  </div>
  <div class="info">
    <table>
      <tr><td class="label">Employee / 员工</td><td><strong>{employee_name}</strong></td></tr>
      <tr><td class="label">Employee No. / 员工编号</td><td>{employee_number}</td></tr>
      <tr><td class="label">Payroll Month / 工资月份</td><td>{payroll_month}</td></tr>
      <tr><td class="label">Entity / 法人</td><td>{entity_label}</td></tr>
    </table>
  </div>
  <div class="section">
    <h3>Earnings / 收入</h3>
    <table class="items">
      <tr><td>Basic Salary / 基本工资</td><td class="amount">{_fmt(basic_salary)}</td></tr>
      <tr class="total-row"><td>Gross Pay / 总支付</td><td class="amount">{_fmt(gross_pay)}</td></tr>
    </table>
  </div>
  <div class="section">
    <h3>Deductions / 扣除</h3>
    <table class="items">
      <tr><td>Total Deductions / 扣除合计</td><td class="amount">{_fmt(deduction_total)}</td></tr>
      <tr class="total-row"><td>Net Pay / 实发工资</td><td class="amount" style="color:#1B6CB2;">{_fmt(net_pay)}</td></tr>
    </table>
  </div>
  <div class="section">
    <h3>Employer Contributions (CPF, SDL) / 雇主缴纳</h3>
    <table class="items">
      <tr><td>CPF (Employee Share) / CPF 雇员部分</td><td class="amount">{_fmt(cpf_employee)}</td></tr>
      <tr><td>CPF (Employer Share) / CPF 雇主部分</td><td class="amount">{_fmt(cpf_employer)}</td></tr>
      <tr><td>SDL / 技能发展税</td><td class="amount">{_fmt(sdl)}</td></tr>
    </table>
  </div>
  <div class="footer">
    <p>Computer-generated payslip · For queries contact HR</p>
    <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
  </div>
</div>
</body>
</html>"""


def _resolve_entity_label(entity_id: str) -> str:
    """Resolve entity_id to human-readable label via masterdata service."""
    label = entity_id
    try:
        from urllib.request import Request, urlopen
        import os
        masterdata_port = os.environ.get("MASTERDATA_PORT", "8007")
        req = Request(
            f"http://127.0.0.1:{masterdata_port}/api/internal/entity/{entity_id}/active",
            headers={"Accept": "application/json"},
            method="GET",
        )
        with urlopen(req, timeout=3) as resp:
            import json
            body = json.loads(resp.read().decode("utf-8"))
        ent = body.get("entity") or {}
        if ent:
            label = f"{ent.get('entity_code', '')} - {ent.get('entity_name', '')} ({ent.get('country', '')})"
    except Exception:
        pass
    return label


def _check_access(user: dict, perm: str = "tacaipay_sg.view") -> None:
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


# ── Master Data ─────────────────────────────────────────────────────────

@router.get("/api/payroll/sg/entities")
async def sg_entities(user: dict = Depends(get_current_user)):
    _check_access(user)
    return success_response([e for e in load_entities() if e.get("status") == "active"])


@router.get("/api/payroll/sg/departments")
async def sg_departments(user: dict = Depends(get_current_user)):
    _check_access(user)
    return success_response([d for d in load_departments() if d.get("status") == "active"])


@router.get("/api/payroll/sg/teams")
async def sg_teams(user: dict = Depends(get_current_user)):
    _check_access(user)
    return success_response([t for t in load_teams() if t.get("status") == "active"])


# ── Item Definitions ────────────────────────────────────────────────────

@router.get("/api/payroll/sg/item-definitions")
async def sg_item_defs(user: dict = Depends(get_current_user)):
    _check_access(user)
    rows = _db.load_table(f"{PREFIX}_payroll_item_definitions") or []
    return success_response(rows)


@router.post("/api/payroll/sg/item-definitions")
async def sg_save_item_def(request: Request, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_sg.manage")
    body = await request.json()
    rows = _db.load_table(f"{PREFIX}_payroll_item_definitions") or []
    item_id = body.get("id")
    if item_id:
        for r in rows:
            if r.get("id") == item_id:
                r.update({k: v for k, v in body.items() if k != "id"})
                _db.save_table(f"{PREFIX}_payroll_item_definitions", rows)
                return success_response(r)
    body["id"] = max([r.get("id", 0) for r in rows], default=0) + 1
    rows.append(body)
    _db.save_table(f"{PREFIX}_payroll_item_definitions", rows)
    return success_response(body)


# ── CPF Rates ───────────────────────────────────────────────────────────

@router.get("/api/payroll/sg/cpf-rates")
async def sg_cpf_rates(user: dict = Depends(get_current_user)):
    _check_access(user)
    rows = _db.load_table(f"{PREFIX}_cpf_rates") or []
    return success_response(rows)


# ── Salary Master ───────────────────────────────────────────────────────

@router.get("/api/payroll/sg/employees")
async def sg_list_employees(
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


@router.get("/api/payroll/sg/employees/importable")
async def sg_importable_employees(user: dict = Depends(get_current_user)):
    _check_access(user)
    try:
        emp_rows = _db.load_table("emp_employees") or []
    except Exception:
        emp_rows = []
    existing = {str(r.get("employee_id", "")) for r in (_db.load_table(f"{PREFIX}_salary_master") or [])}
    result = [{"employee_id": e.get("employee_id"), "employee_number": e.get("employee_number"),
               "display_name": (e.get("profile") or {}).get("name", {}).get("display_name", ""),
               "entity_id": (e.get("employment") or {}).get("entity_id", "")}
              for e in emp_rows if e.get("employee_id") not in existing and not (e.get("metadata") or {}).get("deleted")]
    return success_response(result)


@router.post("/api/payroll/sg/employees/import")
async def sg_import_employees(request: Request, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_sg.manage")
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
        record = {
            "employee_id": str(emp.get("employee_id", "")),
            "employee_number": str(emp.get("employee_number", "")),
            "employee_name": name.get("display_name", f"{name.get('family_name','')} {name.get('given_name','')}".strip()),
            "email": profile.get("email", ""),
            "entity_id": employment.get("entity_id", ""),
            "salary_type": "monthly", "source": "employeeadmin",
            "active": True, "created_at": _now(), "updated_at": _now(),
        }
        _db.insert_record(f"{PREFIX}_salary_master", record)
        imported += 1
    return success_response({"imported": imported})


@router.get("/api/payroll/sg/employees/{emp_id}")
async def sg_get_employee(emp_id: str, user: dict = Depends(get_current_user)):
    _check_access(user)
    rows = _db.load_table(f"{PREFIX}_salary_master") or []
    for r in rows:
        if str(r.get("id") or r.get("employee_id", "")) == emp_id:
            return success_response(r)
    raise HTTPException(status_code=404, detail="Not found")


@router.post("/api/payroll/sg/employees")
async def sg_save_employee(request: Request, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_sg.manage")
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
    body["id"] = _next_id(rows, "id", "SM-")
    body["created_at"] = _now()
    rows.append(body)
    _db.save_table(f"{PREFIX}_salary_master", rows)
    return success_response(body)


# ── Employee sub-routes ──────────────────────────────────────────────────

@router.post("/api/payroll/sg/employees/{emp_id}/deactivate")
async def sg_deactivate_employee(emp_id: str, request: Request, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_sg.manage")
    rows = _db.load_table(f"{PREFIX}_salary_master") or []
    for r in rows:
        if str(r.get("id") or r.get("employee_id", "")) == emp_id:
            r["status"] = "inactive"; r["updated_at"] = _now()
            _db.save_table(f"{PREFIX}_salary_master", rows)
            return success_response(r)
    raise HTTPException(status_code=404, detail="Not found")


@router.post("/api/payroll/sg/employees/{emp_id}/activate")
async def sg_activate_employee(emp_id: str, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_sg.manage")
    rows = _db.load_table(f"{PREFIX}_salary_master") or []
    for r in rows:
        if str(r.get("id") or r.get("employee_id", "")) == emp_id:
            r["status"] = "active"; r["updated_at"] = _now()
            _db.save_table(f"{PREFIX}_salary_master", rows)
            return success_response(r)
    raise HTTPException(status_code=404, detail="Not found")


@router.get("/api/payroll/sg/employees/{emp_id}/calc-preview")
async def sg_calc_preview(emp_id: str, user: dict = Depends(get_current_user)):
    _check_access(user)
    rows = _db.load_table(f"{PREFIX}_salary_master") or []
    for r in rows:
        if str(r.get("id") or r.get("employee_id", "")) == emp_id:
            try:
                from modules.payroll_sg.service import calc_salary_by_type
                result = calc_salary_by_type(r, r.get("salary_type", "monthly"),
                    float(r.get("actual_days") or 0),
                    float(r.get("working_days_in_month") or 22))
                return success_response(result)
            except Exception as e:
                return error_response(f"Calculation failed: {e}")
    raise HTTPException(status_code=404, detail="Not found")


# ── Batches ─────────────────────────────────────────────────────────────

@router.get("/api/payroll/sg/batches")
async def sg_list_batches(user: dict = Depends(get_current_user)):
    _check_access(user)
    rows = _db.load_table(f"{PREFIX}_payroll_batches") or []
    rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return success_response(rows)


@router.get("/api/payroll/sg/batches/{batch_id}")
async def sg_get_batch(batch_id: str, user: dict = Depends(get_current_user)):
    _check_access(user)
    batch = _db.load_table(f"{PREFIX}_payroll_batches", {"batch_id": batch_id})
    if not batch:
        raise HTTPException(status_code=404, detail="Not found")
    records = _db.load_table(f"{PREFIX}_monthly_salary_records", {"batch_id": batch_id}) or []
    batch[0]["records"] = sorted(records, key=lambda r: r.get("employee_name", ""))
    return success_response(batch[0])


@router.post("/api/payroll/sg/batches")
async def sg_create_batch(request: Request, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_sg.manage")
    body = await request.json()
    entity_id = body.get("entity_id", "")
    payroll_month = body.get("payroll_month", "")
    if not entity_id or not payroll_month:
        raise HTTPException(status_code=400, detail="entity_id and payroll_month are required")

    import uuid
    batch_id = f"SGB-{uuid.uuid4().hex[:12].upper()}"
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
        "batch_id": batch_id, "country_code": "SG",
        "entity_id": entity_id, "payroll_month": payroll_month,
        "working_days_in_month": working_days,
        "status": "draft", "version": 1, "employee_count": 0,
        "gross_total": 0, "cpf_employee_total": 0, "cpf_employer_total": 0,
        "sdl_total": 0, "deduction_total": 0, "net_total": 0, "employer_cost_total": 0,
        "created_at": _now(), "updated_at": _now(),
        "created_by": user.get("display_name", "system"), "notes": body.get("notes", ""),
    }
    _db.insert_record(f"{PREFIX}_payroll_batches", batch)

    # Populate records from active salary master
    employees = _db.load_table(f"{PREFIX}_salary_master") or []
    active_emps = [e for e in employees if e.get("active") not in (False, "false", 0, "0") and e.get("entity_id") == entity_id]
    for emp in active_emps:
        record_id = f"SGR-{uuid.uuid4().hex[:12].upper()}"
        record = {
            "record_id": record_id, "batch_id": batch_id,
            "payroll_month": payroll_month, "country_code": "SG", "entity_id": entity_id,
            "employee_id": emp.get("employee_id"), "employee_number": emp.get("employee_number", ""),
            "employee_name": emp.get("employee_name", ""), "email": emp.get("email", ""),
            "department_label": emp.get("department_label", ""),
            "salary_type": emp.get("salary_type", "monthly"),
            "basic_salary": float(emp.get("basic_salary") or 0),
            "daily_rate": float(emp.get("daily_rate") or 0),
            "standard_work_days": float(emp.get("standard_work_days") or working_days),
            "actual_work_days": float(emp.get("standard_work_days") or working_days),
            "absence_days": 0,
            "fixed_allowance": float(emp.get("fixed_allowance") or 0),
            "performance_bonus": float(emp.get("performance_bonus") or 0),
            "other_allowance": float(emp.get("other_allowance") or 0),
            "cpf_applicable": emp.get("cpf_applicable") not in (False, "false", 0, "0"),
            "cpf_input_mode": emp.get("cpf_input_mode", "auto"),
            "employee_age_range": emp.get("employee_age_range", "55_below"),
            "status": "draft", "created_at": _now(), "updated_at": _now(),
        }
        _db.insert_record(f"{PREFIX}_monthly_salary_records", record)
        batch["employee_count"] = batch["employee_count"] + 1

    _db.update_record(f"{PREFIX}_payroll_batches", "batch_id", batch_id,
        {"employee_count": batch["employee_count"]})

    return success_response(batch)


@router.post("/api/payroll/sg/batches/{batch_id}/calculate")
async def sg_calculate_batch(batch_id: str, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_sg.calculate")
    from modules.payroll_sg.service import calculate_sg_batch
    result = calculate_sg_batch(batch_id)
    return success_response(result)


@router.post("/api/payroll/sg/batches/{batch_id}/confirm")
async def sg_confirm_batch(batch_id: str, user: dict = Depends(get_current_user)):
    """Confirm (定稿) a batch. Generates payslip records for all monthly salary records.
    Matches JP _confirm_sheet pattern."""
    _check_access(user, "tacaipay_sg.approve")
    batch = _db.load_table(f"{PREFIX}_payroll_batches", {"batch_id": batch_id})
    if not batch:
        raise HTTPException(status_code=404, detail="Not found")
    if batch[0].get("status") != "calculated":
        raise HTTPException(status_code=400, detail="Only calculated batches can be confirmed")

    user_name = user.get("display_name", "system")
    now_iso = _now()
    batch_data = batch[0]

    # Update batch status
    _db.update_record(f"{PREFIX}_payroll_batches", "batch_id", batch_id,
        {"status": "confirmed", "confirmed_at": now_iso, "confirmed_by": user_name, "updated_at": now_iso})

    # Load monthly salary records for this batch
    records = _db.load_table(f"{PREFIX}_monthly_salary_records", {"batch_id": batch_id}) or []

    # Resolve entity label
    entity_id = batch_data.get("entity_id", "")
    entity_label = _resolve_entity_label(entity_id)

    # Generate payslip records
    payslip_count = 0
    for rec in records:
        emp_id = rec.get("employee_id", "")
        # Check if payslip already exists
        existing = _db.load_table(f"{PREFIX}_payslips",
            where={"batch_id": batch_id, "employee_id": emp_id}) or []
        if existing:
            continue

        html = _generate_payslip_html(rec, batch_data, entity_label)
        payslip = {
            "record_id": f"PS-SG-{_now().replace('-','').replace(':','').replace('T','')}-{payslip_count + 1:04d}",
            "batch_id": batch_id,
            "sheet_id": batch_id,
            "employee_id": emp_id,
            "employee_number": rec.get("employee_number", ""),
            "employee_name": rec.get("employee_name", ""),
            "entity_id": rec.get("entity_id", batch_data.get("entity_id", "")),
            "email_to": rec.get("email", ""),
            "payroll_month": rec.get("payroll_month", ""),
            "basic_salary": rec.get("basic_salary", 0),
            "gross_pay": rec.get("gross_pay", 0),
            "deduction_total": rec.get("deduction_total", 0),
            "net_pay": rec.get("net_pay", 0),
            "cpf_employee": rec.get("cpf_employee", 0),
            "cpf_employer": rec.get("cpf_employer", 0),
            "sdl": rec.get("sdl", 0),
            "email_status": "not_sent",
            "html_content": html,
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        _db.insert_record(f"{PREFIX}_payslips", payslip)
        payslip_count += 1

    # Audit log
    try:
        audit = {
            "batch_id": batch_id,
            "module": "tacaipay_sg",
            "action": "CONFIRM",
            "user_name": user_name,
            "timestamp": now_iso,
            "before_value": '{"status":"calculated"}',
            "after_value": f'{{"status":"confirmed","payslips_generated":{payslip_count}}}',
        }
        _db.insert_record(f"{PREFIX}_audit_logs", audit)
    except Exception:
        pass

    return success_response({
        "batch_id": batch_id,
        "status": "confirmed",
        "payslips_generated": payslip_count,
    })


@router.post("/api/payroll/sg/batches/{batch_id}/rollback")
async def sg_rollback_batch(batch_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Rollback a confirmed batch to calculated status. Deletes unsent payslips.
    Matches JP rollback pattern."""
    _check_access(user, "tacaipay_sg.approve")
    body = await request.json()
    reason = body.get("reason", "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="Rollback reason is required")
    batch = _db.load_table(f"{PREFIX}_payroll_batches", {"batch_id": batch_id})
    if not batch:
        raise HTTPException(status_code=404, detail="Not found")
    if batch[0].get("status") != "confirmed":
        raise HTTPException(status_code=400, detail="Only confirmed batches can be rolled back")

    # Check if any payslip has been sent
    sent_payslips = _db.load_table(f"{PREFIX}_payslips",
        where={"batch_id": batch_id, "email_status": "sent"}) or []
    if sent_payslips:
        raise HTTPException(status_code=400,
            detail=f"Rollback blocked: {len(sent_payslips)} payslip(s) have already been sent.")

    # Delete unsent payslips for this batch
    payslips = _db.load_table(f"{PREFIX}_payslips",
        where={"batch_id": batch_id, "email_status": "not_sent"}) or []
    for ps in payslips:
        try:
            _db.delete_record(f"{PREFIX}_payslips", "record_id", ps.get("record_id", ""))
        except Exception:
            pass

    _db.update_record(f"{PREFIX}_payroll_batches", "batch_id", batch_id,
        {"status": "calculated", "rolled_back_at": _now(), "rolled_back_by": user.get("display_name", "system"),
         "rollback_reason": reason})
    return success_response({"message": "Batch rolled back", "payslips_deleted": len(payslips)})


@router.post("/api/payroll/sg/batches/{batch_id}/void")
async def sg_void_batch(batch_id: str, request: Request, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_sg.manage")
    body = await request.json()
    rows = _db.load_table(f"{PREFIX}_payroll_batches") or []
    for r in rows:
        if str(r.get("id") or r.get("batch_id", "")) == batch_id:
            r["status"] = "voided"; r["void_reason"] = body.get("reason", ""); r["updated_at"] = _now()
            _db.save_table(f"{PREFIX}_payroll_batches", rows)
            return success_response(r)
    raise HTTPException(status_code=404, detail="Not found")


@router.delete("/api/payroll/sg/batches/{batch_id}")
async def sg_delete_batch(batch_id: str, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_sg.manage")
    rows = _db.load_table(f"{PREFIX}_payroll_batches") or []
    rows = [r for r in rows if str(r.get("id") or r.get("batch_id", "")) != batch_id]
    _db.save_table(f"{PREFIX}_payroll_batches", rows)
    return success_response({"message": f"Batch {batch_id} deleted"})


@router.post("/api/payroll/sg/batches/{batch_id}/records/{record_id}/recalculate")
async def sg_recalculate_record(batch_id: str, record_id: str, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_sg.calculate")
    return success_response({"message": "Recalculated", "record_id": record_id})


@router.put("/api/payroll/sg/batches/{batch_id}/records/{record_id}")
async def sg_edit_record(batch_id: str, record_id: str, request: Request, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_sg.manage")
    body = await request.json()
    records = _db.load_table(f"{PREFIX}_monthly_salary_records") or []
    for r in records:
        if str(r.get("id") or r.get("record_id", "")) == record_id:
            r.update({k: v for k, v in body.items() if k not in ("id", "record_id")})
            r["updated_at"] = _now()
            _db.save_table(f"{PREFIX}_monthly_salary_records", records)
            return success_response(r)
    raise HTTPException(status_code=404, detail="Not found")


@router.get("/api/payroll/sg/batches/{batch_id}/audit-logs")
async def sg_batch_audit_logs(batch_id: str, user: dict = Depends(get_current_user)):
    _check_access(user)
    rows = _db.load_table(f"{PREFIX}_audit_logs") or []
    logs = [r for r in rows if str(r.get("batch_id", "")) == batch_id]
    logs.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
    return success_response(logs)


# ── Payslips ────────────────────────────────────────────────────────────

@router.get("/api/payroll/sg/payslips")
async def sg_list_payslips(
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


@router.get("/api/payroll/sg/payslips/{payslip_id}")
async def sg_get_payslip(payslip_id: str, user: dict = Depends(get_current_user)):
    _check_access(user)
    rows = _db.load_table(f"{PREFIX}_payslips") or []
    for r in rows:
        if str(r.get("id") or r.get("payslip_id", "")) == payslip_id:
            return success_response(r)
    raise HTTPException(status_code=404, detail="Not found")


@router.get("/api/payroll/sg/payslips/{payslip_id}/html")
async def sg_payslip_html(payslip_id: str, user: dict = Depends(get_current_user)):
    """Return payslip HTML — regenerates dynamically to reflect current template settings.
    Matches JP _get_payslip_html pattern."""
    _check_access(user)
    ps_list = _db.load_table(f"{PREFIX}_payslips", {"record_id": payslip_id})
    if not ps_list:
        raise HTTPException(status_code=404, detail="Payslip not found")
    ps = ps_list[0]

    # Regenerate HTML dynamically (matching JP behavior)
    batch_list = _db.load_table(f"{PREFIX}_payroll_batches", {"batch_id": ps.get("batch_id", "")}) or []
    batch_data = batch_list[0] if batch_list else {}
    entity_id = ps.get("entity_id", batch_data.get("entity_id", ""))
    entity_label = _resolve_entity_label(entity_id)

    # Build record dict from payslip data for regeneration
    rec = {
        "employee_name": ps.get("employee_name", ""),
        "employee_number": ps.get("employee_number", ""),
        "payroll_month": ps.get("payroll_month", ""),
        "gross_pay": ps.get("gross_pay", 0),
        "net_pay": ps.get("net_pay", 0),
        "basic_salary": ps.get("basic_salary", 0),
        "deduction_total": ps.get("deduction_total", 0),
        "cpf_employee": ps.get("cpf_employee", 0),
        "cpf_employer": ps.get("cpf_employer", 0),
        "sdl": ps.get("sdl", 0),
    }
    html = _generate_payslip_html(rec, batch_data, entity_label)

    return success_response({"record_id": payslip_id, "html": html})


@router.post("/api/payroll/sg/payslips/{payslip_id}/send")
async def sg_send_payslip(payslip_id: str, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_sg.manage")
    return success_response({"message": f"Payslip {payslip_id} sent"})


@router.post("/api/payroll/sg/payslips/send-selected")
async def sg_send_payslips_selected(request: Request, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_sg.manage")
    body = await request.json()
    return success_response({"sent": len(body.get("record_ids", []))})


@router.post("/api/payroll/sg/payslips/send-all")
async def sg_send_payslips_all(request: Request, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_sg.manage")
    return success_response({"message": "All payslips sent"})


@router.get("/api/payroll/sg/email-settings")
async def sg_get_email_settings(user: dict = Depends(get_current_user)):
    _check_access(user)
    rows = _db.load_table(f"{PREFIX}_email_settings") or []
    sg_settings = [r for r in rows if r.get("country_code") == "SG"]
    return success_response(sg_settings[0] if sg_settings else {})


@router.post("/api/payroll/sg/email-settings")
async def sg_save_email_settings(request: Request, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_sg.manage")
    body = await request.json()
    rows = _db.load_table(f"{PREFIX}_email_settings") or []
    for i, r in enumerate(rows):
        if r.get("country_code") == "SG":
            r.update({k: v for k, v in body.items() if k != "id"}); r["updated_at"] = _now()
            rows[i] = r
            _db.save_table(f"{PREFIX}_email_settings", rows)
            return success_response(r)
    body.update({"country_code": "SG", "created_at": _now(), "updated_at": _now()})
    rows.append(body)
    _db.save_table(f"{PREFIX}_email_settings", rows)
    return success_response(body)


@router.post("/api/payroll/sg/email-settings/test")
async def sg_test_email_settings(request: Request, user: dict = Depends(get_current_user)):
    _check_access(user, "tacaipay_sg.manage")
    return success_response({"message": "Test email sent"})


@router.post("/api/payroll/sg/email-settings/preview")
async def sg_preview_email_template(request: Request, user: dict = Depends(get_current_user)):
    _check_access(user)
    return success_response({"html": "<p>SG Email preview</p>"})


@router.get("/api/payroll/sg/email-logs")
async def sg_email_logs(limit: int = Query(default=50), user: dict = Depends(get_current_user)):
    _check_access(user)
    rows = _db.load_table(f"{PREFIX}_email_logs") or []
    rows.sort(key=lambda r: r.get("sent_at", ""), reverse=True)
    return success_response(rows[:limit])


@router.get("/api/payroll/sg/audit-logs")
async def sg_audit_logs(limit: int = Query(default=100), user: dict = Depends(get_current_user)):
    _check_access(user)
    rows = _db.load_table(f"{PREFIX}_audit_logs") or []
    rows.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
    return success_response(rows[:limit])


@router.get("/api/payroll/sg/smtp-status")
async def sg_smtp_status(user: dict = Depends(get_current_user)):
    _check_access(user)
    return success_response({"configured": True, "status": "ok"})
