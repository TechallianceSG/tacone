"""Payroll CN calculation engine — China social insurance, housing fund, IIT.

CN salary calculation is monthly-based (月薪制).
Formula derived from: docs/TECH ALLIANCE 工资明细 202605南京 copy.xlsx

Key differences from JP:
- Social insurance (五险): pension, medical, unemployment, work injury, maternity
- Housing fund (住房公积金): employee + employer contributions
- IIT (个人所得税): progressive tax brackets with quick deduction
- Attendance-based pay: (basic_salary + position_allowance) / full_days * actual_days
"""

from __future__ import annotations

from typing import Any


def lookup_social_insurance_rates(rates_record: dict) -> dict:
    """Extract social insurance rates from a rate record.

    Returns dict with rates for: pension, medical, unemployment, work_injury, maternity
    (both employee and employer shares).
    """
    return {
        "pension_employee": float(rates_record.get("pension_employee", 0.08)),
        "pension_employer": float(rates_record.get("pension_employer", 0.16)),
        "medical_employee": float(rates_record.get("medical_employee", 0.02)),
        "medical_employer": float(rates_record.get("medical_employer", 0.08)),
        "unemployment_employee": float(rates_record.get("unemployment_employee", 0.005)),
        "unemployment_employer": float(rates_record.get("unemployment_employer", 0.005)),
        "work_injury_employer": float(rates_record.get("work_injury_employer", 0.004)),
        "maternity_employer": float(rates_record.get("maternity_employer", 0.008)),
        # Ceilings
        "si_ceiling": float(rates_record.get("si_ceiling", 24000)),
        "si_floor": float(rates_record.get("si_floor", 4494)),
    }


def lookup_housing_fund_rate(rate_record: dict) -> dict:
    """Extract housing fund rate from a rate record."""
    return {
        "employee_rate": float(rate_record.get("employee_rate", 0.07)),
        "employer_rate": float(rate_record.get("employer_rate", 0.07)),
        "hf_ceiling": float(rate_record.get("hf_ceiling", 38700)),
        "hf_floor": float(rate_record.get("hf_floor", 2280)),
    }


def calculate_iit(taxable_income: float, tax_brackets: list) -> float:
    """Calculate China IIT (个人所得税) using progressive tax brackets.

    Standard formula: IIT = taxable_income * rate - quick_deduction

    Tax brackets are sorted by threshold ascending.
    Each bracket: {threshold, rate, quick_deduction}
    """
    if taxable_income <= 0:
        return 0.0

    brackets = sorted(tax_brackets, key=lambda b: float(b.get("threshold", 0)))
    rate = 0.0
    quick_deduction = 0.0

    for b in brackets:
        threshold = float(b.get("threshold", 0))
        if taxable_income <= threshold:
            rate = float(b.get("rate", 0))
            quick_deduction = float(b.get("quick_deduction", 0))
            break
    else:
        # Above highest bracket — use the last bracket
        if brackets:
            rate = float(brackets[-1].get("rate", 0.45))
            quick_deduction = float(brackets[-1].get("quick_deduction", 181920))

    iit = taxable_income * rate - quick_deduction
    return max(0.0, round(iit, 2))


