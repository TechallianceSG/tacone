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
from datetime import date, datetime, timedelta, timezone
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

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

from auth_utils import validate_session, has_permission, is_system_admin
from cors_middleware import add_cors_headers, handle_preflight
from api_utils import send_json, success, error, paginated


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


# validate_session() is imported from shared auth_utils below


# ── SMTP Configuration ──
SMTP_HOST = os.environ.get("SMTP_HOST", "").strip()
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "").strip()
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "").strip()
SMTP_FROM = os.environ.get("SMTP_FROM", "").strip()
SMTP_FROM_NAME = os.environ.get("SMTP_FROM_NAME", "TACAI Payroll JP").strip()
SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"


def is_smtp_configured() -> bool:
    """Check if SMTP settings are properly configured."""
    return bool(SMTP_HOST and SMTP_PORT and SMTP_USER and SMTP_PASSWORD and SMTP_FROM)


def _send_email(to_email: str, subject: str, html_body: str, attachments: list | None = None) -> tuple[bool, str]:
    """Send email via SMTP. Returns (success, error_message).

    Uses smtplib + email.mime from Python standard library.
    If SMTP is not configured, returns (False, 'SMTP not configured').
    """
    if not is_smtp_configured():
        return (False, "SMTP not configured")

    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.base import MIMEBase
    from email import encoders

    try:
        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM}>"
        msg["To"] = to_email
        msg["Date"] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0900")

        # Attach HTML body
        html_part = MIMEText(html_body, "html", "utf-8")
        msg.attach(html_part)

        # Attach files if any
        if attachments:
            for att in attachments:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(att.get("content", b""))
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f'attachment; filename="{att.get("filename", "attachment")}"')
                msg.attach(part)

        # Connect and send
        if SMTP_USE_TLS:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15)
            server.starttls()
        else:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15)

        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_FROM, [to_email], msg.as_string())
        server.quit()

        return (True, "")
    except Exception as e:
        return (False, str(e))


def _write_audit_log(handler, action: str, table_name: str, record_id: str,
                      user_name: str, before_value=None, after_value=None):
    """Write a single audit log entry to pay_jp_audit_logs.

    Called on every calculation, edit, confirm, rollback, and email send action.
    """
    if not _PG_AVAILABLE:
        return
    try:
        import json as _json
        log_entry = {
            "module": "pay_jp",
            "record_id": str(record_id),
            "action": str(action),
            "user_name": str(user_name),
            "table_name": str(table_name),
            "before_value": _json.dumps(before_value, ensure_ascii=False, default=str) if before_value is not None else None,
            "after_value": _json.dumps(after_value, ensure_ascii=False, default=str) if after_value is not None else None,
            "ip_address": handler.client_address[0] if hasattr(handler, 'client_address') else "",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _db.insert_record("pay_jp_audit_logs", log_entry)
    except Exception as e:
        print(f"[{MODULE_NAME}] Audit log write failed: {e}", file=_sys.stderr)


def _generate_payslip_html(record: dict, batch: dict, entity_label_text: str) -> str:
    """Generate a self-contained HTML payslip from a monthly salary record.

    Used for both preview and email sending. Returns a complete HTML document
    with embedded CSS suitable for email clients.
    """
    fmt = lambda v: f"¥{int(v or 0):,}"  # noqa: E731

    emp_name = record.get("employee_name", "")
    emp_num = record.get("employee_number", "")
    payroll_month = record.get("payroll_month", "") or batch.get("payroll_month", "")
    salary_type = record.get("salary_type", "monthly")
    department_label = record.get("department_label", "")

    # Earnings items
    earnings = []
    earning_keys = [
        ("base_pay_calculated", "基本給 / Base Pay"),
        ("commute_allowance", "通勤手当 / Commute Allowance"),
        ("housing_allowance", "住宅手当 / Housing Allowance"),
        ("family_allowance", "家族手当 / Family Allowance"),
        ("position_allowance", "役職手当 / Position Allowance"),
        ("fixed_allowance", "固定手当 / Fixed Allowance"),
        ("transport_allowance", "交通費 / Transport"),
        ("phone_allowance", "電話手当 / Phone Allowance"),
        ("performance_bonus", "業績賞与 / Performance Bonus"),
        ("project_bonus", "PJ賞与 / Project Bonus"),
    ]
    for key, label in earning_keys:
        val = float(record.get(key) or 0)
        if val > 0:
            earnings.append((label, val))

    # Deduction items
    deductions = []
    deduction_keys = [
        ("health_insurance_employee", "健康保険 / Health Insurance"),
        ("pension_employee", "厚生年金 / Pension"),
        ("care_insurance_employee", "介護保険 / Nursing Care"),
        ("employment_insurance_employee", "雇用保険 / Employment Insurance"),
        ("income_tax", "所得税 / Income Tax"),
        ("monthly_resident_tax", "住民税 / Resident Tax"),
        ("recurring_deductions", "その他控除 / Other Deductions"),
    ]
    for key, label in deduction_keys:
        val = float(record.get(key, record.get(key.replace("_employee", ""), 0)) or 0)
        if val > 0:
            deductions.append((label, val))

    gross = float(record.get("gross_pay") or 0)
    deduct_total = float(record.get("deduction_total") or 0)
    net = float(record.get("net_pay") or 0)
    employer_cost = float(record.get("employer_cost_total") or 0)

    def _build_rows(items, total_val, total_label):
        rows = ""
        for label, amount in items:
            rows += f'<tr><td style="padding:6px 10px;border-bottom:1px solid #eee;">{label}</td><td style="padding:6px 10px;text-align:right;border-bottom:1px solid #eee;">{fmt(amount)}</td></tr>'
        rows += f'<tr style="font-weight:700;font-size:15px;color:#1B6CB2;"><td style="padding:8px 10px;border-top:2px solid #1d2a3a;">{total_label}</td><td style="padding:8px 10px;text-align:right;border-top:2px solid #1d2a3a;">{fmt(total_val)}</td></tr>'
        return rows

    # Employer cost breakdown
    employer_items = []
    employer_keys = [
        ("employer_health", "健康保険 / Health Insurance (Employer)"),
        ("employer_pension", "厚生年金 / Pension (Employer)"),
        ("employer_care", "介護保険 / Nursing Care (Employer)"),
        ("employer_employ", "雇用保険 / Employment Insurance (Employer)"),
        ("employer_child_allowance", "児童手当拠出金 / Child Allowance Contribution"),
        ("employer_accident_insurance", "労災保険 / Accident Insurance"),
    ]
    for key, label in employer_keys:
        val = float(record.get(key) or 0)
        if val > 0:
            employer_items.append((label, val))

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head><meta charset="utf-8"><title>給与明細 / Payslip — {payroll_month}</title></head>
<body style="margin:0;padding:0;font-family:'Helvetica Neue',Arial,'Hiragino Sans','Noto Sans JP',sans-serif;font-size:14px;color:#1a1a2e;line-height:1.5;">
<div style="max-width:700px;margin:0 auto;background:#fff;">
  <div style="background:linear-gradient(135deg,#0f2b46,#1a4a7a);color:#fff;padding:20px 28px;">
    <h2 style="margin:0 0 4px;font-size:20px;font-weight:800;">📄 給与明細 / Payslip</h2>
    <p style="margin:0;opacity:.85;font-size:13px;">{entity_label_text}</p>
  </div>
  <div style="padding:20px 28px;border:1px solid #e5e7eb;border-top:none;">
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px 20px;margin-bottom:16px;padding:12px 16px;background:#f9fafb;border-radius:8px;">
      <div><span style="color:#6b7280;font-size:11px;text-transform:uppercase;">支給月 / Payroll Month</span><br><strong>{payroll_month}</strong></div>
      <div><span style="color:#6b7280;font-size:11px;text-transform:uppercase;">社員名 / Employee</span><br><strong>{emp_name}</strong></div>
      <div><span style="color:#6b7280;font-size:11px;text-transform:uppercase;">社員番号 / Employee No.</span><br><strong>{emp_num}</strong></div>
      <div><span style="color:#6b7280;font-size:11px;text-transform:uppercase;">給与形態 / Salary Type</span><br><strong>{salary_type}</strong></div>
      <div><span style="color:#6b7280;font-size:11px;text-transform:uppercase;">部署 / Department</span><br><strong>{department_label or '-'}</strong></div>
      <div><span style="color:#6b7280;font-size:11px;text-transform:uppercase;">通貨 / Currency</span><br><strong>JPY</strong></div>
    </div>

    <h3 style="font-size:14px;color:#1d2a3a;border-bottom:2px solid #1B6CB2;padding-bottom:4px;margin:16px 0 8px;">💰 支給項目 / Earnings</h3>
    <table style="width:100%;border-collapse:collapse;margin:6px 0;">
      {_build_rows(earnings, gross, '支給総額 / Gross Pay')}
    </table>

    <h3 style="font-size:14px;color:#1d2a3a;border-bottom:2px solid #1B6CB2;padding-bottom:4px;margin:16px 0 8px;">📉 控除項目 / Deductions</h3>
    <table style="width:100%;border-collapse:collapse;margin:6px 0;">
      {_build_rows(deductions, deduct_total, '控除合計 / Total Deductions')}
    </table>

    <table style="width:100%;border-collapse:collapse;margin:14px 0;">
      <tr style="font-weight:800;font-size:17px;color:#059669;">
        <td style="padding:12px;background:#ecfdf5;border-radius:8px;">💵 差引支給額 / Net Pay</td>
        <td style="padding:12px;text-align:right;background:#ecfdf5;border-radius:8px;">{fmt(net)}</td>
      </tr>
    </table>

    <h3 style="font-size:14px;color:#1d2a3a;border-bottom:2px solid #1B6CB2;padding-bottom:4px;margin:16px 0 8px;">🏢 会社負担 / Employer Cost</h3>
    <table style="width:100%;border-collapse:collapse;margin:6px 0;">
      {_build_rows(employer_items, employer_cost, '会社負担総額 / Total Employer Cost')}
    </table>

    <div style="margin-top:20px;text-align:center;color:#9ca3af;font-size:11px;border-top:1px solid #e5e7eb;padding-top:14px;">
      <p style="margin:0;">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} · Computer-generated payslip · For queries contact HR</p>
    </div>
  </div>
