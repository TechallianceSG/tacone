"""Payroll SG — Singapore payroll calculation engine.

CPF contribution rates, SDL calculation, monthly and daily salary types.
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

# Ensure shared is importable
_shared_path = Path(__file__).resolve().parents[2] / 'shared'
if str(_shared_path) not in sys.path:
    sys.path.insert(0, str(_shared_path))

from shared import db_utils as _db

# CPF contribution rates (standard)
CPF_RATES = {
    "55_below": {"employee": 0.20, "employer": 0.17},
    "55_60":    {"employee": 0.13, "employer": 0.13},
    "60_65":    {"employee": 0.075, "employer": 0.09},
    "65_above": {"employee": 0.05, "employer": 0.075},
}

CPF_OW_CEILING = 6000  # Ordinary Wage ceiling (SGD)
SDL_CAP = 4500          # SDL wage cap (SGD)
SDL_RATE = 0.0025       # 0.25%


def calc_allowances(emp: dict) -> float:
    """Calculate total allowances for SG employee."""
    return (
        float(emp.get("fixed_allowance") or 0) +
        float(emp.get("performance_bonus") or 0) +
        float(emp.get("other_allowance") or 0)
    )


def compute_sg_working_days(year_month: str) -> int:
    """Count Mon-Fri working days in a given month (YYYY-MM)."""
    from datetime import date, timedelta
    try:
        y, m = year_month.split("-")
        year, month = int(y), int(m)
    except (ValueError, TypeError):
        return 22  # fallback
    first = date(year, month, 1)
    if month == 12:
        last = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last = date(year, month + 1, 1) - timedelta(days=1)
    days = 0
    current = first
    while current <= last:
        if current.weekday() < 5:  # Mon=0, Fri=4
            days += 1
        current += timedelta(days=1)
    return days


def get_cpf_age_range(employee_id: str, emp_record: dict | None = None) -> str:
    """Determine CPF age range based on employee's date of birth."""
    try:
        if emp_record and (emp_record.get("date_of_birth") or (emp_record.get("profile") or {}).get("date_of_birth")):
            dob = emp_record.get("date_of_birth") or (emp_record.get("profile") or {}).get("date_of_birth")
        else:
            emp_rows = _db.load_table("emp_employees", where={"employee_id": employee_id})
            if emp_rows:
                dob = (emp_rows[0].get("profile") or {}).get("date_of_birth", "")
            else:
                return "55_below"
        if not dob:
            return "55_below"
        if isinstance(dob, str):
            dob_date = date.fromisoformat(dob[:10]) if hasattr(date, 'fromisoformat') else datetime.strptime(dob[:10], "%Y-%m-%d").date()
        else:
            dob_date = dob
        today = date.today()
        age = today.year - dob_date.year - ((today.month, today.day) < (dob_date.month, dob_date.day))
        if age >= 65:
            return "65_above"
        elif age >= 60:
            return "60_65"
        elif age >= 55:
            return "55_60"
        else:
            return "55_below"
    except Exception:
        return "55_below"


def calc_salary_by_type(emp: dict, salary_type: str, actual_days: float = 0.0,
                        working_days_in_month: float = 22.0) -> dict:
    """Calculate SG payroll for an employee.

    Supports 'monthly' and 'daily' salary types with CPF + SDL deductions.
    """
    messages: list = []

    # ── Base pay ──
    if salary_type == "monthly":
        basic = float(emp.get("monthly_base") or emp.get("basic_salary") or 0)
        wd = max(float(working_days_in_month or 22), 1)
        ad = actual_days or wd
        base = round(basic * ad / wd, 2)
        messages.append(f"Monthly: SGD {basic:,.2f} × {ad:.0f}/{wd:.0f} days = SGD {base:,.2f}")

    elif salary_type == "daily":
        ad = actual_days or 1
        rate = float(emp.get("daily_rate") or 0)
        base = round(rate * ad, 2)
        messages.append(f"Daily: SGD {rate:,.2f} × {ad:.0f} days = SGD {base:,.2f}")

    else:
        base = float(emp.get("monthly_base") or emp.get("basic_salary") or 0)
        messages.append(f"Default (monthly): SGD {base:,.2f}")

    # ── Allowances ──
    allowances = calc_allowances(emp)
    gross_pay = base + allowances

    # ── CPF ──
    cpf_eligible = emp.get("cpf_eligible") not in (False, "false", 0, "0")
    age_range = get_cpf_age_range(emp.get("employee_id", ""), emp)
    cpf_employee = 0.0
    cpf_employer = 0.0

    if cpf_eligible:
        if emp.get("cpf_override"):
            cpf_employee = float(emp.get("cpf_employee_override", 0) or 0)
            cpf_employer = float(emp.get("cpf_employer_override", 0) or 0)
            messages.append(f"CPF: Manual override")
        else:
            computable = min(base, CPF_OW_CEILING)
            rates = CPF_RATES.get(age_range, CPF_RATES["55_below"])
            cpf_employee = round(computable * rates["employee"], 2)
            cpf_employer = round(computable * rates["employer"], 2)
            messages.append(f"CPF: Age {age_range} — Computable SGD {computable:,.2f} × EE {rates['employee']:.0%} = SGD {cpf_employee:,.2f}")
    else:
        messages.append("CPF: Not applicable (foreigner / exempt)")

    # ── SDL (雇主强制，员工无需支付）──
    sdl = round(min(base, float(SDL_CAP)) * SDL_RATE, 2)

    # ── SG has no paycheck deductions (CPF is retirement savings, SDL is employer-only) ──
    deduction_total = 0
    net_pay = gross_pay

    # ── Employer cost ──
    employer_cost = cpf_employer + sdl

    return {
        "salary_type": salary_type,
        "base_pay": round(base, 2),
        "allowance_total": round(allowances, 2),
        "gross_pay": round(gross_pay, 2),
        "cpf_employee": cpf_employee,
        "cpf_employer": cpf_employer,
        "sdl": sdl,
        "cpf_age_range": age_range,
        "deduction_total": round(deduction_total, 2),
        "net_pay": round(net_pay, 2),
        "employer_cost_total": round(employer_cost, 2),
        "standard_work_days": float(working_days_in_month or 22),
        "actual_days": actual_days or float(working_days_in_month or 22),
        "messages": messages,
    }


