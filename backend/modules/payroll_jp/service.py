"""Payroll JP — salary calculation engine (日本薪资计算引擎).

Extracted from backend/services/payroll/jp/app.py.
Supports 5 salary types per Japanese labor law:
  - monthly (月給制), hourly (時給制), daily (日給制)
  - monthly_fixed_ot (月給＋固定残業), monthly_hour (月給＋時給併用)

Includes social insurance, income tax withholding, and employer cost calculations.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from shared import db_utils as _db

PREFIX = "pay_jp"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Fiscal Age (介護保険用) ────────────────────────────────────────────────

def calc_fiscal_age(employee_id: str, emp_record: dict | None = None) -> int | None:
    """Calculate age as of April 1 of the current fiscal year (for nursing care insurance).

    Reads date_of_birth from emp_employees.
    """
    try:
        if emp_record and emp_record.get("date_of_birth"):
            dob = emp_record["date_of_birth"]
        else:
            emp_rows = _db.load_table("emp_employees", where={"employee_id": employee_id})
            dob = (emp_rows[0].get("profile") or {}).get("date_of_birth") if emp_rows else None
            if not dob:
                dob = (emp_rows[0].get("date_of_birth") if emp_rows else None)
        if not dob:
            return None
        if isinstance(dob, str):
            from datetime import date as _date
            dob_date = _date.fromisoformat(dob[:10])
        else:
            dob_date = dob
        today = datetime.now(timezone.utc).date()
        fiscal_year_start = _date(today.year, 4, 1)
        if today < fiscal_year_start:
            fiscal_year_start = _date(today.year - 1, 4, 1)
        age = fiscal_year_start.year - dob_date.year - (
            (fiscal_year_start.month, fiscal_year_start.day) < (dob_date.month, dob_date.day)
        )
        return age
    except Exception:
        return None


# ── Insurance Rate Lookup ─────────────────────────────────────────────────

def lookup_insurance_rate(rate_type: str, prefecture_code: str | None = None,
                          category: str | None = None) -> tuple[float, float]:
    """Look up insurance rate from pay_jp_social_insurance_rates table.

    Returns (employee_rate, employer_rate).
    """
    try:
        where = {"rate_type": rate_type, "is_current": True}
        rows = _db.load_table(f"{PREFIX}_social_insurance_rates", where=where)
        if not rows:
            rows = _db.load_table(f"{PREFIX}_social_insurance_rates") or []
            rows = [r for r in rows if r.get("rate_type") == rate_type]
    except Exception:
        rows = []

    # Filter by prefecture if specified
    if prefecture_code and rows:
        prefecture_rows = [r for r in rows if str(r.get("prefecture_code", "")).upper() == str(prefecture_code).upper()]
        if prefecture_rows:
            rows = prefecture_rows

    if rows:
        r = rows[0]
        return float(r.get("employee_rate", 0)), float(r.get("employer_rate", 0))

    # Default rates (2026 Japan standard)
    defaults = {
        "health_insurance": (0.04985, 0.04985),  # Tokyo 2026
        "pension": (0.0915, 0.0915),
        "nursing_care": (0.00895, 0.00895),
        "employment": (0.006, 0.0095),
        "child_support": (0.0000, 0.00115),
        "child_allowance": (0.0000, 0.0036),
    }
    return defaults.get(rate_type, (0.0, 0.0))


def lookup_standard_remuneration(monthly_amount: float, grade_type: str = "health_insurance") -> float:
    """Look up standard monthly remuneration (標準報酬月額) from grade table."""
    try:
        rows = _db.load_table(f"{PREFIX}_standard_remuneration_grades") or []
        rows = [r for r in rows if r.get("grade_type") == grade_type]
        rows.sort(key=lambda r: float(r.get("min_amount", 0)))
        for r in rows:
            if monthly_amount <= float(r.get("max_amount", float("inf"))):
                return float(r.get("standard_amount", monthly_amount))
    except Exception:
        pass
    return monthly_amount


def lookup_withholding_tax(taxable_income: float, dependents_count: int = 0) -> float:
    """Look up withholding tax from progressive bracket table (源泉徴収税額表)."""
    try:
        rows = _db.load_table(f"{PREFIX}_withholding_tax_brackets") or []
        rows = [r for r in rows if int(r.get("dependents", 0)) == dependents_count]
        rows.sort(key=lambda r: float(r.get("min_income", 0)))
        for r in rows:
            if taxable_income <= float(r.get("max_income", float("inf"))):
                return float(r.get("tax_amount", 0))
    except Exception:
        pass
    # Simplified fallback: ~5% effective rate
    return round(taxable_income * 0.05)


# ── Core Calculation Engine ───────────────────────────────────────────────

def calc_salary_by_type(emp: dict, salary_type: str, actual_hours: float = 0.0,
                        actual_days: float = 0.0, working_days_in_month: float = 22.0) -> dict:
    """Calculate salary based on salary type.

    Returns dict with base_pay, allowance_total, gross_pay, deductions, net_pay,
    employer_cost_total, calculation_detail, messages.
    """
    messages: list = []

    # ── Base pay ──
    if salary_type == "monthly":
        basic = float(emp.get("basic_salary") or 0)
        wd = max(float(working_days_in_month or 22), 1)
        absence = float(emp.get("absence_days") or 0)
        effective = max(wd - absence, 0)
        base = round(basic * effective / wd, 0)

    elif salary_type == "hourly":
        ah = actual_hours or float(emp.get("standard_monthly_hours") or 160)
        rate = float(emp.get("hourly_rate") or 0)
        base = round(rate * ah, 0)

    elif salary_type == "daily":
        ad = actual_days or 1
        rate = float(emp.get("daily_rate") or 0)
        base = round(rate * ad, 0)

    elif salary_type == "monthly_fixed_ot":
        basic = float(emp.get("basic_salary") or 0)
        fixed_ot = float(emp.get("fixed_overtime_amount") or 0)
        wd = max(float(working_days_in_month or 22), 1)
        absence = float(emp.get("absence_days") or 0)
        effective = max(wd - absence, 0)
        base = round(basic * effective / wd, 0) + fixed_ot

    elif salary_type == "monthly_hour":
        std_hours = float(emp.get("standard_monthly_hours") or 160)
        ah = actual_hours or std_hours
        basic = float(emp.get("basic_salary") or 0)
        hr = float(emp.get("hourly_rate") or 0)
        ot_rate = float(emp.get("overtime_hourly_rate") or 0)
        if ah <= std_hours:
            monthly_part = round(basic * ah / max(std_hours, 1), 0)
            hourly_part = round(hr * ah, 0)
            overtime_pay = 0.0
        else:
            monthly_part = basic
            hourly_part = round(hr * std_hours, 0)
            overtime_pay = round(ot_rate * (ah - std_hours), 0)
        base = monthly_part + hourly_part + overtime_pay

    else:
        base = float(emp.get("basic_salary") or 0)

    # ── Allowances ──
    allowance_keys = [
        "commute_allowance", "housing_allowance", "family_allowance",
        "position_allowance", "fixed_allowance", "transport_allowance",
        "phone_allowance", "performance_bonus", "project_bonus",
    ]
    if salary_type != "monthly_fixed_ot":
        allowance_keys.append("fixed_overtime_amount")
    allowances = sum(float(emp.get(k) or 0) for k in allowance_keys)
    gross_pay = base + allowances

    # ── Social insurance ──
    si_eligible = emp.get("social_insurance_eligible") not in (False, "false", 0, "0")
    ei_eligible = emp.get("employment_insurance_eligible") not in (False, "false", 0, "0")
    age = calc_fiscal_age(emp.get("employee_id", ""), emp) or 0
    prefecture = emp.get("prefecture_code") or None

    health_er, health_empr = lookup_insurance_rate("health_insurance", prefecture)
    pension_er, pension_empr = lookup_insurance_rate("pension")
    care_er, care_empr = lookup_insurance_rate("nursing_care")
    employ_er, employ_empr = lookup_insurance_rate("employment", category=emp.get("employment_insurance_category"))
    child_sup_er, child_sup_empr = lookup_insurance_rate("child_support")
    child_al_er, child_al_empr = lookup_insurance_rate("child_allowance")

    # Insurance base: use standard monthly remuneration for monthly_hour
    if salary_type == "monthly_hour":
        ins_base_health = lookup_standard_remuneration(base, "health_insurance")
        ins_base_pension = lookup_standard_remuneration(base, "pension_insurance")
    else:
        ins_base_health = base
        ins_base_pension = base

    health_ins = round(ins_base_health * health_er, 0) if si_eligible else 0
    pension = round(ins_base_pension * pension_er, 0) if si_eligible else 0
    care_ins = round(ins_base_health * care_er, 0) if (si_eligible and 40 <= age <= 64) else 0
    employ_ins = round(base * employ_er, 0) if ei_eligible else 0
    si_total = health_ins + pension + care_ins + employ_ins

    # ── Income tax ──
    non_taxable_commute = float(emp.get("commute_allowance") or 0)
    taxable_income = max(gross_pay - non_taxable_commute - si_total, 0)
    dependents = int(emp.get("dependents_count") or 0)
    income_tax = lookup_withholding_tax(taxable_income, dependents)

    resident_tax = float(emp.get("monthly_resident_tax") or 0)
    recurring = float(emp.get("recurring_deductions") or 0)
    deduction_total = si_total + income_tax + resident_tax + recurring
    net_pay = gross_pay - deduction_total

    # ── Employer cost ──
    employer_health = round(ins_base_health * health_empr, 0) if si_eligible else 0
    employer_pension = round(ins_base_pension * pension_empr, 0) if si_eligible else 0
    employer_care = round(ins_base_health * care_empr, 0) if (si_eligible and 40 <= age <= 64) else 0
    employer_employ = round(base * employ_empr, 0) if ei_eligible else 0
    employer_child_support = round(ins_base_health * child_sup_empr, 0) if si_eligible else 0
    employer_child = round(ins_base_health * child_al_empr, 0) if si_eligible else 0

    # Accident insurance (労災保険)
    accident_rate = 0.0
    industry_code = emp.get("industry_code") or None
    if industry_code:
        try:
            ai_rows = _db.load_table(f"{PREFIX}_accident_insurance_rates",
                                     where={"industry_code": industry_code, "is_current": True})
            if ai_rows:
                accident_rate = float(ai_rows[0].get("rate", 0))
        except Exception:
            pass
    employer_accident = round(base * accident_rate, 0)

    employer_cost = (employer_health + employer_pension + employer_care + employer_employ
                     + employer_child_support + employer_child + employer_accident)

    return {
        "salary_type": salary_type,
        "base_pay": int(round(base)),
        "allowance_total": int(round(allowances)),
        "gross_pay": int(round(gross_pay)),
        "health_insurance_employee": int(round(health_ins)),
        "pension_employee": int(round(pension)),
        "care_insurance_employee": int(round(care_ins)),
        "employment_insurance_employee": int(round(employ_ins)),
        "income_tax": int(round(income_tax)),
        "monthly_resident_tax": int(round(resident_tax)),
        "recurring_deductions": int(round(recurring)),
        "deduction_total": int(round(deduction_total)),
        "net_pay": int(round(net_pay)),
        "employer_cost_total": int(round(employer_cost)),
        "employer_health": int(round(employer_health)),
        "employer_pension": int(round(employer_pension)),
        "employer_care": int(round(employer_care)),
        "employer_employ": int(round(employer_employ)),
        "employer_child_support": int(round(employer_child_support)),
        "employer_child_allowance": int(round(employer_child)),
        "employer_accident_insurance": int(round(employer_accident)),
        "standard_work_days": float(working_days_in_month or 22),
        "actual_days": actual_days or float(working_days_in_month or 22),
        "actual_hours": actual_hours or float(emp.get("standard_work_hours") or 176),
        "messages": messages,
    }