def calc_salary(
    emp: dict,
    attendance: dict,
    si_rates: dict | None = None,
    hf_rate: dict | None = None,
    tax_brackets: list | None = None,
) -> dict:
    """Calculate China monthly salary.

    Args:
        emp: Employee salary master record or batch record
        attendance: {
            full_attendance_days, actual_attendance_days,
            personal_leave_days, annual_leave_days, sick_leave_days, other_leave_days,
            other_additions, other_deductions
        }
        si_rates: Social insurance rates record (from pay_cn_social_insurance_rates)
        hf_rate: Housing fund rate record (from pay_cn_housing_fund_rates)
        tax_brackets: IIT tax brackets list (from pay_cn_tax_brackets)

    Returns:
        dict with all calculated fields
    """
    si = lookup_social_insurance_rates(si_rates or {})
    hf = lookup_housing_fund_rate(hf_rate or {})
    brackets = tax_brackets or []

    # ── Attendance ──
    full_days = float(attendance.get("full_attendance_days", 22))
    actual_days = float(attendance.get("actual_attendance_days", full_days))
    sick_days = float(attendance.get("sick_leave_days", 0))
    other_additions = float(attendance.get("other_additions", 0))
    other_deductions = float(attendance.get("other_deductions", 0))

    # ── Base Pay ──
    basic_salary = float(emp.get("basic_salary", 0))
    position_allowance = float(emp.get("position_allowance", 0))
    monthly_base = basic_salary + position_allowance

    # Attendance pay: (basic + position) / full_days * actual_days
    if full_days > 0:
        attendance_pay = round(monthly_base / full_days * actual_days, 2)
    else:
        attendance_pay = monthly_base

    # ── Sick Leave Pay ──
    # Standard: 60% of daily rate for sick days (adjustable by company policy)
    sick_leave_pay = 0.0
    if sick_days > 0 and full_days > 0:
        daily_rate = monthly_base / full_days
        sick_leave_pay = round(daily_rate * sick_days * 0.6, 2)

    # ── Full Attendance Bonus ──
    full_attendance_bonus = 0.0
    if actual_days >= full_days:
        full_attendance_bonus = float(emp.get("full_attendance_bonus", 200))

    # ── Gross Pay ──
    gross_pay = attendance_pay + sick_leave_pay + full_attendance_bonus + other_additions

    # ── Social Insurance Base ──
    si_base = float(emp.get("social_insurance_base", monthly_base))
    si_base = max(si["si_floor"], min(si_base, si["si_ceiling"]))

    # ── Social Insurance (Employee) ──
    si_employee = round(si_base * (
        si["pension_employee"] +
        si["medical_employee"] +
        si["unemployment_employee"]
    ), 2)

    # ── Housing Fund Base ──
    hf_base = float(emp.get("housing_fund_base", monthly_base))
    hf_base = max(hf["hf_floor"], min(hf_base, hf["hf_ceiling"]))

    # ── Housing Fund (Employee) ──
    hf_employee = round(hf_base * hf["employee_rate"], 2)

    # ── IIT (个人所得税) ──
    # Taxable income = gross_pay - si_employee - hf_employee - standard_deduction(5000)
    standard_deduction = 5000.0  # China standard monthly deduction
    taxable_income = gross_pay - si_employee - hf_employee - standard_deduction
    iit = calculate_iit(taxable_income, brackets)

    # ── Total Deductions ──
    deduction_total = si_employee + hf_employee + iit + other_deductions

    # ── Net Pay ──
    net_pay = round(gross_pay - deduction_total, 2)

    # ── Employer Contributions ──
    employer_si = round(si_base * (
        si["pension_employer"] +
        si["medical_employer"] +
        si["unemployment_employer"] +
        si["work_injury_employer"] +
        si["maternity_employer"]
    ), 2)
    employer_hf = round(hf_base * hf["employer_rate"], 2)
    employer_cost_total = employer_si + employer_hf

    return {
        # Attendance
        "full_attendance_days": full_days,
        "actual_attendance_days": actual_days,
        # Earnings
        "basic_salary": basic_salary,
        "position_allowance": position_allowance,
        "attendance_pay": attendance_pay,
        "sick_leave_pay": sick_leave_pay,
        "full_attendance_bonus": full_attendance_bonus,
        "other_additions": other_additions,
        "gross_pay": round(gross_pay, 2),
        # Deductions
        "social_insurance": si_employee,
        "housing_fund": hf_employee,
        "iit": iit,
        "other_deductions": other_deductions,
        "deduction_total": round(deduction_total, 2),
        # Net
        "net_pay": net_pay,
        # Employer costs
        "employer_social_insurance": employer_si,
        "employer_housing_fund": employer_hf,
        "employer_cost_total": round(employer_cost_total, 2),
        # Debug
        "si_base": si_base,
        "hf_base": hf_base,
        "taxable_income": round(taxable_income, 2),
        "standard_deduction": standard_deduction,
        "messages": [],
    }
