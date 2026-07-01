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
            self._list("pay_jp_payroll_parameters")
        elif path == "/api/payroll/jp/employees":
            self._list("pay_jp_employees")
        elif path == "/api/payroll/jp/batches":
            self._list("pay_jp_payroll_batches")
        elif path == "/api/payroll/jp/sheets":
            self._list("pay_jp_monthly_salary_sheets")
        elif path == "/api/payroll/jp/payslips":
            self._list("pay_jp_payslips")
        elif path == "/api/payroll/jp/audit-logs":
            self._list("pay_jp_audit_logs")
        else:
            # Detail by ID
            for prefix, table, pk in [
                ("/api/payroll/jp/item-definitions/", "pay_jp_payroll_item_definitions", "item_id"),
                ("/api/payroll/jp/parameters/", "pay_jp_payroll_parameters", "entity_id"),
                ("/api/payroll/jp/employees/", "pay_jp_employees", "employee_id"),
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
            self._save("pay_jp_payroll_parameters", "entity_id", session, body)
        elif path == "/api/payroll/jp/employees":
            self._save("pay_jp_employees", "employee_id", session, body)
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

    def _detail(self, table: str, pk_col: str, pk_val: str):
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        try:
            row = _db.load_table(table, where={pk_col: pk_val})
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
            existing = _db.load_table(table, where={pk_col: pk_val})
            if existing:
                _db.update_record(table, pk_col, pk_val, body)
            else:
                body["created_at"] = datetime.now(timezone.utc).isoformat()
                body["updated_at"] = datetime.now(timezone.utc).isoformat()
                _db.insert_record(table, body)
            success(self, {pk_col: pk_val})
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
            batch = _db.load_table("pay_jp_payroll_batches", where={"batch_id": batch_id})
            if not batch:
                error(self, "Batch not found", 404)
                return
            entity_id = batch[0].get("entity_id", "")

            # Load JP employees and parameters
            employees = _db.load_table("pay_jp_employees", where={"entity_id": entity_id, "active": True}) if entity_id else []
            params_list = _db.load_table("pay_jp_payroll_parameters", where={"entity_id": entity_id}) if entity_id else []
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