</div>
</body>
</html>"""
    return html


def _calc_fiscal_age(employee_id: str) -> int | None:
    """Calculate age at fiscal year start (April 1) from employee's date_of_birth.

    Returns None if DOB is unavailable or cannot be parsed.
    Used for 介護保険 eligibility (40-64 years old).
    """
    if not employee_id or not _PG_AVAILABLE:
        return None
    try:
        rows = _db.load_table("emp_employees", where={"employee_id": employee_id})
        if not rows:
            return None
        profile = rows[0].get("profile", {})
        if isinstance(profile, str):
            import json as _json
            profile = _json.loads(profile)
        dob = profile.get("date_of_birth", "")
        if not dob:
            return None
        dob_date = datetime.strptime(dob, "%Y-%m-%d").date()
        # Fiscal year start: April 1 of the current calendar year
        today = datetime.now(timezone.utc).date()
        fiscal_start = date(today.year, 4, 1)
        if today < fiscal_start:
            fiscal_start = date(today.year - 1, 4, 1)
        age = fiscal_start.year - dob_date.year
        if (fiscal_start.month, fiscal_start.day) < (dob_date.month, dob_date.day):
            age -= 1
        return age
    except Exception:
        return None


class PayrollJPHandler(BaseHTTPRequestHandler):

    def _get_session(self) -> dict[str, Any] | None:
        cookies = SimpleCookie(self.headers.get("Cookie", ""))
        for key in [USER_ADMIN_SESSION_COOKIE, "tacai_session_id"]:
            if key in cookies:
                return validate_session(session_id=cookies[key].value)
        return None

    def _check_permission(self, user: dict, permission: str) -> bool:
        if not user:
            return False
        if is_system_admin(user):
            return True
        return has_permission(user, permission)

    def _require_auth(self) -> dict[str, Any] | None:
        # Trust Portal gateway — auth already validated by Portal before proxying.
        # Portal forwards requests from localhost; skip redundant session validation.
        client_host = self.client_address[0] if self.client_address else ""
        if client_host in ("127.0.0.1", "localhost", "::1"):
            return {"user": {"email": "portal-gateway", "roles": ["system_admin"]}, "permissions": ["tacaipay_jp.access", "tacaipay_jp.manage", "tacaipay_jp.calculate", "tacaipay_jp.approve"]}
        # Direct access (non-localhost) — validate session with User_admin
        user = self._get_session()
        if not user:
            error(self, "Unauthorized", 401)
            return None
        return user

    def do_OPTIONS(self) -> None:
        handle_preflight(self)

    # ── Routing ──
    def do_GET(self) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"

        if path == "/health":
            send_json(self, {"status": "ok", "module": MODULE_NAME, "port": DEFAULT_PORT})
            return

        session = self._require_auth()
        if not session:
            return

        if path == "/api/payroll/jp/entities":
            self._list_md_table("md_entities", "entity_code")
        elif path == "/api/payroll/jp/departments":
            self._list_md_table("md_departments", "department_code")
        elif path == "/api/payroll/jp/teams":
            self._list_md_table("md_teams", "team_code")
        elif path == "/api/payroll/jp/item-definitions":
            self._list_item_definitions()
        elif path == "/api/payroll/jp/rate-type-labels":
            self._list_rate_type_labels()
        elif path == "/api/payroll/jp/parameters":
            self._list_parameters()
        elif path == "/api/payroll/jp/employees/importable":
            self._list_importable_employees()
        elif path == "/api/payroll/jp/employees":
            self._list("pay_jp_salary_master")
        elif path == "/api/payroll/jp/batches":
            self._list("pay_jp_payroll_batches")
        elif path == "/api/payroll/jp/payslips":
            self._list("pay_jp_payslips")
        elif path == "/api/payroll/jp/audit-logs":
            self._list("pay_jp_audit_logs")
        else:
            # ── Batch-level audit logs ──
            if path.startswith("/api/payroll/jp/batches/") and path.endswith("/audit-logs"):
                batch_id = path.split("/")[-2]
                self._get_batch_audit_logs(batch_id)
                return
            # ── Payslip HTML preview ──
            if path.startswith("/api/payroll/jp/payslips/") and path.endswith("/html"):
                payslip_id = path.split("/")[-2]
                self._get_payslip_html(payslip_id)
                return
            # ── SMTP health check ──
            if path == "/api/payroll/jp/smtp-status":
                send_json(self, {"smtp_configured": is_smtp_configured()})
                return
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
        elif path.startswith("/api/payroll/jp/employees/") and path.endswith("/activate"):
            emp_id = path.split("/")[-2]
            self._activate_employee(session, emp_id)
        elif path == "/api/payroll/jp/batches":
            self._create_batch(session, body)
        elif path.startswith("/api/payroll/jp/batches/") and path.endswith("/calculate"):
            batch_id = path.split("/")[-2]
            self._calculate_batch(session, batch_id)
        elif path.startswith("/api/payroll/jp/batches/") and path.endswith("/rollback"):
            batch_id = path.split("/")[-2]
            self._rollback_batch(session, batch_id, body)
        elif path.startswith("/api/payroll/jp/batches/") and path.endswith("/void"):
            batch_id = path.split("/")[-2]
            self._void_batch(session, batch_id, body)
        elif path.startswith("/api/payroll/jp/batches/") and path.endswith("/recalculate"):
            # Single record recalculate: /batches/{batch_id}/records/{record_id}/recalculate
            parts = path.split("/")
            if len(parts) >= 6 and parts[-3] == "records":
                record_id = parts[-2]
                self._recalculate_single_record(session, record_id)
            else:
                error(self, "Invalid recalculate path", 400)
        elif path.startswith("/api/payroll/jp/batches/") and path.endswith("/payslips/send-all"):
            batch_id = path.split("/")[-3]
            self._send_all_payslips(session, batch_id)
        elif path.startswith("/api/payroll/jp/batches/") and path.endswith("/payslips/send-selected"):
            batch_id = path.split("/")[-3]
            self._send_selected_payslips(session, batch_id, body)
        elif path.startswith("/api/payroll/jp/batches/") and path.endswith("/confirm"):
            batch_id = path.split("/")[-2]
            self._confirm_sheet(session, batch_id)
        elif path.startswith("/api/payroll/jp/payslips/") and path.endswith("/send"):
            payslip_id = path.split("/")[-2]
            self._send_single_payslip(session, payslip_id)
        elif path.startswith("/api/payroll/jp/payslips/") and path.endswith("/email"):
            payslip_id = path.split("/")[-2]
            self._email_payslip(session, payslip_id)
        else:
            error(self, "Not Found", 404)

    def do_PUT(self) -> None:
        """Handle PUT requests — used for editing individual records."""
        path = urlparse(self.path).path.rstrip("/") or "/"
        session = self._require_auth()
        if not session:
            return
        body = parse_json_body(self)

        # PUT /api/payroll/jp/batches/{batch_id}/records/{record_id}
        if "/api/payroll/jp/batches/" in path and "/records/" in path:
            # Extract record_id from path
            parts = path.split("/")
            record_id = parts[-1]
            self._edit_record(session, record_id, body)
        else:
            error(self, "Not Found", 404)

    def do_DELETE(self) -> None:
        """Handle DELETE requests — used for deleting voided batches and records."""
        path = urlparse(self.path).path.rstrip("/") or "/"
        session = self._require_auth()
        if not session:
            return

        # DELETE /api/payroll/jp/batches/{batch_id}
        if path.startswith("/api/payroll/jp/batches/"):
            batch_id = path.split("/")[-1]
            self._delete_batch(session, batch_id)
        elif path.startswith("/api/payroll/jp/sheets/"):
            # Legacy sheets path — redirect to batches
            batch_id = path.split("/")[-1]
            self._delete_batch(session, batch_id)
        else:
            error(self, "Not Found", 404)

    # ── DB helpers ──
    def _list(self, table: str):
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        try:
            rows = _db.load_table(table, order_by="created_at DESC")
            paginated(self, rows, 1, len(rows), len(rows))
        except Exception as e:
            error(self, f"Database error: {str(e)}", 500)

    def _list_md_table(self, table: str, order_col: str):
        """Read master data via masterdata internal API (no direct DB reads)."""
        endpoint_map = {
            "md_entities": "/api/internal/entities/active",
            "md_departments": "/api/internal/departments",
            "md_teams": "/api/internal/teams",
        }
        endpoint = endpoint_map.get(table)
        if not endpoint:
            error(self, f"Unknown master data table: {table}", 400)
            return
        try:
            req = Request(
                f"http://127.0.0.1:8007{endpoint}",
                headers={"Accept": "application/json"},
                method="GET",
            )
            with urlopen(req, timeout=3) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            # Extract the list key (entities, departments, or teams)
            data = body.get("entities") or body.get("departments") or body.get("teams") or []
            paginated(self, data, 1, len(data), len(data))
        except Exception as e:
            error(self, f"Masterdata service unavailable: {str(e)}", 502)

    def _list_item_definitions(self):
        """Return payroll item definitions sorted by display_order."""
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        try:
            rows = _db.load_table("pay_jp_payroll_item_definitions", order_by="display_order ASC")
            paginated(self, rows, 1, len(rows), len(rows))
        except Exception as e:
            error(self, f"Database error: {str(e)}", 500)

    def _list_rate_type_labels(self):
        """Return rate_type label dictionary, optionally filtered by category."""
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        try:
            cat = get_query_param(self, "category", "").strip()
            where = {"category": cat} if cat else None
            rows = _db.load_table("pay_jp_rate_type_labels", where=where, order_by="display_order")
            paginated(self, rows, 1, len(rows), len(rows))
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

            paginated(self, all_items, 1, len(all_items), len(all_items))
        except Exception as e:
            error(self, f"Database error: {str(e)}", 500)

    def _detail(self, table: str, pk_col: str, pk_val: str):
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        try:
            row = _db.load_table(table, where={pk_col: pk_val})
            if not row:
                error(self, "Not Found", 404)
                return
            data = row[0]

            # ── For batches: also include monthly salary records ──
            if table == "pay_jp_payroll_batches":
                batch_id = data.get("batch_id", pk_val)
                records = _db.load_table("pay_jp_monthly_salary_records",
                    where={"batch_id": batch_id}, order_by="employee_number ASC")
                data["records"] = records or []

            success(self, data)
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
            # Get employees from employee_admin internal API (with payroll data)
            req = Request(
                "http://127.0.0.1:8004/api/internal/employees?include_payroll=true",
                headers={"Accept": "application/json"},
                method="GET",
            )
            with urlopen(req, timeout=5) as resp:
                ea_body = json.loads(resp.read().decode("utf-8"))
            ea_employees = ea_body.get("employees") or []
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
            paginated(self, result, 1, len(result), len(result))
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

                # Load employee from employee_admin internal API
                try:
                    req = Request(
                        f"http://127.0.0.1:8004/api/internal/employees/{emp_id}?include_payroll=true",
                        headers={"Accept": "application/json"},
                        method="GET",
                    )
                    with urlopen(req, timeout=3) as resp:
                        ea_body = json.loads(resp.read().decode("utf-8"))
                    ea = ea_body.get("employee")
                except Exception:
                    continue
                if not ea:
                    continue

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
                    "standard_work_hours": float(payroll.get("standard_work_hours", 176) or 176),
                    "standard_monthly_hours": float(payroll.get("standard_monthly_hours", 160) or 160),
                    "commute_allowance": float(payroll.get("commute_allowance", 0) or 0),
                    "transport_allowance": float(payroll.get("transport_allowance", 0) or 0),
                    "phone_allowance": float(payroll.get("phone_allowance", 0) or 0),
                    "project_bonus": float(payroll.get("project_bonus", 0) or 0),
                    "social_insurance_eligible": payroll.get("social_insurance_eligible", True),
                    "employment_insurance_eligible": payroll.get("employment_insurance_eligible", True),
                    "age_at_fiscal_year_start": _calc_fiscal_age(ea.get("employee_id", emp_id)) or int(payroll.get("age_at_fiscal_year_start", 0) or 0),
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

            user_email = session.get("email", "system")
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
            existing = _db.load_table("pay_jp_salary_master", where={"employee_id": emp_id})
            if not existing:
                error(self, "Employee not found", 404)
                return
            reason = body.get("deactivation_reason", "") if body else ""
            user_email = session.get("email", "system")
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

    def _activate_employee(self, session, emp_id):
        """Re-activate a deactivated employee in salary master."""
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        if not self._check_permission(session, "tacaipay_jp.manage"):
            error(self, "Forbidden", 403)
            return
        try:
            existing = _db.load_table("pay_jp_salary_master", where={"employee_id": emp_id})
            if not existing:
                error(self, "Employee not found", 404)
                return
            user_email = session.get("email", "system")
            now_iso = datetime.now(timezone.utc).isoformat()
            _db.update_record("pay_jp_salary_master", "employee_id", emp_id, {
                "active": True,
                "deactivated_at": None,
                "deactivated_by": None,
                "deactivation_reason": None,
                "updated_at": now_iso,
            })
            _write_audit_log(self, "ACTIVATE", "pay_jp_salary_master", emp_id,
                            user_email,
                            before_value={"active": False},
                            after_value={"active": True})
            success(self, {"employee_id": emp_id, "status": "activated"})
        except Exception as e:
            error(self, f"Activate failed: {str(e)}", 500)

    def _calc_preview(self, emp_id):
        """Calculate salary preview for an employee based on their salary type."""
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        try:
            rows = _db.load_table("pay_jp_salary_master", where={"employee_id": emp_id})
            if not rows:
                error(self, "Employee not found", 404)
                return
            emp = rows[0]

            # Parse query params
            actual_hours = float(get_query_param(self, "actual_hours", "0") or "0")
            actual_days = float(get_query_param(self, "actual_days", "0") or "0")
            absence_days = float(get_query_param(self, "absence_days", "0") or "0")
            working_days = float(get_query_param(self, "working_days_in_month", "22") or "22")

            # Overlay query params onto emp for calculation
            emp["absence_days"] = absence_days
            emp["actual_work_days"] = actual_days
            emp["actual_work_hours"] = actual_hours

            salary_type = (emp.get("salary_type") or "monthly").strip()
            result = self._calc_salary_by_type(emp, salary_type, actual_hours, actual_days, working_days)

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

    def _lookup_insurance_rate(self, rate_type: str, prefecture_code: str | None = None,
                                category: str | None = None):
        """Look up employee and employer insurance rates from the parameter table.

        Precedence: exact prefecture/category match → national default (prefecture IS NULL).
        For 'employment' rate_type, use category (e.g. 'agri_const' for 0.60%).
        Returns (employee_rate, employer_rate) or (0, 0) if not found.
        """
        if not _PG_AVAILABLE:
            return (0, 0)
        try:
            # Try prefecture/category-specific first, then national default
            if prefecture_code or category:
                filter_val = prefecture_code or category
                rows = _db.load_table("pay_jp_social_insurance_rates",
                    where="rate_type = %s AND is_current = true AND (prefecture = %s OR prefecture IS NULL)",
                    params=(rate_type, filter_val),
                    order_by="prefecture NULLS LAST")
            else:
                rows = _db.load_table("pay_jp_social_insurance_rates",
                    where="rate_type = %s AND is_current = true AND prefecture IS NULL",
                    params=(rate_type,))
            if rows:
                r = rows[0]
                return (float(r.get("employee_rate") or 0) / 100.0,
                        float(r.get("employer_rate") or 0) / 100.0)
        except Exception:
            pass
        return (0, 0)

    def _lookup_standard_remuneration(self, monthly_amount, grade_type="health_insurance"):
        """Look up standard monthly remuneration (標準報酬月額) from grade table.

        Japanese social insurance premiums are calculated on the standard monthly
        remuneration determined by grade brackets, NOT on actual gross pay.

        Args:
            monthly_amount: The employee's reference monthly remuneration
            grade_type: 'health_insurance' or 'pension_insurance'

        Returns:
            The standard_monthly_amount for the matching grade, or the input
            monthly_amount as fallback if the grade table is unavailable.
        """
        if not _PG_AVAILABLE:
            return monthly_amount
        try:
            rows = _db.load_table("pay_jp_standard_remuneration_grades",
                where="grade_type = %s AND min_monthly_amount <= %s "
                      "AND max_monthly_amount > %s AND is_current = true",
                params=(grade_type, int(monthly_amount), int(monthly_amount)))
            if rows:
                return float(rows[0].get("standard_monthly_amount") or monthly_amount)
        except Exception:
            pass
        return monthly_amount

    def _lookup_withholding_tax(self, taxable_income, dependents_count=0):
        """Look up withholding tax amount from monthly tax bracket table.

        Follows Japanese NTA standard: taxable income is truncated to the
        nearest 1,000 yen (千円未満切捨て) before bracket lookup.

        Falls back to 5% simplified rate if the table is unavailable.

        Args:
            taxable_income: Salary after social insurance deductions
            dependents_count: Number of dependents declared by the employee

        Returns:
            Monthly withholding tax amount in JPY.
        """
        if not _PG_AVAILABLE:
            return round(taxable_income * 0.05, 0)
        try:
            # 千円未満切捨て — Japanese tax law standard
            truncated = (int(taxable_income) // 1000) * 1000
            dep_col = f"tax_dep_{min(int(dependents_count), 7)}"
            # Standard Japanese tax table: [以上, 未満) — inclusive lower bound,
            # exclusive upper bound. 千円未満切捨て applied above.
            # Boundary values (truncated == min_salary) go to the higher bracket.
            # Documented in docs/JP_PAYROLL_CALCULATION_FORMULAS.md §税表边界处理
            rows = _db.load_table("pay_jp_withholding_tax_brackets",
                where="table_type = %s AND min_salary <= %s "
                      "AND max_salary > %s AND is_current = true",
                params=('monthly', truncated, truncated))
            if rows:
                return float(rows[0].get(dep_col) or 0)
        except Exception:
            pass
        # Fallback to simplified 5% if bracket lookup fails
        return round(taxable_income * 0.05, 0)

    def _calc_salary_by_type(self, emp, salary_type, actual_hours, actual_days, working_days_in_month=22):
        """Salary-type-specific calculation logic.

        日本薪资计算核心函数。根据 salary_type 执行不同的计算逻辑。

        支持 5 种计算方式，详见 docs/JP_PAYROLL_CALCULATION_FORMULAS.md：
        - monthly (月給制):          base = basic_salary × (working_days - absence_days) / working_days
                                     正社員向け。欠勤控除あり。
        - hourly (時給制):           base = hourly_rate × actual_hours
                                     パート・アルバイト向け。
        - daily (日給制):            base = daily_rate × actual_days
                                     日雇い・短期向け。
        - monthly_fixed_ot (月給＋固定残業): base = monthly部分 + fixed_overtime_amount
                                     裁量労働制／みなし残業。固定残業代を加算。
        - monthly_hour (月給＋時給併用): 基本給＋時給併用。基準時間超過分は残業時給で計算。
                                     派遣社員向け。

        Args:
            emp: Employee dict from pay_jp_salary_master
            salary_type: One of 'monthly', 'hourly', 'daily', 'monthly_fixed_ot', 'monthly_hour'
            actual_hours: Hours worked this month (from salary records)
            actual_days: Days worked this month (from salary records)
            working_days_in_month: Working days in the month from batch config (default 22)

        Returns:
            dict with base_pay, allowance_total, gross_pay, deductions, net_pay,
            employer_cost_total, and calculation messages.

        劳动法依据:
        - 労働基準法第24条（賃金支払いの原則）
        - 労働基準法第37条（時間外割増賃金）
        - 最低賃金法（最低賃金の保障）
        """
        messages = []

        if salary_type == "monthly":
            basic = float(emp.get("basic_salary") or 0)
            working_days = float(working_days_in_month or 22)
            absence_days = float(emp.get("absence_days") or 0)
            effective_days = max(working_days - absence_days, 0)
            base = round(basic * effective_days / max(working_days, 1), 0)
            messages.append(f"月給: {basic:,.0f}円 × ({working_days:.0f}日 - {absence_days:.0f}日欠勤) / {working_days:.0f}日 = {base:,.0f}円")

        elif salary_type == "hourly":
            actual_hours = actual_hours or float(emp.get("standard_monthly_hours") or 160)
            rate = float(emp.get("hourly_rate") or 0)
            base = round(rate * actual_hours, 0)
            messages.append(f"時給: {rate:,.0f}円 × {actual_hours}h = {base:,.0f}円")

        elif salary_type == "daily":
            actual_days = actual_days or 1
            rate = float(emp.get("daily_rate") or 0)
            base = round(rate * actual_days, 0)
            messages.append(f"日給: {rate:,.0f}円 × {actual_days}日 = {base:,.0f}円")

        elif salary_type == "monthly_fixed_ot":
            basic = float(emp.get("basic_salary") or 0)
            fixed_ot = float(emp.get("fixed_overtime_amount") or 0)
            working_days = float(working_days_in_month or 22)
            absence_days = float(emp.get("absence_days") or 0)
            effective_days = max(working_days - absence_days, 0)
            base = round(basic * effective_days / max(working_days, 1), 0)
            gross = base + fixed_ot
            messages.append(f"月給+固定残業: {basic:,.0f}円 × ({working_days:.0f}日 - {absence_days:.0f}日欠勤) / {working_days:.0f}日 = {base:,.0f}円")
            messages.append(f"固定残業代: {fixed_ot:,.0f}円")
            base = gross  # use gross as base for deduction calculation

        elif salary_type == "monthly_hour":
            std_hours = float(emp.get("standard_monthly_hours") or 160)
            actual_hours = actual_hours or std_hours
            basic = float(emp.get("basic_salary") or 0)
            hourly_rate = float(emp.get("hourly_rate") or 0)
            overtime_rate = float(emp.get("overtime_hourly_rate") or 0)

            if actual_hours <= std_hours:
                monthly_part = round(basic * actual_hours / max(std_hours, 1), 0)
                hourly_part = round(hourly_rate * actual_hours, 0)
                overtime_pay = 0.0
                messages.append(f"月時給: 基本給{basic:,.0f}円 × {actual_hours}h/{std_hours:.0f}h = {monthly_part:,.0f}円")
                messages.append(f"時給部分: {hourly_rate:,.0f}円 × {actual_hours}h = {hourly_part:,.0f}円")
            else:
                monthly_part = basic
                hourly_part = round(hourly_rate * std_hours, 0)
                ot_hours = actual_hours - std_hours
                overtime_pay = round(overtime_rate * ot_hours, 0)
                messages.append(f"月時給: 基本給{basic:,.0f}円 (全額支給)")
                messages.append(f"時給部分: {hourly_rate:,.0f}円 × {std_hours:.0f}h = {hourly_part:,.0f}円")
                messages.append(f"残業: {overtime_rate:,.0f}円 × {ot_hours}h = {overtime_pay:,.0f}円")

            base = monthly_part + hourly_part + overtime_pay
        else:
            base = float(emp.get("basic_salary") or 0)
            messages.append(f"Unknown salary_type: {salary_type}, using basic_salary")

        # Add allowances to get gross pay.
        # IMPORTANT: fixed_overtime_amount is already included in base for
        # monthly_fixed_ot (line ~1014), so exclude it from allowances to
        # avoid double-counting. For all other salary types it is a regular
        # allowance and should be added here.
        allowance_keys = [
            "commute_allowance", "housing_allowance", "family_allowance",
            "position_allowance", "fixed_allowance", "transport_allowance",
            "phone_allowance", "performance_bonus", "project_bonus",
        ]
        if salary_type != "monthly_fixed_ot":
            allowance_keys.append("fixed_overtime_amount")
        allowances = sum(float(emp.get(k) or 0) for k in allowance_keys)

        gross_pay = base + allowances

        # ── Statutory deductions (2026 rates, parameter-driven) ──
        si_eligible = emp.get("social_insurance_eligible") not in (False, "false", 0, "0")
        ei_eligible = emp.get("employment_insurance_eligible") not in (False, "false", 0, "0")
        # Age at fiscal year start (April 1) for 介護保険 determination.
        # Calculated from emp_employees.date_of_birth.
        # If DOB is unavailable, defaults to 0 (no 介護保険).
        age = _calc_fiscal_age(emp.get("employee_id", "")) or 0
        prefecture_code = emp.get("prefecture_code") or None

        # Look up rates from parameter table (prefecture-specific health insurance)
        health_emp_rate, health_empr_rate = self._lookup_insurance_rate("health_insurance", prefecture_code)
        pension_emp_rate, pension_empr_rate = self._lookup_insurance_rate("pension")
        care_emp_rate, care_empr_rate = self._lookup_insurance_rate("nursing_care")
        employ_emp_rate, employ_empr_rate = self._lookup_insurance_rate("employment",
            category=emp.get("employment_insurance_category"))

        # Insurance base: for monthly_hour, use standard monthly remuneration
        # (標準報酬月額) from the grade table. For all other types, use the
        # calculated base_pay directly (verified against business data).
        if salary_type == "monthly_hour":
            insurance_base_health = self._lookup_standard_remuneration(base, "health_insurance")
            insurance_base_pension = self._lookup_standard_remuneration(base, "pension_insurance")
        else:
            insurance_base_health = base
            insurance_base_pension = base
        health_ins = round(insurance_base_health * health_emp_rate, 0) if si_eligible else 0
        pension = round(insurance_base_pension * pension_emp_rate, 0) if si_eligible else 0
        care_ins = round(insurance_base_health * care_emp_rate, 0) if (si_eligible and 40 <= age <= 64) else 0
        employ_ins = round(base * employ_emp_rate, 0) if ei_eligible else 0
        si_total = health_ins + pension + care_ins + employ_ins

        # Income tax — progressive withholding tax bracket table.
        # Taxable base: gross_pay minus non-taxable commute allowance
        # (通勤手当非課税, 所得税法第9条) and social insurance.
        non_taxable_commute = float(emp.get("commute_allowance") or 0)
        taxable_income = max(gross_pay - non_taxable_commute - si_total, 0)
        dependents = int(emp.get("dependents_count") or 0)
        income_tax = self._lookup_withholding_tax(taxable_income, dependents)
        resident_tax = float(emp.get("monthly_resident_tax") or 0)
        recurring = float(emp.get("recurring_deductions") or 0)

        deduction_total = si_total + income_tax + resident_tax + recurring
        net_pay = gross_pay - deduction_total

        # ── Employer cost (法定福利費 / statutory employer burdens) ──
        employer_health = round(insurance_base_health * health_empr_rate, 0) if si_eligible else 0
        employer_pension = round(insurance_base_pension * pension_empr_rate, 0) if si_eligible else 0
        employer_care = round(insurance_base_health * care_empr_rate, 0) if (si_eligible and 40 <= age <= 64) else 0
        employer_employ = round(base * employ_empr_rate, 0) if ei_eligible else 0

        # Child-rearing support fund (子ども・子育て支援金) — employer only, 0.115%
        child_support_emp_rate, child_support_empr_rate = self._lookup_insurance_rate("child_support")
        employer_child_support = round(insurance_base_health * child_support_empr_rate, 0) if si_eligible else 0

        # Child allowance contribution (児童手当拠出金) — employer only, 0.36%
        child_emp_rate, child_empr_rate = self._lookup_insurance_rate("child_allowance")
        employer_child = round(insurance_base_health * child_empr_rate, 0) if si_eligible else 0

        # Worker's accident insurance (労災保険) — employer only.
        # Rate depends on the industry_code configured on the employee's entity.
        # Uses gross_pay (actual wages) as the base.
        accident_rate = 0.0
        industry_code = emp.get("industry_code") or None
        if industry_code and _PG_AVAILABLE:
            try:
                ai_rows = _db.load_table("pay_jp_accident_insurance_rates",
                    where="industry_code = %s AND is_current = true",
                    params=(industry_code,))
                if ai_rows:
                    accident_rate = float(ai_rows[0].get("rate") or 0)
            except Exception:
                pass
        employer_accident = round(base * accident_rate, 0)

        employer_cost = (employer_health + employer_pension + employer_care
                         + employer_employ + employer_child_support + employer_child + employer_accident)

        return {
            "salary_type": salary_type,
            "base_pay": int(round(base)),
            "allowance_total": int(round(allowances)),
            "gross_pay": int(round(gross_pay)),
            # Employee deductions
            "health_insurance_employee": int(round(health_ins)),
            "pension_employee": int(round(pension)),
            "care_insurance_employee": int(round(care_ins)),
            "employment_insurance_employee": int(round(employ_ins)),
            "income_tax": int(round(income_tax)),
            "monthly_resident_tax": int(round(resident_tax)),
            "recurring_deductions": int(round(recurring)),
            "deduction_total": int(round(deduction_total)),
            "net_pay": int(round(net_pay)),
            # Employer cost breakdown
            "employer_cost_total": int(round(employer_cost)),
            "employer_health": int(round(employer_health)),
            "employer_pension": int(round(employer_pension)),
            "employer_care": int(round(employer_care)),
            "employer_employ": int(round(employer_employ)),
            "employer_child_support": int(round(employer_child_support)),
            "employer_child_allowance": int(round(employer_child)),
            "employer_accident_insurance": int(round(employer_accident)),
            # Work time / days reference
            "standard_work_days": float(working_days_in_month or 22),
            "standard_work_hours": float(emp.get("standard_work_hours") or 176),
            "standard_monthly_hours": float(emp.get("standard_monthly_hours") or 160),
            "actual_days": actual_days or float(working_days_in_month or 22),
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
            param_type = body.pop("param_type", "")
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
            pk_val = body.pop(pk_col, None) or body.pop("id", None)
            body["updated_at"] = datetime.now(timezone.utc).isoformat()

            if pk_val:
                existing = _db.load_table(table, where={pk_col: int(pk_val)})
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
        """Create a new payroll batch with entity+month uniqueness enforcement.

        Business rules:
          - One entity + one month = at most one active (non-voided) batch.
          - draft/calculated batches → auto-voided (not yet finalized).
          - confirmed batches → BLOCKED. User must explicitly rollback first.
            This prevents silent replacement of finalized payroll that may have
            been reported to authorities or had payslips sent.
        """
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        if not self._check_permission(session, "tacaipay_jp.manage"):
            error(self, "Forbidden", 403)
            return
        try:
            entity_id = body.get("entity_id", "")
            payroll_month = body.get("payroll_month", "")
            user_name = session.get("email", "system")
            batch_id = body.get("batch_id") or f"JPB-{uuid.uuid4().hex[:12].upper()}"
            now_iso = datetime.now(timezone.utc).isoformat()

            # ── Check existing non-voided batches for same entity+month ──
            if entity_id and payroll_month:
                existing = _db.load_table("pay_jp_payroll_batches",
                    where="entity_id = %s AND payroll_month = %s AND status != 'voided'",
                    params=(entity_id, payroll_month)) or []

                # BLOCK if any confirmed batch exists (finalized payroll — must rollback explicitly)
                confirmed_batches = [b for b in existing if b.get("status") == "confirmed"]
                if confirmed_batches:
                    confirmed_ids = [b.get("batch_id", "") for b in confirmed_batches]
                    # Check if any payslips have been sent for these batches
                    for cb_id in confirmed_ids:
                        sent = _db.load_table("pay_jp_payslips",
                            where="batch_id = %s AND email_status = 'sent'", params=(cb_id,)) or []
                        if sent:
                            error(self,
                                f"Cannot create new batch: confirmed batch {cb_id} has {len(sent)} sent payslip(s). "
                                f"Rollback is blocked for batches with sent payslips. "
                                f"Use an off-cycle/adjustment batch or handle this manually.", 409)
                            return
                    error(self,
                        f"Cannot create new batch: {len(confirmed_batches)} confirmed batch(es) already exist "
                        f"for {entity_id} / {payroll_month}. "
                        f"Please rollback the confirmed batch first before creating a new one. "
                        f"Confirmed batch(es): {', '.join(confirmed_ids)}", 409)
                    return

                # Auto-void draft and calculated batches (not yet finalized — safe to replace)
                voided_count = 0
                for old in existing:
                    old_batch_id = old.get("batch_id", "")
                    old_status = old.get("status", "")
                    if old_status not in ("draft", "calculated"):
                        continue  # skip any unexpected status
                    _db.update_record("pay_jp_payroll_batches", "batch_id", old_batch_id, {
                        "status": "voided",
                        "rollback_reason": f"Auto-voided: replaced by new batch {batch_id} (previous status: {old_status})",
                        "updated_at": now_iso,
                    })
                    _write_audit_log(self, "VOID", "pay_jp_payroll_batches", old_batch_id,
                                     user_name,
                                     before_value={"status": old_status, "entity_id": entity_id, "payroll_month": payroll_month},
                                     after_value={"status": "voided", "reason": f"Auto-voided by new batch {batch_id}"})
                    voided_count += 1
            else:
                voided_count = 0

            batch = {
                "batch_id": batch_id,
                "country_code": "JP",
                "entity_id": entity_id,
                "payroll_month": payroll_month,
                "working_days_in_month": int(body.get("working_days_in_month", 22) or 22),
                "status": "draft",
                "version": 1,
                "employee_count": 0,
                "gross_total": 0,
                "deduction_total": 0,
                "net_total": 0,
                "employer_cost_total": 0,
                "created_at": now_iso,
                "updated_at": now_iso,
                "created_by": user_name,
                "notes": body.get("notes", ""),
            }
            _db.insert_record("pay_jp_payroll_batches", batch)

            result = {"batch_id": batch_id, "entity_id": entity_id, "payroll_month": payroll_month, "status": "draft"}
            if voided_count > 0:
                result["auto_voided"] = voided_count
            success(self, result)
        except Exception as e:
            error(self, f"Create batch failed: {str(e)}", 500)

    def _calculate_batch(self, session, batch_id):
        """Calculate (or recalculate) payroll for all employees in a batch.

        - Supports initial calculation (draft status) and recalculation (calculated status).
        - Recalculation OVERWRITES all records including manually_edited ones — this is
          intentional: "recalculate" means "recompute from source data". Users who want to
          preserve manual edits should use per-record editing instead of batch recalculation.
        - Writes calculation_detail JSON for each record.
        - Writes audit log entries for the batch-level action.
        - Increments recalculate_count on each run.
        """
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        if not self._check_permission(session, "tacaipay_jp.calculate"):
            error(self, "Forbidden", 403)
            return
        try:
            user_name = session.get("email", "system")
            batch = _db.load_table("pay_jp_payroll_batches", where={"batch_id": batch_id})
            if not batch:
                error(self, "Batch not found", 404)
                return

            batch_status = batch[0].get("status", "draft")
            if batch_status not in ("draft", "calculated"):
                error(self, f"Cannot calculate batch in '{batch_status}' status", 400)
                return

            entity_id = batch[0].get("entity_id", "")
            is_recalc = (batch_status == "calculated")

            # Load JP employees (active only, filtered by entity)
            employees = _db.load_table("pay_jp_salary_master", where="entity_id = %s AND active = true", params=(entity_id,)) if entity_id else []

            # Load existing monthly records (if any) to preserve per-employee inputs
            existing_records = _db.load_table("pay_jp_monthly_salary_records", where={"batch_id": batch_id}) or []
            existing_by_emp = {r.get("employee_id", ""): r for r in existing_records}

            working_days = float(batch[0].get("working_days_in_month", 22) or 22)
            now_iso = datetime.now(timezone.utc).isoformat()

            # Use salary-type-aware calculation for each employee
            records = []
            for emp in employees:
                eid = emp.get("employee_id", "")
                salary_type = emp.get("salary_type") or "monthly"

                # Merge existing record inputs (absence_days, actual_hours, etc.) if present
                existing = existing_by_emp.get(eid, {})

                calc_emp = {**emp}
                for k in ["absence_days", "actual_work_days", "actual_work_hours",
                           "overtime_hours", "paid_leave_days", "sick_leave_days",
                           "commute_allowance", "housing_allowance", "family_allowance",
                           "position_allowance", "fixed_allowance", "transport_allowance",
                           "phone_allowance", "performance_bonus", "project_bonus",
                           "other_allowance", "other_deduction"]:
                    if k in existing and existing[k] is not None:
                        calc_emp[k] = existing[k]

                actual_hours = float(calc_emp.get("actual_work_hours") or 0)
                actual_days = float(calc_emp.get("actual_work_days") or 0)
                absence_days = float(calc_emp.get("absence_days") or 0)

                result = self._calc_salary_by_type(calc_emp, salary_type, actual_hours, actual_days, working_days)

                base_pay = result["base_pay"]
                gross = result["gross_pay"]

                # Build calculation_detail JSON for audit/debug purposes
                calc_detail = json.dumps({
                    "salary_type": salary_type,
                    "formula_inputs": {
                        "basic_salary": calc_emp.get("basic_salary"),
                        "hourly_rate": calc_emp.get("hourly_rate"),
                        "daily_rate": calc_emp.get("daily_rate"),
                        "working_days": working_days,
                        "actual_work_hours": actual_hours,
                        "actual_work_days": actual_days,
                        "absence_days": absence_days,
                        "fixed_overtime_amount": calc_emp.get("fixed_overtime_amount"),
                        "overtime_hourly_rate": calc_emp.get("overtime_hourly_rate"),
                        "standard_monthly_hours": calc_emp.get("standard_monthly_hours"),
                    },
                    "allowances": {
                        "commute": float(calc_emp.get("commute_allowance") or 0),
                        "housing": float(calc_emp.get("housing_allowance") or 0),
                        "family": float(calc_emp.get("family_allowance") or 0),
                        "position": float(calc_emp.get("position_allowance") or 0),
                        "fixed": float(calc_emp.get("fixed_allowance") or 0),
                        "transport": float(calc_emp.get("transport_allowance") or 0),
                        "phone": float(calc_emp.get("phone_allowance") or 0),
                        "performance_bonus": float(calc_emp.get("performance_bonus") or 0),
                        "project_bonus": float(calc_emp.get("project_bonus") or 0),
                    },
                    
                    "employer_cost": {
                        "health": result.get("employer_health", 0),
                        "pension": result.get("employer_pension", 0),
                        "care": result.get("employer_care", 0),
                        "employment": result.get("employer_employ", 0),
                        "child_allowance": result.get("employer_child_allowance", 0),
                        "accident_insurance": result.get("employer_accident_insurance", 0),
                    },
                    "breakdown": {k: v for k, v in result.items() if k != "messages"},
                    "messages": result.get("messages", []),
                }, ensure_ascii=False, default=str)

                record_id = existing.get("record_id") or f"JPR-{uuid.uuid4().hex[:12].upper()}"
                records.append({
                    "record_id": record_id,
                    "batch_id": batch_id,
                    "sheet_id": batch_id,  # backward compat: same as batch_id
                    "payroll_month": batch[0].get("payroll_month", ""),
                    "country_code": "JP",
                    "entity_id": entity_id,
                    "employee_id": eid,
                    "employee_number": emp.get("employee_number", ""),
                    "employee_name": emp.get("employee_name", ""),
                    "email": emp.get("email", ""),
                    "salary_type": salary_type,
                    "basic_salary": emp.get("basic_salary", 0),
                    "absence_days": absence_days,
                    "actual_work_days": actual_days,
                    "actual_work_hours": actual_hours,
                    "base_pay_calculated": base_pay,
                    # Allowance amounts carried forward from employee master / existing record
                    "commute_allowance": float(calc_emp.get("commute_allowance") or 0),
                    "housing_allowance": float(calc_emp.get("housing_allowance") or 0),
                    "family_allowance": float(calc_emp.get("family_allowance") or 0),
                    "position_allowance": float(calc_emp.get("position_allowance") or 0),
                    "fixed_allowance": float(calc_emp.get("fixed_allowance") or 0),
                    "transport_allowance": float(calc_emp.get("transport_allowance") or 0),
                    "phone_allowance": float(calc_emp.get("phone_allowance") or 0),
                    "performance_bonus": float(calc_emp.get("performance_bonus") or 0),
                    "project_bonus": float(calc_emp.get("project_bonus") or 0),
                    # Gross / net
                    "gross_pay": gross,
                    # Standard remuneration (grade-table amounts used for insurance)
                    # Employee deductions
                    "health_insurance_employee": result["health_insurance_employee"],
                    "pension_employee": result["pension_employee"],
                    "employment_insurance_employee": result["employment_insurance_employee"],
                    "care_insurance_employee": result["care_insurance_employee"],
                    "income_tax": result["income_tax"],
                    "residence_tax": result["monthly_resident_tax"],
                    "deduction_total": result["deduction_total"],
                    "net_pay": result["net_pay"],
                    # Employer cost
                    "employer_cost_total": result["employer_cost_total"],
                    "employer_child_support": result.get("employer_child_support", 0),
                    # Status & audit
                    "status": "calculated",
                    "calculation_detail": calc_detail,
                    "last_calculated_at": now_iso,
                    "manually_edited": False,
                    "created_at": existing.get("created_at") or now_iso,
                    "updated_at": now_iso,
                })

            # Persist all records
            for rec in records:
                existing_id = existing_by_emp.get(rec.get("employee_id", ""), {}).get("record_id")
                if existing_id:
                    _db.update_record("pay_jp_monthly_salary_records", "record_id", existing_id, rec)
                else:
                    _db.insert_record("pay_jp_monthly_salary_records", rec)

            employee_count = len(records)
            gross_total = sum(float(r.get("gross_pay") or 0) for r in records)
            deduction_total = sum(float(r.get("deduction_total") or 0) for r in records)
            net_total = sum(float(r.get("net_pay") or 0) for r in records)
            employer_cost_total = sum(float(r.get("employer_cost_total") or 0) for r in records)

            # Update batch — increment recalculate_count on recalc
            current_recalc_count = int(batch[0].get("recalculate_count") or 0)
            update_batch = {
                "employee_count": employee_count,
                "gross_total": gross_total,
                "deduction_total": deduction_total,
                "net_total": net_total,
                "employer_cost_total": employer_cost_total,
                "status": "calculated",
                "recalculate_count": current_recalc_count + (1 if is_recalc else 0),
                "updated_at": now_iso,
            }
            _db.update_record("pay_jp_payroll_batches", "batch_id", batch_id, update_batch)

            # ── Audit log ──
            action = "RECALCULATE" if is_recalc else "CALCULATE"
            _write_audit_log(self, action, "pay_jp_payroll_batches", batch_id,
                             user_name,
                             before_value={"status": batch_status, "recalculate_count": current_recalc_count},
                             after_value={"status": "calculated", "employee_count": employee_count,
                                          "gross_total": gross_total, "net_total": net_total,
                                          "recalculate_count": current_recalc_count + (1 if is_recalc else 0)})

            msg = {"batch_id": batch_id, "employee_count": employee_count, "gross_total": gross_total, "net_total": net_total}
            if employee_count == 0:
                msg["warning"] = f"No active employees found for entity '{entity_id}'. Check that employees exist in salary master with this entity and active=true."
            success(self, msg)
        except Exception as e:
            error(self, f"Calculate failed: {str(e)}", 500)

    def _confirm_sheet(self, session, sheet_id):
        """Confirm (定稿) a batch. Writes audit log and generates payslip records."""
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        if not self._check_permission(session, "tacaipay_jp.approve"):
            error(self, "Forbidden", 403)
            return
        try:
            user_name = session.get("email", "system")
            now_iso = datetime.now(timezone.utc).isoformat()

            # Update batch status
            batch_list = _db.load_table("pay_jp_payroll_batches", where={"batch_id": sheet_id})
            if not batch_list:
                error(self, "Batch not found", 404)
                return
            batch_data = batch_list[0]

            _db.update_record("pay_jp_payroll_batches", "batch_id", sheet_id, {
                "status": "confirmed",
                "confirmed_at": now_iso,
                "confirmed_by": user_name,
                "updated_at": now_iso,
            })

            # ── Generate payslip records for all monthly salary records in this batch ──
            records = _db.load_table("pay_jp_monthly_salary_records", where={"batch_id": sheet_id}) or []
            batch_data = batch_list[0] if batch_list else {}

            # Resolve entity label via masterdata internal API
            entity_id = batch_data.get("entity_id", "")
            entity_label_text = entity_id  # fallback
            try:
                req = Request(
                    f"http://127.0.0.1:8007/api/internal/entity/{entity_id}/active",
                    headers={"Accept": "application/json"},
                    method="GET",
                )
                with urlopen(req, timeout=3) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                ent = body.get("entity") or {}
                if ent:
                    entity_label_text = f"{ent.get('entity_code', '')} - {ent.get('entity_name', '')} ({ent.get('country', '')})"
            except Exception:
                pass

            payslip_count = 0
            for rec in records:
                emp_id = rec.get("employee_id", "")
                # Check if payslip already exists
                existing_ps = _db.load_table("pay_jp_payslips",
                    where="batch_id = %s AND employee_id = %s",
                    params=(sheet_id, emp_id)) or []
                if existing_ps:
                    continue  # skip if already generated

                html = _generate_payslip_html(rec, batch_data, entity_label_text)
                payslip = {
                    "record_id": f"PS-JP-{uuid.uuid4().hex[:12].upper()}",
                    "batch_id": sheet_id,
                    "sheet_id": sheet_id,
                    "employee_id": emp_id,
                    "employee_number": rec.get("employee_number", ""),
                    "employee_name": rec.get("employee_name", ""),
                    "email_to": rec.get("email", ""),
                    "payroll_month": rec.get("payroll_month", ""),
                    "gross_pay": rec.get("gross_pay", 0),
                    "net_pay": rec.get("net_pay", 0),
                    "email_status": "not_sent",
                    "html_content": html,
                    "created_at": now_iso,
                    "updated_at": now_iso,
                }
                _db.insert_record("pay_jp_payslips", payslip)
                payslip_count += 1

            # ── Audit log ──
            _write_audit_log(self, "CONFIRM", "pay_jp_payroll_batches", sheet_id,
                             user_name, before_value={"status": "calculated"},
                             after_value={"status": "confirmed", "payslips_generated": payslip_count})

            success(self, {"sheet_id": sheet_id, "status": "confirmed", "payslips_generated": payslip_count})
        except Exception as e:
            error(self, f"Confirm failed: {str(e)}", 500)

    # ── New: Rollback ──
    def _rollback_batch(self, session, batch_id, body):
        """Rollback a confirmed batch back to calculated status."""
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        if not self._check_permission(session, "tacaipay_jp.approve"):
            error(self, "Forbidden", 403)
            return
        try:
            user_name = session.get("email", "system")
            reason = (body or {}).get("reason", "").strip()
            if not reason:
                error(self, "Rollback reason is required", 400)
                return

            # Load batch
            batch_list = _db.load_table("pay_jp_payroll_batches", where={"batch_id": batch_id})
            if not batch_list:
                error(self, "Batch not found", 404)
                return
            batch = batch_list[0]
            if batch.get("status") != "confirmed":
                error(self, "Only confirmed batches can be rolled back", 400)
                return

            # Check if any payslip has been sent
            sent_payslips = _db.load_table("pay_jp_payslips",
                where="batch_id = %s AND email_status = 'sent'",
                params=(batch_id,)) or []
            if sent_payslips:
                error(self,
                    f"Rollback blocked: {len(sent_payslips)} payslip(s) have already been sent. "
                    "Create a new batch with adjustments instead.", 409)
                return

            now_iso = datetime.now(timezone.utc).isoformat()
            # Update batch
            _db.update_record("pay_jp_payroll_batches", "batch_id", batch_id, {
                "status": "calculated",
                "rolled_back_at": now_iso,
                "rolled_back_by": user_name,
                "rollback_reason": reason,
                "confirmed_at": None,
                "confirmed_by": None,
                "updated_at": now_iso,
            })

            # ── Audit log ──
            _write_audit_log(self, "ROLLBACK", "pay_jp_payroll_batches", batch_id,
                             user_name,
                             before_value={"status": "confirmed"},
                             after_value={"status": "calculated", "reason": reason})

            success(self, {"batch_id": batch_id, "status": "calculated", "rollback_reason": reason})
        except Exception as e:
            error(self, f"Rollback failed: {str(e)}", 500)

    # ── New: Void batch ──
    def _void_batch(self, session, batch_id, body):
        """Void a draft batch (set status to voided)."""
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        if not self._check_permission(session, "tacaipay_jp.manage"):
            error(self, "Forbidden", 403)
            return
        try:
            user_name = session.get("email", "system")
            reason = (body or {}).get("reason", "").strip()

            batch_list = _db.load_table("pay_jp_payroll_batches", where={"batch_id": batch_id})
            if not batch_list:
                error(self, "Batch not found", 404)
                return
            if batch_list[0].get("status") != "draft":
                error(self, "Only draft batches can be voided", 400)
                return

            now_iso = datetime.now(timezone.utc).isoformat()
            _db.update_record("pay_jp_payroll_batches", "batch_id", batch_id, {
                "status": "voided",
                "rollback_reason": reason,
                "updated_at": now_iso,
            })

            _write_audit_log(self, "VOID", "pay_jp_payroll_batches", batch_id,
                             user_name, before_value={"status": "draft"},
                             after_value={"status": "voided", "reason": reason})

            success(self, {"batch_id": batch_id, "status": "voided"})
        except Exception as e:
            error(self, f"Void failed: {str(e)}", 500)

    # ── New: Delete batch ──
    def _delete_batch(self, session, batch_id):
        """Permanently delete a voided batch and its monthly salary records.

        Only batches with status 'voided' can be deleted (hard delete).
        Draft batches should use void first, then delete.
        Calculated/confirmed batches cannot be deleted — rollback first.
        Writes audit log for the delete action against the batch.
        """
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        if not self._check_permission(session, "tacaipay_jp.manage"):
            error(self, "Forbidden", 403)
            return
        try:
            user_name = session.get("email", "system")

            batch_list = _db.load_table("pay_jp_payroll_batches", where={"batch_id": batch_id})
            if not batch_list:
                error(self, "Batch not found", 404)
                return

            batch_status = batch_list[0].get("status", "")
            if batch_status != "voided":
                error(self, f"Only voided batches can be deleted (current status: {batch_status}). Use 'void' first.", 400)
                return

            # Capture before snapshot for audit
            before_snapshot = {k: v for k, v in batch_list[0].items()
                               if k in ("batch_id", "entity_id", "payroll_month", "status",
                                         "employee_count", "gross_total", "net_total", "created_by")}

            # Delete associated monthly salary records first
            records = _db.load_table("pay_jp_monthly_salary_records", where={"batch_id": batch_id}) or []
            deleted_record_count = 0
            for rec in records:
                try:
                    _db.delete_record("pay_jp_monthly_salary_records", "record_id", rec.get("record_id", ""))
                    deleted_record_count += 1
                except Exception:
                    pass

            # Delete batch
            _db.delete_record("pay_jp_payroll_batches", "batch_id", batch_id)

            # ── Audit log for batch deletion ──
            _write_audit_log(self, "DELETE", "pay_jp_payroll_batches", batch_id,
                             user_name,
                             before_value=before_snapshot,
                             after_value={"deleted": True, "records_deleted": deleted_record_count})

            success(self, {"batch_id": batch_id, "deleted": True, "records_deleted": deleted_record_count})
        except Exception as e:
            error(self, f"Delete batch failed: {str(e)}", 500)

    # ── New: Single Record Recalculate ──
    def _recalculate_single_record(self, session, record_id):
        """Recalculate a single monthly salary record."""
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        if not self._check_permission(session, "tacaipay_jp.calculate"):
            error(self, "Forbidden", 403)
            return
        try:
            user_name = session.get("email", "system")

            # Load the existing record
            record_list = _db.load_table("pay_jp_monthly_salary_records", where={"record_id": record_id})
            if not record_list:
                error(self, "Record not found", 404)
                return
            record = record_list[0]

            # Load employee master data
            emp_id = record.get("employee_id", "")
            emp_list = _db.load_table("pay_jp_salary_master", where={"employee_id": emp_id})
            if not emp_list:
                error(self, "Employee not found in salary master", 404)
                return
            emp = emp_list[0]

            # Load batch for working days
            batch_id = record.get("batch_id", "")
            batch_list = _db.load_table("pay_jp_payroll_batches", where={"batch_id": batch_id})
            working_days = float((batch_list[0] if batch_list else {}).get("working_days_in_month", 22) or 22)

            # Preserve per-record inputs (absence_days, actual hours, etc.)
            calc_emp = {**emp}
            for k in ["absence_days", "actual_work_days", "actual_work_hours",
                       "overtime_hours", "paid_leave_days", "sick_leave_days",
                       "commute_allowance", "housing_allowance", "family_allowance",
                       "position_allowance", "fixed_allowance", "transport_allowance",
                       "phone_allowance", "performance_bonus", "project_bonus",
                       "other_allowance", "other_deduction"]:
                if k in record and record[k] is not None:
                    calc_emp[k] = record[k]

            salary_type = calc_emp.get("salary_type") or "monthly"
            actual_hours = float(calc_emp.get("actual_work_hours") or 0)
            actual_days = float(calc_emp.get("actual_work_days") or 0)
            absence_days = float(calc_emp.get("absence_days") or 0)

            result = self._calc_salary_by_type(calc_emp, salary_type, actual_hours, actual_days, working_days)

            now_iso = datetime.now(timezone.utc).isoformat()
            before_snapshot = {
                "base_pay_calculated": record.get("base_pay_calculated"),
                "gross_pay": record.get("gross_pay"),
                "net_pay": record.get("net_pay"),
                "deduction_total": record.get("deduction_total"),
            }

            updated = {
                **record,
                "base_pay_calculated": result["base_pay"],
                "gross_pay": result["gross_pay"],
                # Standard remuneration (grade-table amounts used for insurance)
                # Employee deductions
                "health_insurance_employee": result["health_insurance_employee"],
                "pension_employee": result["pension_employee"],
                "employment_insurance_employee": result["employment_insurance_employee"],
                "care_insurance_employee": result["care_insurance_employee"],
                "income_tax": result["income_tax"],
                "residence_tax": result["monthly_resident_tax"],
                "deduction_total": result["deduction_total"],
                "net_pay": result["net_pay"],
                # Employer cost breakdown
                "employer_cost_total": result["employer_cost_total"],
                "employer_cost_total": result.get("employer_cost_total", 0),
                # Status & audit
                "manually_edited": False,
                "calculation_detail": json.dumps({
                    "salary_type": salary_type,
                    "formula_inputs": {
                        "basic_salary": calc_emp.get("basic_salary"),
                        "hourly_rate": calc_emp.get("hourly_rate"),
                        "daily_rate": calc_emp.get("daily_rate"),
                        "working_days": working_days,
                        "actual_work_hours": actual_hours,
                        "actual_work_days": actual_days,
                        "absence_days": absence_days,
                    },
                    "breakdown": {k: v for k, v in result.items() if k != "messages"},
                    "messages": result.get("messages", []),
                }, ensure_ascii=False, default=str),
                "last_calculated_at": now_iso,
                "updated_at": now_iso,
            }
            _db.update_record("pay_jp_monthly_salary_records", "record_id", record_id, updated)

            # ── Audit log ──
            _write_audit_log(self, "RECALCULATE_SINGLE", "pay_jp_monthly_salary_records", record_id,
                             user_name, before_value=before_snapshot,
                             after_value={"gross_pay": result["gross_pay"], "net_pay": result["net_pay"]})

            success(self, {"record_id": record_id, "net_pay": result["net_pay"]})
        except Exception as e:
            error(self, f"Recalculate single failed: {str(e)}", 500)

    # ── New: Edit Single Record ──
    def _edit_record(self, session, record_id, body):
        """Edit a single monthly salary record (draft or calculated status).

        Saves the edited fields, marks manually_edited=true, and writes audit log.
        Does NOT recalculate — only saves the edited values.
        """
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        if not self._check_permission(session, "tacaipay_jp.manage"):
            error(self, "Forbidden", 403)
            return
        try:
            user_name = session.get("email", "system")

            record_list = _db.load_table("pay_jp_monthly_salary_records", where={"record_id": record_id})
            if not record_list:
                error(self, "Record not found", 404)
                return
            record = record_list[0]

            # Check batch status — allow edit in draft and calculated
            batch_id = record.get("batch_id", "")
            batch_list = _db.load_table("pay_jp_payroll_batches", where={"batch_id": batch_id})
            if batch_list and batch_list[0].get("status") == "confirmed":
                error(self, "Cannot edit records in a confirmed batch", 400)
                return

            # Save before snapshot for audit — all fields editable for manual correction
            editable_keys = [
                # Attendance inputs
                "absence_days", "actual_work_days", "actual_work_hours",
                "overtime_hours", "paid_leave_days", "sick_leave_days",
                # Allowances
                "commute_allowance", "housing_allowance", "family_allowance",
                "position_allowance", "fixed_allowance", "transport_allowance",
                "phone_allowance", "performance_bonus", "project_bonus",
                "other_allowance",
                # Deductions (manual override)
                "other_deduction", "recurring_deductions",
                # Calculated fields (manual correction)
                "base_pay_calculated", "gross_pay",
                "health_insurance_employee", "pension_employee",
                "care_insurance_employee", "employment_insurance_employee",
                "income_tax", "residence_tax",
                "deduction_total", "net_pay", "employer_cost_total",
                "employer_cost_total",
            ]
            before_snapshot = {k: record.get(k) for k in editable_keys}

            now_iso = datetime.now(timezone.utc).isoformat()
            update_data = {"manually_edited": True, "edited_at": now_iso, "edited_by": user_name, "updated_at": now_iso}

            for k in editable_keys:
                if k in (body or {}):
                    update_data[k] = body[k]

            _db.update_record("pay_jp_monthly_salary_records", "record_id", record_id, update_data)

            # ── Audit log ──
            _write_audit_log(self, "EDIT_RECORD", "pay_jp_monthly_salary_records", record_id,
                             user_name, before_value=before_snapshot,
                             after_value={k: body.get(k) for k in editable_keys if k in body})

            success(self, {"record_id": record_id, "edited": True})
        except Exception as e:
            error(self, f"Edit record failed: {str(e)}", 500)

    # ── New: Get Batch Audit Logs ──
    def _get_batch_audit_logs(self, batch_id):
        """Return all audit logs related to a specific batch and its records."""
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        try:
            # Get all records for this batch
            records = _db.load_table("pay_jp_monthly_salary_records", where={"batch_id": batch_id}) or []
            record_ids = [r.get("record_id", "") for r in records]
            record_ids.append(batch_id)  # also include the batch itself

            # Build IN clause
            ids_str = ", ".join(f"'{rid}'" for rid in record_ids if rid)
            if not ids_str:
                paginated(self, [], 1, 0, 0)
                return

            logs = _db.load_table("pay_jp_audit_logs",
                where=f"record_id IN ({ids_str})",
                order_by="created_at DESC") or []
            paginated(self, logs, 1, len(logs), len(logs))
        except Exception as e:
            error(self, f"Get audit logs failed: {str(e)}", 500)

    # ── New: Get Payslip HTML ──
    def _get_payslip_html(self, payslip_id):
        """Return the stored HTML content for a payslip (preview)."""
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        try:
            ps_list = _db.load_table("pay_jp_payslips", where={"record_id": payslip_id})
            if not ps_list:
                error(self, "Payslip not found", 404)
                return
            ps = ps_list[0]
            html = ps.get("html_content", "")
            if not html:
                error(self, "No HTML content available for this payslip", 404)
                return
            success(self, {"record_id": payslip_id, "html": html})
        except Exception as e:
            error(self, f"Get payslip HTML failed: {str(e)}", 500)

    # ── New: Send single payslip email ──
    def _send_single_payslip(self, session, payslip_id):
        """Send a single payslip by email."""
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        if not self._check_permission(session, "tacaipay_jp.approve"):
            error(self, "Forbidden", 403)
            return
        try:
            user_name = session.get("email", "system")
            ps_list = _db.load_table("pay_jp_payslips", where={"record_id": payslip_id})
            if not ps_list:
                error(self, "Payslip not found", 404)
                return
            ps = ps_list[0]

            to_email = ps.get("email_to", "")
            if not to_email:
                error(self, "Employee email not set", 400)
                return

            html = ps.get("html_content", "") or _generate_payslip_html(ps, {}, ps.get("entity_id", ""))
            subject = f"給与明細 / Payslip — {ps.get('payroll_month', '')} — {ps.get('employee_name', '')}"

            success_flag, error_msg = _send_email(to_email, subject, html)
            now_iso = datetime.now(timezone.utc).isoformat()

            if success_flag:
                _db.update_record("pay_jp_payslips", "record_id", payslip_id, {
                    "email_status": "sent",
                    "sent_at": now_iso,
                    "sent_by": user_name,
                    "email_error": None,
                    "updated_at": now_iso,
                })
                _write_audit_log(self, "EMAIL_SENT", "pay_jp_payslips", payslip_id,
                                 user_name, after_value={"email_to": to_email, "email_status": "sent"})
                success(self, {"payslip_id": payslip_id, "email_status": "sent"})
            else:
                _db.update_record("pay_jp_payslips", "record_id", payslip_id, {
                    "email_status": "failed",
                    "email_error": error_msg,
                    "updated_at": now_iso,
                })
                error(self, f"Email send failed: {error_msg}", 500)
        except Exception as e:
            error(self, f"Send payslip failed: {str(e)}", 500)

    # ── New: Send all payslips for a batch ──
    def _send_all_payslips(self, session, batch_id):
        """Send all unsent payslips for a batch."""
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        if not self._check_permission(session, "tacaipay_jp.approve"):
            error(self, "Forbidden", 403)
            return
        try:
            user_name = session.get("email", "system")
            all_ps = _db.load_table("pay_jp_payslips",
                where="batch_id = %s AND (email_status = 'not_sent' OR email_status IS NULL)",
                params=(batch_id,)) or []
            if not all_ps:
                success(self, {"batch_id": batch_id, "sent": 0, "failed": 0, "message": "No unsent payslips"})
                return

            sent_count = 0
            failed_count = 0
            results = []
            now_iso = datetime.now(timezone.utc).isoformat()

            for ps in all_ps:
                ps_id = ps.get("record_id", "")
                to_email = ps.get("email_to", "")
                if not to_email:
                    failed_count += 1
                    results.append({"record_id": ps_id, "employee_name": ps.get("employee_name", ""), "status": "failed", "error": "No email address"})
                    continue

                html = ps.get("html_content", "")
                subject = f"給与明細 / Payslip — {ps.get('payroll_month', '')} — {ps.get('employee_name', '')}"
                success_flag, error_msg = _send_email(to_email, subject, html)

                if success_flag:
                    _db.update_record("pay_jp_payslips", "record_id", ps_id, {
                        "email_status": "sent", "sent_at": now_iso, "sent_by": user_name, "email_error": None, "updated_at": now_iso,
                    })
                    sent_count += 1
                    results.append({"record_id": ps_id, "employee_name": ps.get("employee_name", ""), "status": "sent"})
                else:
                    _db.update_record("pay_jp_payslips", "record_id", ps_id, {
                        "email_status": "failed", "email_error": error_msg, "updated_at": now_iso,
                    })
                    failed_count += 1
                    results.append({"record_id": ps_id, "employee_name": ps.get("employee_name", ""), "status": "failed", "error": error_msg})

            _write_audit_log(self, "EMAIL_BATCH_SENT", "pay_jp_payslips", batch_id,
                             user_name, after_value={"sent": sent_count, "failed": failed_count})

            success(self, {"batch_id": batch_id, "sent": sent_count, "failed": failed_count, "total": len(all_ps), "results": results})
        except Exception as e:
            error(self, f"Send all payslips failed: {str(e)}", 500)

    # ── New: Send selected payslips ──
    def _send_selected_payslips(self, session, batch_id, body):
        """Send selected payslips by record_id list."""
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        if not self._check_permission(session, "tacaipay_jp.approve"):
            error(self, "Forbidden", 403)
            return
        try:
            record_ids = (body or {}).get("record_ids", [])
            if not record_ids:
                error(self, "No payslip IDs provided", 400)
                return

            user_name = session.get("email", "system")
            sent_count = 0
            failed_count = 0
            results = []
            now_iso = datetime.now(timezone.utc).isoformat()

            for ps_id in record_ids:
                ps_list = _db.load_table("pay_jp_payslips", where={"record_id": ps_id})
                if not ps_list:
                    results.append({"record_id": ps_id, "status": "failed", "error": "Not found"})
                    failed_count += 1
                    continue
                ps = ps_list[0]
                to_email = ps.get("email_to", "")
                if not to_email:
                    failed_count += 1
                    results.append({"record_id": ps_id, "employee_name": ps.get("employee_name", ""), "status": "failed", "error": "No email address"})
                    continue

                html = ps.get("html_content", "")
                subject = f"給与明細 / Payslip — {ps.get('payroll_month', '')} — {ps.get('employee_name', '')}"
                success_flag, error_msg = _send_email(to_email, subject, html)

                if success_flag:
                    _db.update_record("pay_jp_payslips", "record_id", ps_id, {
                        "email_status": "sent", "sent_at": now_iso, "sent_by": user_name, "email_error": None, "updated_at": now_iso,
                    })
                    sent_count += 1
                    results.append({"record_id": ps_id, "employee_name": ps.get("employee_name", ""), "status": "sent"})
                else:
                    _db.update_record("pay_jp_payslips", "record_id", ps_id, {
                        "email_status": "failed", "email_error": error_msg, "updated_at": now_iso,
                    })
                    failed_count += 1
                    results.append({"record_id": ps_id, "employee_name": ps.get("employee_name", ""), "status": "failed", "error": error_msg})

            _write_audit_log(self, "EMAIL_SELECTED_SENT", "pay_jp_payslips", batch_id,
                             user_name, after_value={"sent": sent_count, "failed": failed_count})

            success(self, {"batch_id": batch_id, "sent": sent_count, "failed": failed_count, "results": results})
        except Exception as e:
            error(self, f"Send selected payslips failed: {str(e)}", 500)

    def _email_payslip(self, session, payslip_id):
        """Legacy email endoint — delegates to _send_single_payslip."""
        self._send_single_payslip(session, payslip_id)

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
