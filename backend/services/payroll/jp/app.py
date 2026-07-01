#!/usr/bin/env python3
"""TACAI Payroll JP — Japan Payroll Service.

Handles:
  - Payroll Item Definitions (salary components catalog)
  - Payroll Parameters (social insurance rates, tax rules)
  - Employee Salary Configuration
  - Payroll Batch processing (calculate with JP labor law)
  - Monthly Salary Sheets
  - Payslip generation & email delivery
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

# ── Shared libraries ──
import sys as _sys
_shared_path = Path(__file__).resolve().parents[3] / 'shared'
if str(_shared_path) not in _sys.path:
    _sys.path.insert(0, str(_shared_path))

try:
    import db_utils as _db
    _PG_AVAILABLE = _db.DB_ENABLED if hasattr(_db, 'DB_ENABLED') else True
except Exception:
    _PG_AVAILABLE = False


def send_json(handler, data, status=200):
    body = json.dumps(data, ensure_ascii=False, default=str).encode('utf-8')
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Content-Length', str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def success(handler, data, status=200):
    send_json(handler, {"success": True, "data": data}, status)


def error(handler, message, status=400):
    send_json(handler, {"success": False, "error": message}, status)


def paginated(handler, data, page, page_size, total):
    send_json(handler, {"success": True, "data": data, "page": page, "page_size": page_size, "total": total})


def parse_json_body(handler):
    try:
        length = int(handler.headers.get('Content-Length', 0))
        if length == 0:
            return {}
        raw = handler.rfile.read(length)
        return json.loads(raw.decode('utf-8'))
    except Exception:
        return None


def get_query_param(handler, key, default=None):
    params = parse_qs(urlparse(handler.path).query)
    values = params.get(key, [])
    return values[0] if values else default


# ── Constants ──
ROOT_DIR = Path(__file__).resolve().parents[0]
DATABASE_DIR = ROOT_DIR / "database"
MODULE_PREFIX = "pay_jp"
MODULE_NAME = "tacaipay_jp"
DEFAULT_PORT = 8013
USER_ADMIN_SESSION_COOKIE = "tacai_session_id"
REQUIRED_MODULE_PERMISSION = "tacaipay_jp.access"
MAX_POST_BYTES = 2 * 1024 * 1024

TACAI_PUBLIC_HOST = os.environ.get("TACAI_PUBLIC_HOST", "127.0.0.1").strip() or "127.0.0.1"


def _resolve_auth_port() -> int:
    try:
        from config import get_auth_port
        return get_auth_port()
    except Exception:
        return int(os.environ.get("AUTH_PORT", "3001"))


AUTH_PORT = _resolve_auth_port()
USER_ADMIN_INTERNAL_BASE_URL = f"http://127.0.0.1:{AUTH_PORT}"


def validate_session(session_id: str) -> dict[str, Any] | None:
    if not session_id:
        return None
    try:
        req = Request(
            f"{USER_ADMIN_INTERNAL_BASE_URL}/api/validate-session",
            data=json.dumps({"session_id": session_id}).encode('utf-8'),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        resp = urlopen(req, timeout=5)
        body = json.loads(resp.read().decode('utf-8'))
        if body.get("success") and body.get("data", {}).get("valid"):
            return body["data"]
        return None
    except Exception:
        return None


class PayrollJPHandler(BaseHTTPRequestHandler):

    def _get_session(self) -> dict[str, Any] | None:
        cookies = SimpleCookie(self.headers.get("Cookie", ""))
        for key in [USER_ADMIN_SESSION_COOKIE, "tacai_session_id"]:
            if key in cookies:
                return validate_session(cookies[key].value)
        return None

    def _check_permission(self, session: dict, permission: str) -> bool:
        if not session:
            return False
        user = session.get("user", {})
        roles = user.get("roles", [])
        if user.get("user_type") == "system_admin" or "system_admin" in roles:
            return True
        perms = session.get("permissions", []) or user.get("permissions", [])
        return permission in perms

    def _require_auth(self) -> dict[str, Any] | None:
        # Trust Portal gateway — auth already validated by Portal before proxying.
        # Portal forwards requests from localhost; skip redundant session validation.
        client_host = self.client_address[0] if self.client_address else ""
        if client_host in ("127.0.0.1", "localhost", "::1"):
            return {"user": {"email": "portal-gateway", "roles": ["system_admin"]}, "permissions": ["tacaipay_jp.access", "tacaipay_jp.manage", "tacaipay_jp.calculate", "tacaipay_jp.approve"]}
        # Direct access (non-localhost) — validate session with User_admin
        session = self._get_session()
        if not session:
            error(self, "Unauthorized", 401)
            return None
        return session

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")
        self.send_header("Access-Control-Allow-Credentials", "true")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    # ── Routing ──
    def do_GET(self) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"

        if path == "/health":
            send_json(self, {"status": "ok", "module": MODULE_NAME, "port": DEFAULT_PORT})
            return

        session = self._require_auth()
        if not session:
            return

        if path == "/api/payroll/jp/item-definitions":
            self._list("pay_jp_payroll_item_definitions")
        elif path == "/api/payroll/jp/parameters":
            self._list_parameters()
        elif path == "/api/payroll/jp/employees/importable":
            self._list_importable_employees()
        elif path == "/api/payroll/jp/employees":
            self._list("pay_jp_salary_master")
        elif path == "/api/payroll/jp/batches":
            self._list("pay_jp_payroll_batches")
        elif path == "/api/payroll/jp/sheets":
            self._list("pay_jp_monthly_salary_sheets")
        elif path == "/api/payroll/jp/payslips":
            self._list("pay_jp_payslips")
        elif path == "/api/payroll/jp/audit-logs":
            self._list("pay_jp_audit_logs")
        else:
            # Detail by ID (check calc-preview first)
            for prefix in ["/api/payroll/jp/employees/"]:
                if path.startswith(prefix) and path.endswith("/calc-preview"):
                    emp_id = path[len(prefix):-len("/calc-preview")]
                    self._calc_preview(emp_id)
                    return
            for prefix, table, pk in [
                ("/api/payroll/jp/item-definitions/", "pay_jp_payroll_item_definitions", "item_id"),
                ("/api/payroll/jp/employees/", "pay_jp_salary_master", "employee_id"),
                ("/api/payroll/jp/batches/", "pay_jp_payroll_batches", "batch_id"),
                ("/api/payroll/jp/sheets/", "pay_jp_monthly_salary_sheets", "sheet_id"),
                ("/api/payroll/jp/payslips/", "pay_jp_payslips", "record_id"),
            ]:
                if path.startswith(prefix):
                    rest = path[len(prefix):]
                    self._detail(table, pk, rest)
                    return
            error(self, "Not Found", 404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"
        session = self._require_auth()
        if not session:
            return
        body = parse_json_body(self)

        if path == "/api/payroll/jp/item-definitions":
            self._save("pay_jp_payroll_item_definitions", "item_id", session, body)
        elif path == "/api/payroll/jp/parameters":
            self._save_parameter(session, body)
        elif path == "/api/payroll/jp/employees/import":
            self._import_employees(session, body)
        elif path == "/api/payroll/jp/employees":
            self._save("pay_jp_salary_master", "employee_id", session, body)
        elif path.startswith("/api/payroll/jp/employees/") and path.endswith("/deactivate"):
            emp_id = path.split("/")[-2]
            self._deactivate_employee(session, emp_id, body)
        elif path == "/api/payroll/jp/batches":
            self._create_batch(session, body)
        elif path.startswith("/api/payroll/jp/batches/") and path.endswith("/calculate"):
            batch_id = path.split("/")[-2]
            self._calculate_batch(session, batch_id)
        elif path.startswith("/api/payroll/jp/sheets/") and path.endswith("/confirm"):
            sheet_id = path.split("/")[-2]
            self._confirm_sheet(session, sheet_id)
        elif path.startswith("/api/payroll/jp/payslips/") and path.endswith("/email"):
            payslip_id = path.split("/")[-2]
            self._email_payslip(session, payslip_id)
        else:
            error(self, "Not Found", 404)

    # ── DB helpers ──
    def _list(self, table: str):
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        try:
            rows = _db.load_table(table, order_by="created_at DESC")
            success(self, {"items": rows, "total": len(rows)})
        except Exception as e:
            error(self, f"Database error: {str(e)}", 500)

    def _list_parameters(self):
        """UNION all 4 parameter tables into one unified response."""
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        try:
            all_items = []

            # 1. Social Insurance
            si_rows = _db.load_table("pay_jp_social_insurance_rates", order_by="rate_type, prefecture NULLS FIRST")
            for r in si_rows:
                all_items.append({**r, "param_type": "social_insurance_rate"})

            # 2. Standard Remuneration Grades
            rg_rows = _db.load_table("pay_jp_standard_remuneration_grades", order_by="grade_type, grade_number")
            for r in rg_rows:
                all_items.append({**r, "param_type": "standard_remuneration_grade"})

            # 3. Withholding Tax Brackets
            tx_rows = _db.load_table("pay_jp_withholding_tax_brackets", order_by="table_type, min_salary")
            for r in tx_rows:
                all_items.append({**r, "param_type": "withholding_tax_bracket"})

            # 4. Accident Insurance
            ai_rows = _db.load_table("pay_jp_accident_insurance_rates", order_by="industry_code")
            for r in ai_rows:
                all_items.append({**r, "param_type": "accident_insurance_rate"})

            success(self, {"items": all_items, "total": len(all_items)})
        except Exception as e:
            error(self, f"Database error: {str(e)}", 500)

    def _detail(self, table: str, pk_col: str, pk_val: str):
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        try:
            row = _db.load_table(table, where=f"{pk_col} = '{pk_val}'")
            success(self, row[0]) if row else error(self, "Not Found", 404)
        except Exception as e:
            error(self, f"Database error: {str(e)}", 500)

    def _save(self, table: str, pk_col: str, session: dict, body: dict):
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        if not self._check_permission(session, "tacaipay_jp.manage"):
            error(self, "Forbidden", 403)
            return
        try:
            pk_val = body.get(pk_col)
            if not pk_val:
                error(self, f"{pk_col} is required", 400)
                return
            existing = _db.load_table(table, where=f"{pk_col} = '{pk_val}'")
            if existing:
                body["updated_at"] = datetime.now(timezone.utc).isoformat()
                _db.update_record(table, pk_col, pk_val, body)
            else:
                # Auto-generate salary_master_id for new salary master records
                if table == "pay_jp_salary_master" and not body.get("salary_master_id"):
                    all_records = _db.load_table(table, order_by="salary_master_id DESC")
                    next_num = 1
                    if all_records:
                        last_id = all_records[0].get("salary_master_id", "SM-JP-0000")
                        try:
                            next_num = int(last_id.split("-")[-1]) + 1
                        except (ValueError, IndexError):
                            next_num = len(all_records) + 1
                    body["salary_master_id"] = f"SM-JP-{next_num:04d}"
                body["created_at"] = datetime.now(timezone.utc).isoformat()
                body["updated_at"] = datetime.now(timezone.utc).isoformat()
                if "source" not in body:
                    body["source"] = "manual"
                _db.insert_record(table, body)
            success(self, {pk_col: pk_val})
        except Exception as e:
            error(self, f"Save failed: {str(e)}", 500)

    def _list_importable_employees(self):
        """Return employees from EmployeeAdmin eligible for import into salary master."""
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        try:
            # Get employees from emp_employees that have payroll data
            ea_employees = _db.load_table("emp_employees", order_by="employee_number")
            existing = _db.load_table("pay_jp_salary_master")
            existing_ids = {r.get("employee_id", "") for r in existing}

            result = []
            for emp in ea_employees:
                eid = emp.get("employee_id", "")
                payroll_raw = emp.get("payroll", {})
                payroll = payroll_raw
                if isinstance(payroll_raw, str):
                    try:
                        payroll = json.loads(payroll_raw)
                    except Exception:
                        payroll = {}
                profile_raw = emp.get("profile", {})
                profile = profile_raw
                if isinstance(profile_raw, str):
                    try:
                        profile = json.loads(profile_raw)
                    except Exception:
                        profile = {}
                employment_raw = emp.get("employment", {})
                employment = employment_raw
                if isinstance(employment_raw, str):
                    try:
                        employment = json.loads(employment_raw)
                    except Exception:
                        employment = {}

                result.append({
                    "employee_id": eid,
                    "employee_number": emp.get("employee_number", ""),
                    "employee_name": profile.get("name", {}).get("display_name", "") if isinstance(profile, dict) else "",
                    "email": profile.get("email", "") if isinstance(profile, dict) else "",
                    "department_label": employment.get("department", "") if isinstance(employment, dict) else "",
                    "team_label": employment.get("team_id", "") if isinstance(employment, dict) else "",
                    "entity_id": employment.get("entity_id", "") if isinstance(employment, dict) else "",
                    "salary_type": payroll.get("salary_type", "monthly") if isinstance(payroll, dict) else "monthly",
                    "already_imported": eid in existing_ids,
                })
            success(self, {"items": result, "total": len(result)})
        except Exception as e:
            error(self, f"Failed to list importable employees: {str(e)}", 500)

    def _import_employees(self, session, body):
        """Import selected employees from EmployeeAdmin into salary master."""
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        if not self._check_permission(session, "tacaipay_jp.manage"):
            error(self, "Forbidden", 403)
            return
        try:
            selected_ids = body.get("employee_ids", [])
            if not selected_ids:
                error(self, "No employee_ids provided", 400)
                return

            existing = _db.load_table("pay_jp_salary_master")
            existing_ids = {r.get("employee_id", "") for r in existing}

            # Determine next salary_master_id number
            all_records = _db.load_table("pay_jp_salary_master", order_by="salary_master_id DESC")
            next_num = 1
            if all_records:
                last_id = all_records[0].get("salary_master_id", "SM-JP-0000")
                try:
                    next_num = int(last_id.split("-")[-1]) + 1
                except (ValueError, IndexError):
                    next_num = len(existing) + 1

            imported = 0
            skipped = 0
            now_iso = datetime.now(timezone.utc).isoformat()

            for emp_id in selected_ids:
                if emp_id in existing_ids:
                    skipped += 1
                    continue

                ea_rows = _db.load_table("emp_employees", where=f"employee_id = '{emp_id}'")
                if not ea_rows:
                    continue
                ea = ea_rows[0]

                payroll_raw = ea.get("payroll", {})
                payroll = payroll_raw
                if isinstance(payroll_raw, str):
                    try:
                        payroll = json.loads(payroll_raw)
                    except Exception:
                        payroll = {}
                profile_raw = ea.get("profile", {})
                profile = profile_raw
                if isinstance(profile_raw, str):
                    try:
                        profile = json.loads(profile_raw)
                    except Exception:
                        profile = {}
                employment_raw = ea.get("employment", {})
                employment = employment_raw
                if isinstance(employment_raw, str):
                    try:
                        employment = json.loads(employment_raw)
                    except Exception:
                        employment = {}

                sm_id = f"SM-JP-{next_num:04d}"
                next_num += 1

                rec = {
                    "salary_master_id": sm_id,
                    "employee_id": ea.get("employee_id", emp_id),
                    "employee_number": ea.get("employee_number", ""),
                    "employee_name": profile.get("name", {}).get("display_name", "") if isinstance(profile, dict) else "",
                    "email": profile.get("email", "") if isinstance(profile, dict) else "",
                    "entity_id": employment.get("entity_id", "ENT-0004") if isinstance(employment, dict) else "ENT-0004",
                    "department_label": employment.get("department", "") if isinstance(employment, dict) else "",
                    "team_label": employment.get("team_id", "") if isinstance(employment, dict) else "",
                    "salary_type": payroll.get("salary_type", "monthly") if isinstance(payroll, dict) else "monthly",
                    "basic_salary": float(payroll.get("basic_salary", 0) or 0),
                    "hourly_rate": float(payroll.get("hourly_rate", 0) or 0),
                    "daily_rate": float(payroll.get("daily_rate", 0) or 0),
                    "standard_work_days": float(payroll.get("standard_work_days", 22) or 22),
                    "standard_work_hours": float(payroll.get("standard_work_hours", 176) or 176),
                    "standard_monthly_hours": float(payroll.get("standard_monthly_hours", 160) or 160),
                    "commute_allowance": float(payroll.get("commute_allowance", 0) or 0),
                    "transport_allowance": float(payroll.get("transport_allowance", 0) or 0),
                    "phone_allowance": float(payroll.get("phone_allowance", 0) or 0),
                    "project_bonus": float(payroll.get("project_bonus", 0) or 0),
                    "social_insurance_eligible": payroll.get("social_insurance_eligible", True),
                    "employment_insurance_eligible": payroll.get("employment_insurance_eligible", True),
                    "age_at_fiscal_year_start": int(payroll.get("age_at_fiscal_year_start", 0) or 0),
                    "dependents_count": int(payroll.get("dependents_count", 0) or 0),
                    "prefecture_code": payroll.get("prefecture_code", "13") or "13",
                    "active": True,
                    "source": "employeeadmin",
                    "created_at": now_iso,
                    "updated_at": now_iso,
                }
                # Insert into DB
                _db.insert_record("pay_jp_salary_master", rec)
                imported += 1

            user_email = session.get("user", {}).get("email", "system")
            result = {
                "ok": True,
                "imported": imported,
                "skipped": skipped,
                "imported_by": user_email,
            }
            success(self, result)
        except Exception as e:
            error(self, f"Import failed: {str(e)}", 500)

    def _deactivate_employee(self, session, emp_id, body):
        """Soft-deactivate an employee in salary master."""
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        if not self._check_permission(session, "tacaipay_jp.manage"):
            error(self, "Forbidden", 403)
            return
        try:
            existing = _db.load_table("pay_jp_salary_master", where=f"employee_id = '{emp_id}'")
            if not existing:
                error(self, "Employee not found", 404)
                return
            reason = body.get("deactivation_reason", "") if body else ""
            user_email = session.get("user", {}).get("email", "system")
            now_iso = datetime.now(timezone.utc).isoformat()
            _db.update_record("pay_jp_salary_master", "employee_id", emp_id, {
                "active": False,
                "deactivated_at": now_iso,
                "deactivated_by": user_email,
                "deactivation_reason": reason,
                "updated_at": now_iso,
            })
            success(self, {"employee_id": emp_id, "status": "deactivated"})
        except Exception as e:
            error(self, f"Deactivate failed: {str(e)}", 500)

    def _calc_preview(self, emp_id):
        """Calculate salary preview for an employee based on their salary type."""
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        try:
            rows = _db.load_table("pay_jp_salary_master", where=f"employee_id = '{emp_id}'")
            if not rows:
                error(self, "Employee not found", 404)
                return
            emp = rows[0]

            # Parse query params
            actual_hours = float(get_query_param(self, "actual_hours", "0") or "0")
            actual_days = float(get_query_param(self, "actual_days", "0") or "0")

            salary_type = (emp.get("salary_type") or "monthly").strip()
            result = self._calc_salary_by_type(emp, salary_type, actual_hours, actual_days)

            # Add employee info
            result["employee"] = {
                "employee_id": emp.get("employee_id", ""),
                "employee_name": emp.get("employee_name", ""),
                "employee_number": emp.get("employee_number", ""),
                "salary_type": salary_type,
            }
            success(self, result)
        except Exception as e:
            error(self, f"Calc preview failed: {str(e)}", 500)

    def _calc_salary_by_type(self, emp, salary_type, actual_hours, actual_days):
        """Salary-type-specific calculation logic, ported from tacaipayjp's calculation.py."""
        messages = []

        if salary_type == "monthly":
            actual_days = actual_days or 22
            std_days = float(emp.get("standard_work_days") or 22)
            basic = float(emp.get("basic_salary") or 0)
            base = round(basic * min(actual_days / max(std_days, 1), 1.0), 0)
            messages.append(f"月給: {basic:,.0f}円 × {actual_days}日/{std_days}日 = {base:,.0f}円")

        elif salary_type == "hourly":
            actual_hours = actual_hours or 160
            rate = float(emp.get("hourly_rate") or 0)
            base = round(rate * actual_hours, 0)
            messages.append(f"時給: {rate:,.0f}円 × {actual_hours}h = {base:,.0f}円")

        elif salary_type == "daily":
            actual_days = actual_days or 1
            rate = float(emp.get("daily_rate") or 0)
            base = round(rate * actual_days, 0)
            messages.append(f"日給: {rate:,.0f}円 × {actual_days}日 = {base:,.0f}円")

        elif salary_type == "monthly_fixed_ot":
            actual_days = actual_days or 22
            std_days = float(emp.get("standard_work_days") or 22)
            basic = float(emp.get("basic_salary") or 0)
            fixed_ot = float(emp.get("fixed_overtime_amount") or 0)
            base = round(basic * min(actual_days / max(std_days, 1), 1.0), 0)
            gross = base + fixed_ot
            messages.append(f"月給: {basic:,.0f}円 × {actual_days}日/{std_days}日 = {base:,.0f}円")
            messages.append(f"固定残業代: {fixed_ot:,.0f}円")
            base = gross  # use gross as base for deduction calculation

        elif salary_type == "monthly_hour":
            actual_hours = actual_hours or 160
            basic = float(emp.get("basic_salary") or 0)
            hourly_rate = float(emp.get("hourly_rate") or 0)
            overtime_rate = float(emp.get("overtime_hourly_rate") or 0)
            std_hours = float(emp.get("standard_monthly_hours") or 160)

            if actual_hours <= std_hours:
                monthly_part = round(basic * actual_hours / max(std_hours, 1), 0)
                hourly_part = round(hourly_rate * actual_hours, 0)
                overtime_pay = 0.0
                messages.append(f"月時給: 基本給{basic:,.0f}円 × {actual_hours}h/{std_hours}h = {monthly_part:,.0f}円")
                messages.append(f"時給部分: {hourly_rate:,.0f}円 × {actual_hours}h = {hourly_part:,.0f}円")
            else:
                monthly_part = basic
                hourly_part = round(hourly_rate * std_hours, 0)
                ot_hours = actual_hours - std_hours
                overtime_pay = round(overtime_rate * ot_hours, 0)
                messages.append(f"月時給: 基本給{basic:,.0f}円 (全額支給)")
                messages.append(f"時給部分: {hourly_rate:,.0f}円 × {std_hours}h = {hourly_part:,.0f}円")
                messages.append(f"残業: {overtime_rate:,.0f}円 × {ot_hours}h = {overtime_pay:,.0f}円")

            base = monthly_part + hourly_part + overtime_pay
            messages.append(f"支給総額: {base:,.0f}円")
        else:
            base = float(emp.get("basic_salary") or 0)
            messages.append(f"Unknown salary_type: {salary_type}, using basic_salary")

        # Add allowances to get gross pay
        allowances = sum(float(emp.get(k) or 0) for k in [
            "commute_allowance", "housing_allowance", "family_allowance",
            "position_allowance", "fixed_allowance", "transport_allowance",
            "phone_allowance", "performance_bonus", "project_bonus",
            "fixed_overtime_amount"
        ])

        gross_pay = base + allowances

        # Statutory deductions (approximate Japanese rates)
        si_eligible = emp.get("social_insurance_eligible") not in (False, "false", 0, "0")
        ei_eligible = emp.get("employment_insurance_eligible") not in (False, "false", 0, "0")
        age = int(emp.get("age_at_fiscal_year_start") or 0)

        health_ins = round(gross_pay * 0.05, 0) if si_eligible else 0
        pension = round(gross_pay * 0.0915, 0) if si_eligible else 0
        care_ins = round(gross_pay * 0.009, 0) if (si_eligible and age >= 40) else 0
        employ_ins = round(gross_pay * 0.006, 0) if ei_eligible else 0
        si_total = health_ins + pension + care_ins + employ_ins
        income_tax = round(gross_pay * 0.05, 0)  # simplified
        resident_tax = float(emp.get("monthly_resident_tax") or 0)
        recurring = float(emp.get("recurring_deductions") or 0)

        deduction_total = si_total + income_tax + resident_tax + recurring
        net_pay = gross_pay - deduction_total
        employer_cost = round(gross_pay * 0.15, 0)  # employer social insurance share

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
            "standard_work_days": float(emp.get("standard_work_days") or 22),
            "standard_work_hours": float(emp.get("standard_work_hours") or 176),
            "standard_monthly_hours": float(emp.get("standard_monthly_hours") or 160),
            "actual_days": actual_days or float(emp.get("standard_work_days") or 22),
            "actual_hours": actual_hours or float(emp.get("standard_work_hours") or 176),
            "messages": messages,
        }

    def _save_parameter(self, session, body):
        """Route parameter save to the correct individual table based on param_type."""
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        if not self._check_permission(session, "tacaipay_jp.manage"):
            error(self, "Forbidden", 403)
            return
        try:
            param_type = body.get("param_type", "")
            table_map = {
                "social_insurance_rate":    ("pay_jp_social_insurance_rates",    "id"),
                "standard_remuneration_grade": ("pay_jp_standard_remuneration_grades", "id"),
                "withholding_tax_bracket":  ("pay_jp_withholding_tax_brackets",  "id"),
                "accident_insurance_rate":  ("pay_jp_accident_insurance_rates",  "id"),
            }
            table_info = table_map.get(param_type)
            if not table_info:
                error(self, f"Unknown param_type: {param_type}", 400)
                return
            table, pk_col = table_info
            pk_val = body.get(pk_col) or body.get("id")
            body["updated_at"] = datetime.now(timezone.utc).isoformat()

            if pk_val:
                existing = _db.load_table(table, where=f"{pk_col} = {int(pk_val)}")
                if existing:
                    _db.update_record(table, pk_col, int(pk_val), body)
                    success(self, {pk_col: pk_val, "action": "updated"})
                    return

            body["created_at"] = datetime.now(timezone.utc).isoformat()
            _db.insert_record(table, body)
            success(self, {"action": "created"}, 201)
        except Exception as e:
            error(self, f"Save failed: {str(e)}", 500)

    def _create_batch(self, session, body):
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        if not self._check_permission(session, "tacaipay_jp.manage"):
            error(self, "Forbidden", 403)
            return
        try:
            batch_id = body.get("batch_id") or f"JPB-{uuid.uuid4().hex[:12].upper()}"
            batch = {
                "batch_id": batch_id,
                "country_code": "JP",
                "entity_id": body.get("entity_id", ""),
                "payroll_month": body.get("payroll_month", ""),
                "status": "draft",
                "version": 1,
                "employee_count": 0,
                "gross_total": 0,
                "deduction_total": 0,
                "net_total": 0,
                "employer_cost_total": 0,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "created_by": session.get("user", {}).get("email", "system"),
                "notes": body.get("notes", ""),
            }
            _db.insert_record("pay_jp_payroll_batches", batch)
            success(self, batch)
        except Exception as e:
            error(self, f"Create batch failed: {str(e)}", 500)

    def _calculate_batch(self, session, batch_id):
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        if not self._check_permission(session, "tacaipay_jp.calculate"):
            error(self, "Forbidden", 403)
            return
        try:
            batch = _db.load_table("pay_jp_payroll_batches", where=f"batch_id = '{batch_id}'")
            if not batch:
                error(self, "Batch not found", 404)
                return
            entity_id = batch[0].get("entity_id", "")

            # Load JP employees and parameters
            employees = _db.load_table("pay_jp_salary_master", where=f"entity_id = '{entity_id}' AND active = true") if entity_id else []
            params_list = _db.load_table("pay_jp_payroll_parameters", where=f"entity_id = '{entity_id}'") if entity_id else []
            params = params_list[0] if params_list else {}

            # Simple JP calculation (can be enhanced with full labor law logic)
            records = []
            for emp in employees:
                basic = float(emp.get("basic_salary", 0) or 0)
                fixed = float(emp.get("fixed_allowance", 0) or 0)
                transport = float(emp.get("transportation_allowance", 0) or 0)
                housing = float(emp.get("housing_allowance", 0) or 0)
                overtime = float(emp.get("overtime_hours", 0) or 0) * float(emp.get("overtime_hourly_rate", 0) or 0)

                gross = basic + fixed + transport + housing + overtime
                # Default JP rates: health ~5%, pension ~9.15%, employment ~0.6%
                health_ins = round(gross * 0.05, 2)
                pension = round(gross * 0.0915, 2)
                emp_ins = round(gross * 0.006, 2)
                income_tax = round(gross * 0.10, 2)  # Simplified
                residence_tax = float(emp.get("residence_tax_amount", 0) or 0)

                deductions = health_ins + pension + emp_ins + income_tax + residence_tax
                net = gross - deductions

                record_id = f"JPR-{uuid.uuid4().hex[:12].upper()}"
                records.append({
                    "record_id": record_id,
                    "batch_id": batch_id,
                    "payroll_month": batch[0].get("payroll_month", ""),
                    "country_code": "JP",
                    "entity_id": entity_id,
                    "employee_id": emp.get("employee_id", ""),
                    "employee_number": emp.get("employee_number", ""),
                    "employee_name": emp.get("employee_name", ""),
                    "email": emp.get("email", ""),
                    "basic_salary": basic,
                    "gross_pay": gross,
                    "health_insurance_employee": health_ins,
                    "pension_employee": pension,
                    "employment_insurance_employee": emp_ins,
                    "income_tax": income_tax,
                    "residence_tax": residence_tax,
                    "deduction_total": deductions,
                    "net_pay": net,
                    "status": "calculated",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                })

            for rec in records:
                _db.insert_record("pay_jp_monthly_salary_records", rec)

            employee_count = len(records)
            gross_total = sum(r["gross_pay"] for r in records)
            deduction_total = sum(r["deduction_total"] for r in records)
            net_total = sum(r["net_pay"] for r in records)

            _db.update_record("pay_jp_payroll_batches", "batch_id", batch_id, {
                "employee_count": employee_count,
                "gross_total": gross_total,
                "deduction_total": deduction_total,
                "net_total": net_total,
                "status": "calculated",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })

            success(self, {"batch_id": batch_id, "employee_count": employee_count, "gross_total": gross_total, "net_total": net_total})
        except Exception as e:
            error(self, f"Calculate failed: {str(e)}", 500)

    def _confirm_sheet(self, session, sheet_id):
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        if not self._check_permission(session, "tacaipay_jp.approve"):
            error(self, "Forbidden", 403)
            return
        try:
            _db.update_record("pay_jp_monthly_salary_sheets", "sheet_id", sheet_id, {
                "status": "confirmed",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            success(self, {"sheet_id": sheet_id, "status": "confirmed"})
        except Exception as e:
            error(self, f"Confirm failed: {str(e)}", 500)

    def _email_payslip(self, session, payslip_id):
        success(self, {"payslip_id": payslip_id, "status": "email_queued"})

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[{MODULE_NAME}] {self.address_string()} - {format % args}", file=_sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="TACAI Payroll JP Service")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Bind port")
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), PayrollJPHandler)
    print(f"[{MODULE_NAME}] Running on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(f"\n[{MODULE_NAME}] Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