def calculate_sg_batch(batch_id: str) -> dict:
    """Calculate all salary records for a given batch."""
    from shared import db_utils as _db

    batches = _db.load_table("pay_sg_payroll_batches", {"batch_id": batch_id})
    if not batches:
        raise ValueError(f"Batch not found: {batch_id}")

    batch = batches[0]
    if batch.get("status") not in ("draft", "calculated"):
        raise ValueError(f"Cannot calculate batch with status '{batch.get('status')}'")

    working_days = float(batch.get("working_days_in_month") or 22)
    records = _db.load_table("pay_sg_monthly_salary_records", {"batch_id": batch_id}) or []

    gross_total = cpf_emp_total = cpf_er_total = sdl_total = 0.0
    deduction_total = net_total = employer_total = 0.0

    for rec in records:
        salary_type = (rec.get("salary_type") or "monthly").strip()
        actual_days = float(rec.get("actual_work_days") or rec.get("standard_work_days") or working_days)

        emp = {
            **rec,
            "absence_days": float(rec.get("absence_days") or 0),
            "cpf_employee_manual": float(rec.get("cpf_employee_manual") or 0),
            "cpf_employer_manual": float(rec.get("cpf_employer_manual") or 0),
        }
        result = calc_salary_by_type(emp, salary_type, actual_days, working_days)

        update_data = {
            "base_pay_calculated": result["base_pay"],
            "allowance_total": result["allowance_total"],
            "gross_pay": result["gross_pay"],
            "cpf_employee": result["cpf_employee"],
            "cpf_employer": result["cpf_employer"],
            "sdl": result["sdl"],
            "deduction_total": result["deduction_total"],
            "net_pay": result["net_pay"],
            "employer_cost_total": result["employer_cost_total"],
            "calculation_detail": json.dumps(result),
            "calculation_messages": json.dumps(result.get("messages", [])),
            "status": "calculated",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        _db.update_record("pay_sg_monthly_salary_records", "record_id", rec["record_id"], update_data)

        gross_total += result["gross_pay"]
        cpf_emp_total += result["cpf_employee"]
        cpf_er_total += result["cpf_employer"]
        sdl_total += result["sdl"]
        deduction_total += result["deduction_total"]
        net_total += result["net_pay"]
        employer_total += result["employer_cost_total"]

    batch_update = {
        "status": "calculated",
        "gross_total": round(gross_total, 2),
        "cpf_employee_total": round(cpf_emp_total, 2),
        "cpf_employer_total": round(cpf_er_total, 2),
        "sdl_total": round(sdl_total, 2),
        "deduction_total": round(deduction_total, 2),
        "net_total": round(net_total, 2),
        "employer_cost_total": round(employer_total, 2),
        "employee_count": len(records),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _db.update_record("pay_sg_payroll_batches", "batch_id", batch_id, batch_update)

    updated_batch = _db.load_table("pay_sg_payroll_batches", {"batch_id": batch_id})[0]
    updated_records = _db.load_table("pay_sg_monthly_salary_records", {"batch_id": batch_id})
    updated_batch["records"] = updated_records
    return updated_batch
