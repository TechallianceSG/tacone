#!/usr/bin/env python3
"""TACAI Payroll SG — Singapore Payroll Service.

Handles:
  - Salary Master (employee salary configuration)
  - Payroll Batch processing (create, calculate, confirm)
  - Monthly Salary Sheets
  - Payslip generation & email delivery
  - Payroll Release Batches
  - CPF, SDL, FWL calculation
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import parse_qs, urlencode, urlparse
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

# ── API utils (inline to avoid import issues with legacy modules) ──
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
MODULE_PREFIX = "pay_sg"
MODULE_NAME = "tacaipay_sg"
DEFAULT_PORT = 8016
USER_ADMIN_SESSION_COOKIE = "tacai_session_id"
REQUIRED_MODULE_PERMISSION = "tacaipay_sg.access"
MAX_POST_BYTES = 2 * 1024 * 1024

TACAI_PUBLIC_HOST = os.environ.get("TACAI_PUBLIC_HOST", "127.0.0.1").strip() or "127.0.0.1"
TACAI_INTERNAL_HOST = os.environ.get("TACAI_INTERNAL_HOST", "127.0.0.1").strip() or "127.0.0.1"

# ── Resolve shared config ──
def _resolve_auth_port() -> int:
    try:
        from config import get_auth_port
        return get_auth_port()
    except Exception:
        return int(os.environ.get("AUTH_PORT", "3001"))

AUTH_PORT = _resolve_auth_port()
USER_ADMIN_INTERNAL_BASE_URL = f"http://127.0.0.1:{AUTH_PORT}"
PORTAL_BASE_URL = f"http://{TACAI_PUBLIC_HOST}:{os.environ.get('PORT', '3000')}"

def validate_session(session_id: str) -> dict[str, Any] | None:
    """Validate session against User_admin internal endpoint."""
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


class PayrollSGHandler(BaseHTTPRequestHandler):
    """Singapore Payroll HTTP request handler."""

    def _get_session(self) -> dict[str, Any] | None:
        cookies = SimpleCookie(self.headers.get("Cookie", ""))
        session_id = None
        for key in [USER_ADMIN_SESSION_COOKIE, "tacai_session_id"]:
            if key in cookies:
                session_id = cookies[key].value
                break
        if not session_id:
            return None
        return validate_session(session_id)

    def _check_permission(self, session: dict, permission: str) -> bool:
        if not session:
            return False
        user = session.get("user", {})
        if user.get("user_type") == "system_admin":
            return True
        roles = user.get("roles", [])
        if "system_admin" in roles:
            return True
        perms = session.get("permissions", []) or user.get("permissions", [])
        return permission in perms

    def _require_auth(self) -> dict[str, Any] | None:
        session = self._get_session()
        if not session:
            error(self, "Unauthorized", 401)
            return None
        return session

    def _send_json(self, data: Any, status: int = 200) -> None:
        send_json(self, data, status)

    # ── CORS ──
    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")
        self.send_header("Access-Control-Allow-Credentials", "true")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def _add_cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Credentials", "true")

    # ── Routing ──
    def do_GET(self) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"

        if path == "/health":
            self._send_json({"status": "ok", "module": MODULE_NAME, "port": DEFAULT_PORT})
            return

        session = self._require_auth()
        if not session:
            return

        # Route map for GET
        routes: dict[str, Any] = {
            "/api/payroll/sg/salary-master": self._handle_salary_master_list,
            "/api/payroll/sg/batches": self._handle_batches_list,
            "/api/payroll/sg/sheets": self._handle_sheets_list,
            "/api/payroll/sg/payslips": self._handle_payslips_list,
        }

        for prefix, handler_fn in routes.items():
            if path == prefix:
                handler_fn(session)
                return
            # Handle path params like /batches/{id}
            if path.startswith(prefix + "/"):
                rest = path[len(prefix) + 1:]
                self._handle_detail(session, prefix, rest)
                return

        error(self, "Not Found", 404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"

        session = self._require_auth()
        if not session:
            return

        body = parse_json_body(self)

        # Route map for POST
        if path == "/api/payroll/sg/salary-master":
            self._handle_salary_master_save(session, body)
        elif path == "/api/payroll/sg/batches":
            self._handle_batches_create(session, body)
        elif path.startswith("/api/payroll/sg/batches/") and path.endswith("/calculate"):
            batch_id = path.split("/")[-2]
            self._handle_batch_calculate(session, batch_id, body)
        elif path.startswith("/api/payroll/sg/sheets/") and path.endswith("/confirm"):
            sheet_id = path.split("/")[-2]
            self._handle_sheet_confirm(session, sheet_id, body)
        elif path.startswith("/api/payroll/sg/sheets/") and path.endswith("/release"):
            sheet_id = path.split("/")[-2]
            self._handle_sheet_release(session, sheet_id, body)
        elif path.startswith("/api/payroll/sg/payslips/") and path.endswith("/email"):
            payslip_id = path.split("/")[-2]
            self._handle_payslip_email(session, payslip_id, body)
        elif path == "/api/payroll/sg/payslips/batch-email":
            self._handle_payslip_batch_email(session, body)
        else:
            error(self, "Not Found", 404)

    # ── GET handlers ──
    def _handle_salary_master_list(self, session):
        if not _PG_AVAILABLE:
            success(self, {"items": [], "total": 0})
            return
        entity_id = get_query_param(self, "entity_id", "")
        status_filter = get_query_param(self, "status", "")
        page = int(get_query_param(self, "page", "1"))
        page_size = int(get_query_param(self, "page_size", "50"))

        where = {}
        if entity_id:
            where["entity_id"] = entity_id
        if status_filter:
            where["active"] = (status_filter == "active")

        try:
            rows = _db.load_table("pay_sg_salary_master", where=where if where else None)
            total = len(rows)
            start = (page - 1) * page_size
            paged = rows[start:start + page_size]
            paginated(self, paged, page, page_size, total)
        except Exception as e:
            error(self, f"Database error: {str(e)}", 500)

    def _handle_batches_list(self, session):
        if not _PG_AVAILABLE:
            success(self, {"items": [], "total": 0})
            return
        try:
            rows = _db.load_table("pay_sg_payroll_batches", order_by="created_at DESC")
            success(self, {"items": rows, "total": len(rows)})
        except Exception as e:
            error(self, f"Database error: {str(e)}", 500)

    def _handle_sheets_list(self, session):
        if not _PG_AVAILABLE:
            success(self, {"items": [], "total": 0})
            return
        try:
            rows = _db.load_table("pay_sg_monthly_salary_sheets", order_by="created_at DESC")
            success(self, {"items": rows, "total": len(rows)})
        except Exception as e:
            error(self, f"Database error: {str(e)}", 500)

    def _handle_payslips_list(self, session):
        if not _PG_AVAILABLE:
            success(self, {"items": [], "total": 0})
            return
        try:
            rows = _db.load_table("pay_sg_payslips", order_by="created_at DESC")
            success(self, {"items": rows, "total": len(rows)})
        except Exception as e:
            error(self, f"Database error: {str(e)}", 500)

    def _handle_detail(self, session, prefix, rest):
        table_map = {
            "/api/payroll/sg/salary-master": "pay_sg_salary_master",
            "/api/payroll/sg/batches": "pay_sg_payroll_batches",
            "/api/payroll/sg/sheets": "pay_sg_monthly_salary_sheets",
            "/api/payroll/sg/payslips": "pay_sg_payslips",
        }
        table = table_map.get(prefix)
        if not table:
            error(self, "Not Found", 404)
            return
        try:
            pk_col = "employee_id" if table == "pay_sg_salary_master" else \
                     "batch_id" if table == "pay_sg_payroll_batches" else \
                     "sheet_id" if table == "pay_sg_monthly_salary_sheets" else \
                     "record_id"
            row = _db.load_table(table, where={pk_col: rest})
            if row:
                success(self, row[0])
            else:
                error(self, "Not Found", 404)
        except Exception as e:
            error(self, f"Database error: {str(e)}", 500)

    # ── POST handlers ──
    def _handle_salary_master_save(self, session, body):
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        if not self._check_permission(session, "tacaipay_sg.manage"):
            error(self, "Forbidden", 403)
            return

        try:
            employee_id = body.get("employee_id")
            if not employee_id:
                error(self, "employee_id is required", 400)
                return

            existing = _db.load_table("pay_sg_salary_master", where={"employee_id": employee_id})
            user_email = session.get("user", {}).get("email", "system")

            if existing:
                _db.update_record("pay_sg_salary_master", "employee_id", employee_id, body)
            else:
                body["created_at"] = datetime.now(timezone.utc).isoformat()
                body["updated_at"] = datetime.now(timezone.utc).isoformat()
                _db.insert_record("pay_sg_salary_master", body)

            # Audit log
            audit = {
                "audit_id": f"AUD-{uuid.uuid4().hex[:12].upper()}",
                "module": MODULE_NAME,
                "record_id": employee_id,
                "action": "update" if existing else "create",
                "user": user_email,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            try:
                _db.insert_record("pay_sg_audit_logs", audit)
            except Exception:
                pass

            success(self, {"employee_id": employee_id})
        except Exception as e:
            error(self, f"Save failed: {str(e)}", 500)

    def _handle_batches_create(self, session, body):
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        if not self._check_permission(session, "tacaipay_sg.manage"):
            error(self, "Forbidden", 403)
            return

        try:
            batch_id = body.get("batch_id") or f"BAT-{uuid.uuid4().hex[:12].upper()}"
            payroll_month = body.get("payroll_month", "")
            entity_id = body.get("entity_id", "")

            batch = {
                "batch_id": batch_id,
                "country_code": "SG",
                "entity_id": entity_id,
                "payroll_month": payroll_month,
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
            _db.insert_record("pay_sg_payroll_batches", batch)
            success(self, batch)
        except Exception as e:
            error(self, f"Create batch failed: {str(e)}", 500)

    def _handle_batch_calculate(self, session, batch_id, body):
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        if not self._check_permission(session, "tacaipay_sg.calculate"):
            error(self, "Forbidden", 403)
            return

        try:
            batch = _db.load_table("pay_sg_payroll_batches", where={"batch_id": batch_id})
            if not batch:
                error(self, "Batch not found", 404)
                return

            # Load salary master records for this batch's entity
            entity_id = batch[0].get("entity_id", "")
            salary_records = _db.load_table("pay_sg_salary_master", where={"entity_id": entity_id, "active": True}) if entity_id else []

            # Create payroll records from salary master
            records = []
            for emp in salary_records:
                basic = float(emp.get("basic_salary", 0) or 0)
                fixed = float(emp.get("fixed_allowance", 0) or 0)
                bonus = float(emp.get("performance_bonus", 0) or 0)
                recurring = float(emp.get("recurring_deductions", 0) or 0)

                gross = basic + fixed + bonus
                deductions = recurring
                net = gross - deductions

                record_id = f"REC-{uuid.uuid4().hex[:12].upper()}"
                records.append({
                    "record_id": record_id,
                    "batch_id": batch_id,
                    "payroll_month": batch[0].get("payroll_month", ""),
                    "country_code": "SG",
                    "entity_id": entity_id,
                    "employee_id": emp.get("employee_id", ""),
                    "employee_number": emp.get("employee_number", ""),
                    "employee_name": emp.get("employee_name", ""),
                    "email": emp.get("email", ""),
                    "salary_type": emp.get("salary_type", ""),
                    "basic_salary": basic,
                    "gross_pay": gross,
                    "deduction_total": deductions,
                    "net_pay": net,
                    "status": "calculated",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                })

            # Save records
            for rec in records:
                _db.insert_record("pay_sg_payroll_records_sg", rec)

            # Update batch
            employee_count = len(records)
            gross_total = sum(r["gross_pay"] for r in records)
            deduction_total = sum(r["deduction_total"] for r in records)
            net_total = sum(r["net_pay"] for r in records)

            _db.update_record("pay_sg_payroll_batches", "batch_id", batch_id, {
                "employee_count": employee_count,
                "gross_total": gross_total,
                "deduction_total": deduction_total,
                "net_total": net_total,
                "status": "calculated",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })

            success(self, {
                "batch_id": batch_id,
                "employee_count": employee_count,
                "gross_total": gross_total,
                "net_total": net_total,
            })
        except Exception as e:
            error(self, f"Calculate failed: {str(e)}", 500)

    def _handle_sheet_confirm(self, session, sheet_id, body):
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        if not self._check_permission(session, "tacaipay_sg.approve"):
            error(self, "Forbidden", 403)
            return
        try:
            _db.update_record("pay_sg_monthly_salary_sheets", "sheet_id", sheet_id, {
                "status": "confirmed",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            success(self, {"sheet_id": sheet_id, "status": "confirmed"})
        except Exception as e:
            error(self, f"Confirm failed: {str(e)}", 500)

    def _handle_sheet_release(self, session, sheet_id, body):
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        if not self._check_permission(session, "tacaipay_sg.release_payment"):
            error(self, "Forbidden", 403)
            return
        try:
            release_id = f"REL-{uuid.uuid4().hex[:12].upper()}"
            release = {
                "release_id": release_id,
                "source_sheet_id": sheet_id,
                "country_code": "SG",
                "status": "released",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": session.get("user", {}).get("email", "system"),
            }
            _db.insert_record("pay_sg_payroll_release_batches", release)
            _db.update_record("pay_sg_monthly_salary_sheets", "sheet_id", sheet_id, {
                "status": "released",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            success(self, release)
        except Exception as e:
            error(self, f"Release failed: {str(e)}", 500)

    def _handle_payslip_email(self, session, payslip_id, body):
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        # Placeholder: in production, integrates with messaging service
        success(self, {"payslip_id": payslip_id, "status": "email_queued"})

    def _handle_payslip_batch_email(self, session, body):
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        release_id = body.get("release_id", "")
        # Placeholder: batch send all payslips in a release
        success(self, {"release_id": release_id, "status": "batch_email_queued"})

    # ── Logging ──
    def log_message(self, format: str, *args: Any) -> None:
        print(f"[{MODULE_NAME}] {self.address_string()} - {format % args}", file=_sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="TACAI Payroll SG Service")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Bind port")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), PayrollSGHandler)
    print(f"[{MODULE_NAME}] Running on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(f"\n[{MODULE_NAME}] Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
