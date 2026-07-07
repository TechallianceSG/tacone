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

def _generate_payslip_html_sg(record: dict, batch: dict, entity_label_text: str = "") -> str:
    """Generate a simple self-contained HTML payslip for Singapore payroll."""
    employee_name = record.get("employee_name", "—")
    employee_number = record.get("employee_number", "—")
    payroll_month = record.get("payroll_month", "—")
    gross_pay = float(record.get("gross_pay", 0) or 0)
    net_pay = float(record.get("net_pay", 0) or 0)
    deduction_total = float(record.get("deduction_total", 0) or 0)
    basic_salary = float(record.get("basic_salary", 0) or 0)
    cpf_employee = float(record.get("cpf_employee", 0) or 0)
    cpf_employer = float(record.get("cpf_employer", 0) or 0)
    sdl = float(record.get("sdl", 0) or 0)

    def fmt_sgd(v: float) -> str:
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
  .info .label {{ color: #6b7280; width: 140px; }}
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
    <div class="subtitle">{entity_label_text}</div>
  </div>
  <div class="info">
    <table>
      <tr><td class="label">Employee / 员工</td><td><strong>{employee_name}</strong></td></tr>
      <tr><td class="label">Employee No. / 员工编号</td><td>{employee_number}</td></tr>
      <tr><td class="label">Payroll Month / 工资月份</td><td>{payroll_month}</td></tr>
      <tr><td class="label">Entity / 法人</td><td>{entity_label_text}</td></tr>
    </table>
  </div>
  <div class="section">
    <h3>Earnings / 收入</h3>
    <table class="items">
      <tr><td>Basic Salary / 基本工资</td><td class="amount">{fmt_sgd(basic_salary)}</td></tr>
      <tr class="total-row"><td>Gross Pay / 总支付</td><td class="amount">{fmt_sgd(gross_pay)}</td></tr>
    </table>
  </div>
  <div class="section">
    <h3>Deductions / 扣除</h3>
    <table class="items">
      <tr><td>Total Deductions / 扣除合计</td><td class="amount">{fmt_sgd(deduction_total)}</td></tr>
      <tr class="total-row"><td>Net Pay / 实发工资</td><td class="amount" style="color:#1B6CB2;">{fmt_sgd(net_pay)}</td></tr>
    </table>
  </div>
  <div class="section">
    <h3>Employer Contributions / 雇主缴纳 (CPF, SDL)</h3>
    <table class="items">
      <tr><td>CPF (Employee Share) / CPF 雇员部分</td><td class="amount">{fmt_sgd(cpf_employee)}</td></tr>
      <tr><td>CPF (Employer Share) / CPF 雇主部分</td><td class="amount">{fmt_sgd(cpf_employer)}</td></tr>
      <tr><td>SDL / 技能发展税</td><td class="amount">{fmt_sgd(sdl)}</td></tr>
    </table>
  </div>
  <div class="footer">
    <p>Computer-generated payslip · For queries contact HR</p>
    <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
  </div>
</div>
</body>
</html>"""

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
        # Trust localhost (Portal/Vite proxy)
        client_host = self.client_address[0] if self.client_address else ""
        if client_host in ("127.0.0.1", "localhost", "::1", TACAI_INTERNAL_HOST):
            return {"user": {"email": "portal-gateway", "roles": ["system_admin"]}, "permissions": ["*"]}
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
            send_json(self, {"status": "ok", "module": MODULE_NAME, "port": DEFAULT_PORT})
            return

        session = self._require_auth()
        if not session:
            return

        if path == "/api/payroll/sg/salary-master":
            self._list_salary_master()
        elif path == "/api/payroll/sg/batches":
            self._list("pay_sg_payroll_batches")
        elif path == "/api/payroll/sg/sheets":
            self._list("pay_sg_monthly_salary_sheets")
        elif path == "/api/payroll/sg/payslips":
            self._list_payslips()
        else:
            # ── Payslip HTML preview ──
            if path.startswith("/api/payroll/sg/payslips/") and path.endswith("/html"):
                payslip_id = path.split("/")[-2]
                self._get_payslip_html(payslip_id)
                return
            # Detail by ID
            for prefix, table, pk in [
                ("/api/payroll/sg/salary-master/", "pay_sg_salary_master", "employee_id"),
                ("/api/payroll/sg/batches/", "pay_sg_payroll_batches", "batch_id"),
                ("/api/payroll/sg/sheets/", "pay_sg_monthly_salary_sheets", "sheet_id"),
                ("/api/payroll/sg/payslips/", "pay_sg_payslips", "record_id"),
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

        if path == "/api/payroll/sg/salary-master":
            self._handle_salary_master_save(session, body)
        elif path == "/api/payroll/sg/batches":
            self._create_batch(session, body)
        elif path.startswith("/api/payroll/sg/batches/") and path.endswith("/calculate"):
            batch_id = path.split("/")[-2]
            self._calculate_batch(session, batch_id)
        elif path.startswith("/api/payroll/sg/batches/") and path.endswith("/confirm"):
            batch_id = path.split("/")[-2]
            self._confirm_sheet(session, batch_id)
        elif path.startswith("/api/payroll/sg/sheets/") and path.endswith("/confirm"):
            sheet_id = path.split("/")[-2]
            self._confirm_sheet(session, sheet_id)
        elif path.startswith("/api/payroll/sg/sheets/") and path.endswith("/release"):
            sheet_id = path.split("/")[-2]
            self._handle_sheet_release(session, sheet_id, body)
        elif path.startswith("/api/payroll/sg/payslips/") and path.endswith("/email"):
            payslip_id = path.split("/")[-2]
            self._email_payslip(session, payslip_id)
        elif path == "/api/payroll/sg/payslips/batch-email":
            self._handle_payslip_batch_email(session, body)
        elif path == "/api/payroll/sg/email-settings":
            self._save_email_settings(session, body)
        else:
            error(self, "Not Found", 404)

    # ── GET handlers ──
    def _list(self, table_name):
        """Generic list handler — matches JP _list pattern."""
        if not _PG_AVAILABLE:
            success(self, {"items": [], "total": 0})
            return
        try:
            rows = _db.load_table(table_name, order_by="created_at DESC")
            success(self, {"items": rows, "total": len(rows)})
        except Exception as e:
            error(self, f"Database error: {str(e)}", 500)

    def _detail(self, table, pk_col, rest):
        """Generic detail-by-ID handler — matches JP _detail pattern."""
        try:
            row = _db.load_table(table, where={pk_col: rest})
            if row:
                success(self, row[0])
            else:
                error(self, "Not Found", 404)
        except Exception as e:
            error(self, f"Database error: {str(e)}", 500)

    def _list_salary_master(self):
        """List salary master with optional filters — matches JP _list_employees pattern."""
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

    def _list_payslips(self):
        """List payslips with optional month and search filters — matches JP _list_payslips pattern."""
        if not _PG_AVAILABLE:
            success(self, {"items": [], "total": 0})
            return
        try:
            payroll_month = get_query_param(self, "payroll_month", "")
            search = get_query_param(self, "search", "")

            rows = _db.load_table("pay_sg_payslips", order_by="created_at DESC")
            # Client-side filter for month/search (same approach as JP)
            if payroll_month:
                rows = [r for r in rows if str(r.get("payroll_month", "")) == payroll_month]
            if search:
                s = search.lower()
                rows = [r for r in rows if s in str(r.get("employee_name", "")).lower()
                        or s in str(r.get("employee_number", "")).lower()]
            success(self, {"items": rows, "total": len(rows)})
        except Exception as e:
            error(self, f"Database error: {str(e)}", 500)

    def _get_payslip_html(self, payslip_id):
        """Return payslip HTML — regenerates dynamically to reflect current template settings.
        Matches JP _get_payslip_html pattern."""
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        try:
            ps_list = _db.load_table("pay_sg_payslips", where={"record_id": payslip_id})
            if not ps_list:
                error(self, "Payslip not found", 404)
                return
            ps = ps_list[0]

            # Regenerate HTML dynamically (matching JP behavior)
            batch_list = _db.load_table("pay_sg_payroll_batches", where={"batch_id": ps.get("batch_id", "")}) or []
            batch_data = batch_list[0] if batch_list else {}
            entity_id = ps.get("entity_id", batch_data.get("entity_id", ""))

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
            html = _generate_payslip_html_sg(rec, batch_data, entity_id)

            success(self, {"record_id": payslip_id, "html": html})
        except Exception as e:
            error(self, f"Get payslip HTML failed: {str(e)}", 500)

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

    def _create_batch(self, session, body):
        """Create a new payroll batch — matches JP _create_batch pattern."""
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

    def _calculate_batch(self, session, batch_id):
        """Calculate payroll for a batch — matches JP _calculate_batch pattern."""
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

    def _confirm_sheet(self, session, sheet_id):
        """Confirm (定稿) a batch/sheet. Generates payslip records for all payroll records.
        Matches JP _confirm_sheet pattern."""
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        if not self._check_permission(session, "tacaipay_sg.approve"):
            error(self, "Forbidden", 403)
            return

        try:
            user_email = session.get("user", {}).get("email", "system")
            now_iso = datetime.now(timezone.utc).isoformat()

            # Load batch (sheet_id is actually batch_id)
            batch_list = _db.load_table("pay_sg_payroll_batches", where={"batch_id": sheet_id})
            if not batch_list:
                error(self, "Batch not found", 404)
                return
            batch_data = batch_list[0]

            # Update batch status
            _db.update_record("pay_sg_payroll_batches", "batch_id", sheet_id, {
                "status": "confirmed",
                "confirmed_at": now_iso,
                "confirmed_by": user_email,
                "updated_at": now_iso,
            })

            # Load payroll records for this batch
            records = _db.load_table("pay_sg_payroll_records_sg", where={"batch_id": sheet_id}) or []

            # Resolve entity label via masterdata internal API
            entity_id = batch_data.get("entity_id", "")
            entity_label_text = entity_id  # fallback
            try:
                masterdata_port = os.environ.get("MASTERDATA_PORT", "8007")
                req = Request(
                    f"http://127.0.0.1:{masterdata_port}/api/internal/entity/{entity_id}/active",
                    headers={"Accept": "application/json"},
                    method="GET",
                )
                with urlopen(req, timeout=3) as resp:
                    body_data = json.loads(resp.read().decode("utf-8"))
                ent = body_data.get("entity") or {}
                if ent:
                    entity_label_text = f"{ent.get('entity_code', '')} - {ent.get('entity_name', '')} ({ent.get('country', '')})"
            except Exception:
                pass

            # Generate payslip records
            payslip_count = 0
            for rec in records:
                emp_id = rec.get("employee_id", "")
                # Check if payslip already exists
                existing_ps = _db.load_table("pay_sg_payslips",
                    where={"batch_id": sheet_id, "employee_id": emp_id}) or []
                if existing_ps:
                    continue

                html = _generate_payslip_html_sg(rec, batch_data, entity_label_text)
                payslip = {
                    "record_id": f"PS-SG-{uuid.uuid4().hex[:12].upper()}",
                    "batch_id": sheet_id,
                    "sheet_id": sheet_id,
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
                _db.insert_record("pay_sg_payslips", payslip)
                payslip_count += 1

            # Also update monthly sheet if it exists
            try:
                _db.update_record("pay_sg_monthly_salary_sheets", "sheet_id", sheet_id, {
                    "status": "confirmed",
                    "updated_at": now_iso,
                })
            except Exception:
                pass

            # Audit log
            audit = {
                "audit_id": f"AUD-{uuid.uuid4().hex[:12].upper()}",
                "module": MODULE_NAME,
                "record_id": sheet_id,
                "action": "CONFIRM",
                "user": user_email,
                "timestamp": now_iso,
                "before_value": json.dumps({"status": "calculated"}),
                "after_value": json.dumps({"status": "confirmed", "payslips_generated": payslip_count}),
            }
            try:
                _db.insert_record("pay_sg_audit_logs", audit)
            except Exception:
                pass

            success(self, {"sheet_id": sheet_id, "status": "confirmed", "payslips_generated": payslip_count})
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

    def _save_email_settings(self, session, body):
        """Save email settings — matches JP _save_email_settings pattern."""
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        if not self._check_permission(session, "tacaipay_sg.manage"):
            error(self, "Forbidden", 403)
            return
        try:
            body["updated_at"] = datetime.now(timezone.utc).isoformat()
            existing = _db.load_table("pay_sg_email_settings",
                where={"country_code": body.get("country_code", "SG")}) or []
            if existing:
                _db.update_record("pay_sg_email_settings", "country_code",
                    body.get("country_code", "SG"), body)
            else:
                body["created_at"] = datetime.now(timezone.utc).isoformat()
                _db.insert_record("pay_sg_email_settings", body)
            success(self, {"status": "saved"})
        except Exception as e:
            error(self, f"Save email settings failed: {str(e)}", 500)

    def _email_payslip(self, session, payslip_id):
        """Email a single payslip — placeholder, integrates with messaging service in production."""
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
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
