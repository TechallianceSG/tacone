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

from auth_utils import validate_session, has_permission, is_system_admin
from cors_middleware import add_cors_headers, handle_preflight
from api_utils import send_json, success, error, paginated
from config import internal_url, INTERNAL_HOST


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

# ── Display constants (labels are bilingual JP/EN; i18n keys are preferred for frontend) ──
DEFAULT_PAYSLIP_SUBJECT = "給与明細 / Payslip — {payroll_month} — {employee_name}"

SALARY_TYPE_LABELS = {
    "monthly": "月給 / Monthly",
    "hourly": "時給 / Hourly",
    "daily": "日給 / Daily",
    "monthly_fixed_ot": "月給＋固定残業 / Monthly + Fixed OT",
    "monthly_hour": "月給時給ハイブリッド / Monthly-Hour Hybrid",
}

# Record field → item definition code mapping (future: add record_field column to item_definitions)
FIELD_TO_CODE = {
    "base_pay_calculated":        "base_pay",
    "hourly_pay_calculated":      "hourly_pay",
    "daily_pay_calculated":       "daily_pay",
    "overtime_pay_calc":          "overtime",
    "commute_allowance":          "transportation",
    "housing_allowance":          "housing_allowance",
    "family_allowance":           "family_allowance",
    "position_allowance":         "position_allowance",
    "fixed_allowance":            "fixed_allowance",
    "transport_allowance":        "transport_allowance",
    "phone_allowance":            "phone_allowance",
    "performance_bonus":          "bonus",
    "project_bonus":              "bonus",
    "health_insurance_employee":  "health_insurance",
    "pension_employee":           "pension",
    "care_insurance_employee":    "care_insurance",
    "employment_insurance_employee": "employment_insurance",
    "income_tax":                 "income_tax",
    "monthly_resident_tax":       "resident_tax",
    "residence_tax":              "resident_tax",
    "recurring_deductions":       "recurring_deductions",
    "absence_days":               "absence",
    "employer_health":            "health_insurance",
    "employer_pension":           "pension",
    "employer_care":              "care_insurance",
    "employer_employ":            "employment_insurance",
    "employer_child_allowance":   "employer_child_allowance",
    "employer_child_support":     "employer_child_support",
    "employer_accident_insurance":"employer_accident_insurance",
}

# Payslip item display definitions: (record_field, fallback_label_jp_en)
PAYSLIP_EARNING_KEYS = [
    ("base_pay_calculated", "基本給 / Base Pay"),
    ("overtime_pay_calc", "時間外手当 / Overtime"),
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

PAYSLIP_DEDUCTION_KEYS = [
    ("health_insurance_employee", "健康保険 / Health Insurance"),
    ("pension_employee", "厚生年金 / Pension"),
    ("care_insurance_employee", "介護保険 / Nursing Care"),
    ("employment_insurance_employee", "雇用保険 / Employment Insurance"),
    ("income_tax", "所得税 / Income Tax"),
    ("monthly_resident_tax", "住民税 / Resident Tax"),
    ("recurring_deductions", "その他控除 / Other Deductions"),
    ("absence_days", "欠勤控除 / Absence Deduction"),
]

PAYSLIP_EMPLOYER_KEYS = [
    ("employer_health", "健康保険 / Health Insurance (Employer)"),
    ("employer_pension", "厚生年金 / Pension (Employer)"),
    ("employer_care", "介護保険 / Nursing Care (Employer)"),
    ("employer_employ", "雇用保険 / Employment Insurance (Employer)"),
    ("employer_child_allowance", "児童手当拠出金 / Child Allowance Contribution"),
    ("employer_child_support", "子育て拠出金 / Child Support"),
    ("employer_accident_insurance", "労災保険 / Accident Insurance"),
]


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


def _send_email(to_email: str, subject: str, html_body: str, attachments: list | None = None,
                 cc_emails: list | None = None, from_override: tuple | None = None,
                 smtp_override: dict | None = None) -> tuple[bool, str]:
    """Send email via SMTP. Returns (success, error_message).

    Uses smtplib + email.mime from Python standard library.
    If SMTP is not configured and no smtp_override is provided,
    returns (False, 'SMTP not configured').

    Args:
        to_email: Primary recipient
        subject: Email subject line
        html_body: HTML body content
        attachments: Optional list of dicts with 'content' (bytes) and 'filename' (str)
        cc_emails: Optional list of CC recipient email addresses
        from_override: Optional (from_name, from_email) tuple to override SMTP_FROM defaults
        smtp_override: Optional dict with host/port/user/password/use_tls to override env vars
    """
    # Resolve SMTP connection settings
    if smtp_override and smtp_override.get("host"):
        host = smtp_override["host"]
        port = int(smtp_override.get("port", 587))
        user = smtp_override.get("user", "")
        password = smtp_override.get("password", "")
        use_tls = smtp_override.get("use_tls", True)
        from_email_addr = smtp_override.get("from_email", user) or user
        from_name_val = smtp_override.get("from_name", "") or from_email_addr
    else:
        if not is_smtp_configured():
            return (False, "SMTP not configured")
        host = SMTP_HOST
        port = SMTP_PORT
        user = SMTP_USER
        password = SMTP_PASSWORD
        use_tls = SMTP_USE_TLS
        from_email_addr = SMTP_FROM
        from_name_val = SMTP_FROM_NAME

    import smtplib
    from email.header import Header
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.base import MIMEBase
    from email import encoders

    # Sanitize inputs — replace non-breaking spaces (common copy-paste artifact)
    def _sanitize(s: str) -> str:
        return s.replace('\xa0', ' ').replace(' ', ' ') if s else s

    user = _sanitize(user)
    password = _sanitize(password)
    to_email = _sanitize(to_email)

    # Resolve sender (from_override takes highest priority)
    if from_override:
        from_name, from_email = from_override
    elif smtp_override and smtp_override.get("host"):
        from_name, from_email = from_name_val, from_email_addr
    else:
        from_name, from_email = from_name_val, from_email_addr

    try:
        msg = MIMEMultipart("mixed")
        # Encode non-ASCII headers (e.g. Japanese subject, sender name)
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = Header(f"{from_name} <{from_email}>", "utf-8")
        msg["To"] = to_email
        msg["Date"] = Header(datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0900"), "utf-8")

        # CC recipients
        all_recipients = [to_email]
        if cc_emails:
            msg["Cc"] = ", ".join(cc_emails)
            all_recipients.extend(cc_emails)

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
        if use_tls:
            server = smtplib.SMTP(host, port, timeout=15)
            server.starttls()
        else:
            server = smtplib.SMTP(host, port, timeout=15)

        server.login(user, password)
        server.sendmail(from_email, all_recipients, msg.as_string())
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
        log_entry = {
            "module": "pay_jp",
            "record_id": str(record_id),
            "action": str(action),
            "user_name": str(user_name),
            "table_name": str(table_name),
            "before_value": json.dumps(before_value, ensure_ascii=False, default=str) if before_value is not None else None,
            "after_value": json.dumps(after_value, ensure_ascii=False, default=str) if after_value is not None else None,
            "ip_address": handler.client_address[0] if hasattr(handler, 'client_address') else "",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _db.insert_record("pay_jp_audit_logs", log_entry)
    except Exception as e:
        print(f"[{MODULE_NAME}] Audit log write failed: {e}", file=_sys.stderr)


# ── Email Settings Helpers ──

def _load_email_settings(country_code: str = "JP") -> dict:
    """Load email settings for a country. Returns empty dict if not configured."""
    if not _PG_AVAILABLE:
        return {}
    try:
        rows = _db.load_table("pay_jp_email_settings", where={"country_code": country_code})
        return rows[0] if rows else {}
    except Exception:
        return {}


def _resolve_email_subject(settings: dict, payslip: dict, default_subject: str) -> str:
    """Resolve email subject from template settings or use the default."""
    template = (settings.get("email_subject_template") or "").strip()
    if not template or "{{default_subject}}" in template:
        return default_subject
    subject = template
    subject = subject.replace("{{employee_name}}", str(payslip.get("employee_name", "")))
    subject = subject.replace("{{payroll_month}}", str(payslip.get("payroll_month", "")))
    subject = subject.replace("{{entity_name}}", str(payslip.get("entity_label", payslip.get("entity_id", ""))))
    return subject


def _resolve_email_body(settings: dict, payslip_html: str) -> str:
    """Wrap payslip HTML in the custom body template if configured.

    If the template contains {{payslip_html}}, the payslip is inserted there.
    Otherwise, the payslip HTML is appended after the template.
    """
    template = (settings.get("email_body_template") or "").strip()
    if not template:
        return payslip_html
    if "{{payslip_html}}" in template:
        return template.replace("{{payslip_html}}", payslip_html)
    # Template without placeholder — append payslip at the end
    return template + "\n" + payslip_html


def _resolve_email_sender(settings: dict) -> tuple | None:
    """Resolve sender override from settings. Returns None if not configured."""
    sender_name = (settings.get("sender_name") or "").strip()
    sender_email = (settings.get("sender_email") or "").strip()
    if sender_email:
        return (sender_name or SMTP_FROM_NAME, sender_email)
    return None


def _write_email_log(payslip_id: str = "", employee_name: str = "",
                     to_email: str = "", cc_emails: list | None = None,
                     subject: str = "", sender_email: str = "",
                     status: str = "sent", error_message: str = "",
                     sent_by: str = "system") -> None:
    """Write an email send log entry to pay_jp_email_logs.

    Called after every email send attempt (success or failure).
    This is the single entry point — future migration to a centralized
    log service only needs to change this function.
    """
    if not _PG_AVAILABLE:
        return
    try:
        entry = {
            "module": MODULE_PREFIX,
            "payslip_id": payslip_id,
            "employee_name": employee_name,
            "recipient_email": to_email,
            "cc_emails": json.dumps(cc_emails or [], ensure_ascii=False),
            "sender_email": sender_email,
            "subject": subject,
            "status": status,
            "error_message": error_message,
            "sent_by": sent_by,
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }
        _db.insert_record("pay_jp_email_logs", entry)
    except Exception:
        pass  # log failure should never block the main flow


def _resolve_email_cc(settings: dict) -> list[str]:
    """Resolve CC list from settings. Returns empty list if not configured."""
    cc = settings.get("cc_recipients") or []
    if isinstance(cc, str):
        try:
            cc = json.loads(cc)
        except Exception:
            cc = []
    return [e.strip() for e in cc if isinstance(e, str) and e.strip()]


def _resolve_email_smtp(settings: dict) -> dict | None:
    """Resolve SMTP override from settings. Returns None if not configured."""
    host = (settings.get("smtp_host") or "").strip()
    if not host:
        return None
    return {
        "host": host,
        "port": settings.get("smtp_port", 587),
        "user": (settings.get("smtp_user") or "").strip(),
        "password": (settings.get("smtp_password") or "").strip(),
        "use_tls": settings.get("smtp_use_tls", True),
    }


def _generate_sample_payslip(entity_label_text: str = "",
                             visibility_overrides: dict | None = None) -> tuple[str, str, str, str]:
    """Generate a sample payslip HTML using _generate_payslip_html() so the preview
    matches real payslips exactly (respecting current visibility settings).

    Args:
        entity_label_text: Entity label for the header
        visibility_overrides: Optional {item_code: bool} for real-time preview
    """
    emp_name = "山田 太郎"
    payroll_month = "2026-07"
    entity_name = entity_label_text or "TAKK - Tech Alliance株式会社 (Japan)"

    # Build a sample record with realistic data — mirrors real calculation output
    sample_record = {
        "employee_name": emp_name,
        "employee_number": "EMP-0001",
        "payroll_month": payroll_month,
        "salary_type": "monthly",
        "department_label": "Engineering",
        "entity_id": "ENT-0002",
        # Earnings
        "base_pay_calculated": 350000,
        "overtime_pay_calc": 25000,
        "commute_allowance": 15000,
        "housing_allowance": 20000,
        "position_allowance": 30000,
        "fixed_allowance": 0,
        "transport_allowance": 0,
        "phone_allowance": 5000,
        "performance_bonus": 0,
        "project_bonus": 0,
        # Totals
        "gross_pay": 445000,
        "deduction_total": 98755,
        "net_pay": 346245,
        "employer_cost_total": 52680,
        # Deductions
        "health_insurance_employee": 20750,
        "pension_employee": 32055,
        "care_insurance_employee": 0,
        "employment_insurance_employee": 2670,
        "income_tax": 15800,
        "monthly_resident_tax": 12500,
        "recurring_deductions": 0,
        "absence_days": 0,
        # Employer cost
        "employer_health": 20750,
        "employer_pension": 32055,
        "employer_care": 0,
        "employer_employ": 3120,
        "employer_child_allowance": 0,
        "employer_child_support": 0,
        "employer_accident_insurance": 0,
    }

    html = _generate_payslip_html(sample_record, {}, entity_name,
                                   visibility_overrides=visibility_overrides)
    return html, emp_name, payroll_month, entity_name


def _dummy_payslip_data() -> tuple[str, str, str, str]:
    """Legacy — kept for backward compat. Use _generate_sample_payslip() instead."""
    return _generate_sample_payslip()


def _generate_payslip_html(record: dict, batch: dict, entity_label_text: str,
                           visibility_overrides: dict | None = None) -> str:
    """Generate a self-contained HTML payslip from a monthly salary record.

    Used for both preview and email sending. Returns a complete HTML document
    with embedded CSS suitable for email clients.

    Respects pay_jp_payroll_item_definitions.payslip_visible — items marked
    as not visible are excluded from the payslip regardless of their value.

    Args:
        record: Payslip record dict with salary fields
        batch: Batch dict (may be empty {})
        entity_label_text: Human-readable entity label for the header
        visibility_overrides: Optional dict {item_code: bool} from email settings.
            When provided, these overrides are applied on top of item definition
            defaults and DB settings. Used for real-time preview before save.
    """
    fmt = lambda v: f"¥{int(v or 0):,}"  # noqa: E731

    emp_name = record.get("employee_name", "")
    emp_num = record.get("employee_number", "")
    payroll_month = record.get("payroll_month", "") or batch.get("payroll_month", "")
    salary_type_raw = record.get("salary_type", "monthly")
    department_label = record.get("department_label", "")
    salary_type = SALARY_TYPE_LABELS.get(salary_type_raw, salary_type_raw)

    # ── Load item definitions to check payslip_visible ──
    hidden_codes: set = set()
    item_labels: dict[str, str] = {}
    if _PG_AVAILABLE:
        try:
            all_items = _db.load_table("pay_jp_payroll_item_definitions") or []
            for it in all_items:
                code = (it.get("code") or "").strip()
                if not code:
                    continue
                labels = it.get("labels", {}) or {}
                if isinstance(labels, str):
                    import json as _json
                    try:
                        labels = _json.loads(labels)
                    except Exception:
                        labels = {}
                ja_label = (labels.get("ja") or labels.get("en") or code).strip()
                item_labels[code] = ja_label
                # Default: hide if payslip_visible is explicitly False
                if it.get("payslip_visible") is False:
                    hidden_codes.add(code)

            # ── Check email settings for custom visibility overrides ──
            email_settings = _load_email_settings("JP")
            visible_items = email_settings.get("payslip_visible_items")
            if visible_items is not None:
                # User has custom visibility settings — override defaults
                if isinstance(visible_items, str):
                    import json as _json
                    try:
                        visible_items = _json.loads(visible_items)
                    except Exception:
                        visible_items = None
                if isinstance(visible_items, dict):
                    for code, is_visible in visible_items.items():
                        if is_visible:
                            hidden_codes.discard(code)
                        else:
                            hidden_codes.add(code)

            # ── Apply caller-provided visibility overrides (for real-time preview) ──
            if visibility_overrides:
                for code, is_visible in visibility_overrides.items():
                    if is_visible:
                        hidden_codes.discard(code)
                    else:
                        hidden_codes.add(code)
        except Exception as _e:
            print(f"[{MODULE_NAME}] _generate_payslip_html: visibility loading failed: {_e}", file=_sys.stderr)

    def _is_visible(field_name: str) -> bool:
        """Check if a record field should be shown on payslip."""
        code = FIELD_TO_CODE.get(field_name, field_name)
        return code not in hidden_codes

    def _get_label(field_name: str, fallback: str) -> str:
        """Get display label from item definitions, fallback to hardcoded."""
        code = FIELD_TO_CODE.get(field_name, field_name)
        return item_labels.get(code, fallback)

    # Earnings items
    earnings = []
    for key, label in PAYSLIP_EARNING_KEYS:
        if not _is_visible(key):
            continue
        val = float(record.get(key) or 0)
        if val > 0:
            earnings.append((_get_label(key, label), val))

    # Deduction items
    deductions = []
    for key, label in PAYSLIP_DEDUCTION_KEYS:
        if not _is_visible(key):
            continue
        val = float(record.get(key, record.get(key.replace("_employee", ""), 0)) or 0)
        if val > 0:
            deductions.append((_get_label(key, label), val))

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
    for key, label in PAYSLIP_EMPLOYER_KEYS:
        if not _is_visible(key):
            continue
        val = float(record.get(key) or 0)
        if val > 0:
            employer_items.append((_get_label(key, label), val))

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>給与明細 / Payslip — {payroll_month}</title>
<style>
  @media print {{
    body {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
    .no-print {{ display: none !important; }}
    .payslip-container {{ box-shadow: none !important; border: 1px solid #ccc !important; }}
  }}
  @media (max-width: 600px) {{
    .info-grid {{ grid-template-columns: 1fr !important; }}
    .payslip-container {{ max-width: 100% !important; }}
    .header-bar {{ padding: 14px 16px !important; }}
    .content-area {{ padding: 12px 16px !important; }}
  }}
</style></head>
<body style="margin:0;padding:0;font-family:'Helvetica Neue',Arial,'Hiragino Sans','Noto Sans JP',sans-serif;font-size:14px;color:#1a1a2e;line-height:1.5;">
<div class="payslip-container" style="max-width:700px;margin:0 auto;background:#fff;box-shadow:0 2px 12px rgba(0,0,0,0.08);border-radius:8px;overflow:hidden;">
  <div class="header-bar" style="background:linear-gradient(135deg,#0f2b46,#1a4a7a);color:#fff;padding:20px 28px;">
    <div style="display:flex;justify-content:space-between;align-items:flex-start;">
      <div>
        <h2 style="margin:0 0 4px;font-size:20px;font-weight:800;">📄 給与明細 / Payslip</h2>
        <p style="margin:0;opacity:.85;font-size:13px;">{entity_label_text}</p>
      </div>
      <button class="no-print" onclick="window.print()" style="background:rgba(255,255,255,0.2);color:#fff;border:1px solid rgba(255,255,255,0.4);border-radius:6px;padding:6px 14px;cursor:pointer;font-size:12px;font-weight:600;">🖨️ Print</button>
    </div>
  </div>
  <div class="content-area" style="padding:20px 28px;">
    <div class="info-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:4px 20px;margin-bottom:16px;padding:12px 16px;background:#f9fafb;border-radius:8px;">
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

    <h3 style="font-size:14px;color:#1d2a3a;border-bottom:2px solid #1B6CB2;padding-bottom:4px;margin:16px 0 8px;">🏢 会社負担 / Employer Cost</h3>
    <table style="width:100%;border-collapse:collapse;margin:6px 0;">
      {_build_rows(employer_items, employer_cost, '会社負担総額 / Total Employer Cost')}
    </table>

    <table style="width:100%;border-collapse:collapse;margin:16px 0;">
      <tr style="font-weight:800;font-size:18px;color:#059669;">
        <td style="padding:14px;background:#ecfdf5;border-radius:8px;">💵 差引支給額 / Net Pay</td>
        <td style="padding:14px;text-align:right;background:#ecfdf5;border-radius:8px;">{fmt(net)}</td>
      </tr>
    </table>

    <div style="margin-top:20px;text-align:center;color:#9ca3af;font-size:11px;border-top:1px solid #e5e7eb;padding-top:14px;">
      <p style="margin:0;">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} · Computer-generated payslip · For queries contact HR</p>
    </div>
  </div>
</div>
</body>
</html>"""
    return html


def _calc_fiscal_age(employee_id: str, emp_record: dict | None = None) -> int | None:
    """Calculate age at fiscal year start (April 1) from employee's date_of_birth.

    Reads DOB from salary master (synced from employee_admin on import).
    Returns None if DOB is unavailable or cannot be parsed.
    Used for 介護保険 eligibility (40-64 years old).
    """
    if not employee_id:
        return None

    dob_str = None

    # 1. Check the salary master record passed by caller
    if emp_record:
        dob_str = emp_record.get("date_of_birth", "")

    # 2. If not in record, query salary master DB directly
    if not dob_str and _PG_AVAILABLE:
        try:
            rows = _db.load_table("pay_jp_salary_master", where={"employee_id": employee_id})
            if rows:
                dob_str = rows[0].get("date_of_birth", "")
        except Exception:
            pass

    # 3. Parse DOB and calculate fiscal age
    if dob_str:
        try:
            if isinstance(dob_str, date):
                dob_date = dob_str
            elif isinstance(dob_str, str) and dob_str.strip():
                dob_date = datetime.strptime(dob_str.strip()[:10], "%Y-%m-%d").date()
            else:
                return None

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
        if client_host in ("127.0.0.1", "localhost", "::1", INTERNAL_HOST):
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
        elif path == "/api/payroll/jp/constants":
            self._get_constants()
        elif path == "/api/payroll/jp/parameters":
            self._list_parameters()
        elif path == "/api/payroll/jp/employees/importable":
            self._list_importable_employees()
        elif path == "/api/payroll/jp/employees":
            self._list_employees()
        elif path == "/api/payroll/jp/batches":
            self._list("pay_jp_payroll_batches")
        elif path == "/api/payroll/jp/payslips":
            self._list_payslips()
        elif path == "/api/payroll/jp/audit-logs":
            self._list("pay_jp_audit_logs")
        elif path == "/api/payroll/jp/email-settings":
            self._get_email_settings()
        elif path == "/api/payroll/jp/email-logs":
            self._list_email_logs()
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
                # Check both env vars and DB override
                smtp_ok = is_smtp_configured()
                if not smtp_ok and _PG_AVAILABLE:
                    settings = _load_email_settings("JP")
                    smtp_ok = bool((settings.get("smtp_host") or "").strip())
                send_json(self, {"smtp_configured": smtp_ok})
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
        elif path == "/api/payroll/jp/email-settings":
            self._save_email_settings(session, body)
        elif path == "/api/payroll/jp/email-settings/test":
            self._test_email_settings(session, body)
        elif path == "/api/payroll/jp/email-settings/preview":
            self._preview_email_template(session, body)
        elif path == "/api/payroll/jp/payslips/send-selected":
            self._send_selected_payslips_standalone(session, body)
        elif path == "/api/payroll/jp/payslips/send-all":
            self._send_all_payslips_filtered(session, body)
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

    def _list_employees(self):
        """List salary master employees with optional filters + pagination."""
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        try:
            search = get_query_param(self, "search", "").strip()
            entity_id = get_query_param(self, "entity_id", "").strip()
            salary_type = get_query_param(self, "salary_type", "").strip()
            department_label = get_query_param(self, "department_label", "").strip()
            status = get_query_param(self, "status", "all").strip()
            page = int(get_query_param(self, "page", "1"))
            page_size = int(get_query_param(self, "page_size", "20"))

            conditions = []
            params = []
            if search:
                conditions.append("(employee_number ILIKE %s OR employee_name ILIKE %s)")
                params.extend([f"%{search}%", f"%{search}%"])
            if entity_id:
                conditions.append("entity_id = %s")
                params.append(entity_id)
            if salary_type:
                conditions.append("salary_type = %s")
                params.append(salary_type)
            if department_label:
                conditions.append("department_label = %s")
                params.append(department_label)
            if status == "active":
                conditions.append("active = true")
            elif status == "inactive":
                conditions.append("active = false")

            where = " AND ".join(conditions) if conditions else None
            rows = _db.load_table(
                "pay_jp_salary_master",
                where=where,
                params=tuple(params) if params else None,
                order_by="created_at DESC",
            )

            total = len(rows)
            start = (page - 1) * page_size
            page_data = rows[start:start + page_size]

            paginated(self, page_data, page, page_size, total)
        except Exception as e:
            error(self, f"Database error: {str(e)}", 500)

    def _list_md_table(self, table: str, order_col: str):
        """Read master data via masterdata internal API."""
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
                internal_url("masterdata", endpoint),
                headers={"Accept": "application/json"},
                method="GET",
            )
            with urlopen(req, timeout=3) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            data = body.get("entities") or body.get("departments") or body.get("teams") or []
            paginated(self, data, 1, len(data), len(data))
        except Exception as e:
            error(self, f"Masterdata service unavailable: {str(e)}", 502)

    def _list_payslips(self):
        """List payslips with optional month and search filters."""
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        try:
            month = get_query_param(self, "payroll_month", "").strip()
            search = get_query_param(self, "search", "").strip()
            conditions = []
            params = []
            if month:
                conditions.append("payroll_month = %s")
                params.append(month)
            if search:
                conditions.append("(employee_number ILIKE %s OR employee_name ILIKE %s)")
                params.extend([f"%{search}%", f"%{search}%"])
            where = " AND ".join(conditions) if conditions else None
            rows = _db.load_table("pay_jp_payslips", where=where, params=tuple(params) if params else None, order_by="created_at DESC")
            paginated(self, rows, 1, len(rows), len(rows))
        except Exception as e:
            error(self, f"Database error: {str(e)}", 500)

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

    def _get_constants(self):
        """Return all JP payroll reference/enum data in one call.

        Used by the frontend to populate dropdowns (categories, subcategories,
        salary types, rate types, parameter types) instead of hardcoding them.
        Falls back to hardcoded defaults when DB is unavailable.
        """
        # Default fallback values
        result = {
            "item_categories": ["earning", "deduction", "employer_cost"],
            "item_category_labels": {
                "earning": "支給 (Earning)",
                "deduction": "控除 (Deduction)",
                "employer_cost": "会社負担 (Employer Cost)",
            },
            "item_subcategory_labels": {
                "base": "基本", "overtime": "残業", "allowance": "手当",
                "manual": "手動入力", "statutory": "法定", "attendance": "勤怠",
            },
            "salary_type_labels": SALARY_TYPE_LABELS,
            "rate_type_labels": [],
            "parameter_types": {
                "SOCIAL_INSURANCE_RATE": "social_insurance_rate",
                "WITHHOLDING_TAX_BRACKET": "withholding_tax_bracket",
                "STANDARD_REMUNERATION_GRADE": "standard_remuneration_grade",
                "ACCIDENT_INSURANCE_RATE": "accident_insurance_rate",
            },
        }

        if _PG_AVAILABLE:
            try:
                # Derive unique categories/subcategories from item definitions
                items = _db.load_table("pay_jp_payroll_item_definitions") or []
                cats = sorted(set(i.get("category", "") for i in items if i.get("category")))
                if cats:
                    result["item_categories"] = cats

                # Build subcategory labels from item definitions' labels field
                subcat_labels: dict = {}
                seen_subcats: set = set()
                for it in items:
                    sc = (it.get("sub_category") or "").strip()
                    if not sc or sc in seen_subcats:
                        continue
                    seen_subcats.add(sc)
                    labels = it.get("labels", {}) or {}
                    if isinstance(labels, str):
                        try:
                            labels = json.loads(labels)
                        except Exception:
                            labels = {}
                    subcat_labels[sc] = (labels.get("ja") or labels.get("en") or sc).strip()
                if subcat_labels:
                    result["item_subcategory_labels"] = subcat_labels

                # Rate type labels from DB
                rate_rows = _db.load_table("pay_jp_rate_type_labels", order_by="display_order") or []
                if rate_rows:
                    result["rate_type_labels"] = rate_rows
            except Exception:
                pass  # DB unavailable — use fallback defaults

        success(self, result)

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
                    where={"batch_id": batch_id}, order_by="employee_number ASC") or []
                data["records"] = records

                # ── Defensive recalculation: derive batch totals from actual records ──
                # This ensures frontend always sees accurate totals even if the batch
                # table has stale/inconsistent data (e.g. from a partial calculation).
                if records:
                    data["employee_count"] = len(records)
                    data["gross_total"] = sum(float(r.get("gross_pay") or 0) for r in records)
                    data["deduction_total"] = sum(float(r.get("deduction_total") or 0) for r in records)
                    data["net_total"] = sum(float(r.get("net_pay") or 0) for r in records)
                    data["employer_cost_total"] = sum(float(r.get("employer_cost_total") or 0) for r in records)

                    # Auto-correct batch status inconsistency:
                    # If batch is still "draft" but records have been calculated
                    # (gross_pay > 0), promote to "calculated".
                    # A "draft" batch with records that have gross_pay=0 is valid
                    # (records pre-populated at creation but not yet calculated).
                    if data.get("status") == "draft" and data["gross_total"] > 0:
                        now_iso = datetime.now(timezone.utc).isoformat()
                        _db.update_record("pay_jp_payroll_batches", "batch_id", batch_id, {
                            "status": "calculated",
                            "employee_count": len(records),
                            "gross_total": data["gross_total"],
                            "deduction_total": data["deduction_total"],
                            "net_total": data["net_total"],
                            "employer_cost_total": data["employer_cost_total"],
                            "updated_at": now_iso,
                        })
                        data["status"] = "calculated"
                        data["updated_at"] = now_iso
                        print(f"[{MODULE_NAME}] Auto-corrected batch {batch_id}: draft → calculated "
                              f"(records={len(records)}, gross={data['gross_total']})", file=sys.stderr)

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
                internal_url("employee_admin", "/api/internal/employees?include_payroll=true"),
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
                        internal_url("employee_admin", f"/api/internal/employees/{emp_id}?include_payroll=true"),
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
                    "date_of_birth": profile.get("date_of_birth", None) if isinstance(profile, dict) else None,
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
        age = _calc_fiscal_age(emp.get("employee_id", ""), emp) or 0
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

            # ── Pre-populate salary records from salary master ──
            # This matches the monolith behavior: batch creation also creates
            # draft records for each active employee. Records are raw (uncalculated)
            # until the user clicks "Calculate".
            employee_count = 0
            if entity_id:
                employees = _db.load_table("pay_jp_salary_master",
                    where="entity_id = %s AND active = true",
                    params=(entity_id,)) or []
                working_days = int(body.get("working_days_in_month", 22) or 22)
                for emp in employees:
                    record_id = f"JPR-{uuid.uuid4().hex[:12].upper()}"
                    rec = {
                        "record_id": record_id,
                        "batch_id": batch_id,
                        "sheet_id": batch_id,
                        "payroll_month": payroll_month,
                        "country_code": "JP",
                        "entity_id": entity_id,
                        "employee_id": emp.get("employee_id", ""),
                        "employee_number": emp.get("employee_number", ""),
                        "employee_name": emp.get("employee_name", ""),
                        "email": emp.get("email", ""),
                        "department_label": emp.get("department_label", ""),
                        "salary_type": emp.get("salary_type", "monthly"),
                        "basic_salary": float(emp.get("basic_salary") or 0),
                        "hourly_rate": float(emp.get("hourly_rate") or 0),
                        "daily_rate": float(emp.get("daily_rate") or 0),
                        "standard_work_days": float(emp.get("standard_work_days") or working_days),
                        "standard_work_hours": float(emp.get("standard_work_hours") or 176),
                        "standard_monthly_hours": float(emp.get("standard_monthly_hours") or 160),
                        "actual_work_days": float(emp.get("standard_work_days") or working_days),
                        "actual_work_hours": float(emp.get("standard_work_hours") or 176),
                        "absence_days": 0,
                        "commute_allowance": float(emp.get("commute_allowance") or 0),
                        "housing_allowance": float(emp.get("housing_allowance") or 0),
                        "family_allowance": float(emp.get("family_allowance") or 0),
                        "position_allowance": float(emp.get("position_allowance") or 0),
                        "fixed_allowance": float(emp.get("fixed_allowance") or 0),
                        "transport_allowance": float(emp.get("transport_allowance") or 0),
                        "phone_allowance": float(emp.get("phone_allowance") or 0),
                        "performance_bonus": float(emp.get("performance_bonus") or 0),
                        "project_bonus": float(emp.get("project_bonus") or 0),
                        "social_insurance_eligible": emp.get("social_insurance_eligible", True),
                        "employment_insurance_eligible": emp.get("employment_insurance_eligible", True),
                        "dependents_count": int(emp.get("dependents_count") or 0),
                        "monthly_resident_tax": float(emp.get("monthly_resident_tax") or 0),
                        "prefecture_code": emp.get("prefecture_code", "13"),
                        "status": "draft",
                        "created_at": now_iso,
                        "updated_at": now_iso,
                    }
                    _db.insert_record("pay_jp_monthly_salary_records", rec)
                    employee_count += 1

                # Update batch with employee count
                if employee_count > 0:
                    _db.update_record("pay_jp_payroll_batches", "batch_id", batch_id, {
                        "employee_count": employee_count,
                        "updated_at": now_iso,
                    })
                    batch["employee_count"] = employee_count

            result = {"batch_id": batch_id, "entity_id": entity_id, "payroll_month": payroll_month,
                      "status": "draft", "employee_count": employee_count}
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

                # Always use the latest salary master data for calculation.
                # Per-record attendance inputs (absence_days, actual_work_hours,
                # etc.) also come from salary master — they are refreshed on each
                # import from EmployeeAdmin.
                existing = existing_by_emp.get(eid, {})
                calc_emp = {**emp}

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
            active_eids = {e.get("employee_id", "") for e in employees}
            for rec in records:
                existing_id = existing_by_emp.get(rec.get("employee_id", ""), {}).get("record_id")
                if existing_id:
                    _db.update_record("pay_jp_monthly_salary_records", "record_id", existing_id, rec)
                else:
                    _db.insert_record("pay_jp_monthly_salary_records", rec)

            # Clean up records for deactivated employees
            for old_eid, old_rec in existing_by_emp.items():
                if old_eid not in active_eids:
                    try:
                        _db.delete_record("pay_jp_monthly_salary_records", "record_id", old_rec.get("record_id", ""))
                    except Exception:
                        pass

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
            updated = _db.update_record("pay_jp_payroll_batches", "batch_id", batch_id, update_batch)
            if not updated:
                print(f"[{MODULE_NAME}] WARNING: Batch update returned 0 rows affected for {batch_id}. "
                      f"Batch may be in an inconsistent state.", file=sys.stderr)

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
                    internal_url("masterdata", f"/api/internal/entity/{entity_id}/active"),
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

            # Delete unsent payslips for this batch
            payslips = _db.load_table("pay_jp_payslips",
                where="batch_id = %s AND email_status != 'sent'",
                params=(batch_id,)) or []
            for ps in payslips:
                try:
                    _db.delete_record("pay_jp_payslips", "record_id", ps.get("record_id", ""))
                except Exception:
                    pass

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
        """Permanently delete a batch and its monthly salary records.

        Any batch that is NOT confirmed can be deleted (hard delete).
        Confirmed batches cannot be deleted — rollback first.
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
            if batch_status == "confirmed":
                error(self, "Cannot delete confirmed batches. Rollback first.", 400)
                return

            # Capture before snapshot for audit
            before_snapshot = {k: v for k, v in batch_list[0].items()
                               if k in ("batch_id", "entity_id", "payroll_month", "status",
                                         "employee_count", "gross_total", "net_total", "created_by")}

            # Delete associated payslips first (if any)
            payslips = _db.load_table("pay_jp_payslips", where={"batch_id": batch_id}) or []
            for ps in payslips:
                try:
                    _db.delete_record("pay_jp_payslips", "record_id", ps.get("record_id", ""))
                except Exception:
                    pass

            # Delete associated monthly salary records
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

    # ── Email Logs ──
    def _list_email_logs(self):
        """List email send logs with optional filters."""
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        try:
            limit = int(get_query_param(self, "limit", "50"))
            status = get_query_param(self, "status", "")
            payslip_id = get_query_param(self, "payslip_id", "")

            where_parts = []
            params = []
            if status:
                where_parts.append("status = %s")
                params.append(status)
            if payslip_id:
                where_parts.append("payslip_id = %s")
                params.append(payslip_id)

            where = " AND ".join(where_parts) if where_parts else None
            logs = _db.load_table("pay_jp_email_logs", where=where, params=tuple(params) if params else None,
                                  order_by="sent_at DESC") or []
            logs = logs[:limit]
            paginated(self, logs, 1, len(logs), len(logs))
        except Exception as e:
            error(self, f"List email logs failed: {str(e)}", 500)

    # ── Email Settings CRUD ──
    def _get_email_settings(self):
        """Get email settings for a country (default JP)."""
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        try:
            country_code = get_query_param(self, "country_code", "JP")
            settings = _load_email_settings(country_code)
            # Redact password — only return whether it's set
            if settings:
                settings["smtp_password_set"] = bool(settings.get("smtp_password"))
                settings.pop("smtp_password", None)
            else:
                settings = {"country_code": country_code, "smtp_password_set": False}
            success(self, settings)
        except Exception as e:
            error(self, f"Get email settings failed: {str(e)}", 500)

    def _save_email_settings(self, session, body):
        """Create or update email settings for a country."""
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        if not self._check_permission(session, "tacaipay_jp.manage"):
            error(self, "Forbidden", 403)
            return
        try:
            user_name = session.get("email", "system")
            country_code = (body or {}).get("country_code", "JP")
            now_iso = datetime.now(timezone.utc).isoformat()

            # Build settings record
            # Handle payslip_visible_items — user's custom visibility overrides
            visible_items = (body or {}).get("payslip_visible_items", None)
            if visible_items is not None:
                visible_items = json.dumps(visible_items, ensure_ascii=False)

            record = {
                "country_code": country_code,
                "sender_name": (body or {}).get("sender_name", ""),
                "sender_email": (body or {}).get("sender_email", ""),
                "cc_recipients": json.dumps((body or {}).get("cc_recipients", []), ensure_ascii=False),
                "email_subject_template": (body or {}).get("email_subject_template", ""),
                "email_body_template": (body or {}).get("email_body_template", ""),
                "payslip_visible_items": visible_items,
                "smtp_host": (body or {}).get("smtp_host", ""),
                "smtp_port": (body or {}).get("smtp_port", 587),
                "smtp_user": (body or {}).get("smtp_user", ""),
                "smtp_use_tls": (body or {}).get("smtp_use_tls", True),
                "updated_at": now_iso,
                "updated_by": user_name,
            }

            # Handle password: if empty and password_set flag is true, keep existing
            existing = _load_email_settings(country_code)
            new_password = (body or {}).get("smtp_password", "")
            if new_password:
                record["smtp_password"] = new_password
            elif (body or {}).get("smtp_password_set") and existing.get("smtp_password"):
                record["smtp_password"] = existing["smtp_password"]

            # Upsert
            if existing:
                _db.update_record("pay_jp_email_settings", "country_code", country_code, record)
            else:
                record["created_at"] = now_iso
                _db.insert_record("pay_jp_email_settings", record)

            _write_audit_log(self, "EMAIL_SETTINGS_SAVED", "pay_jp_email_settings", country_code,
                             user_name, after_value={"country_code": country_code})

            # Return without password
            result = dict(record)
            result["smtp_password_set"] = bool(record.get("smtp_password"))
            result.pop("smtp_password", None)
            success(self, result)
        except Exception as e:
            error(self, f"Save email settings failed: {str(e)}", 500)

    def _test_email_settings(self, session, body):
        """Send a test email using the configured settings."""
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        if not self._check_permission(session, "tacaipay_jp.manage"):
            error(self, "Forbidden", 403)
            return
        try:
            user_name = session.get("email", "system")
            test_to = (body or {}).get("test_to", "").strip()
            if not test_to:
                error(self, "test_to is required", 400)
                return

            country_code = (body or {}).get("country_code", "JP")
            settings = _load_email_settings(country_code)

            # Build test email
            subject = f"[TEST] TACAI Payroll JP — Email Settings Test"
            html_body = f"""<!DOCTYPE html>
<html><body style="font-family:sans-serif;padding:20px;">
  <h2>✅ メール設定テスト / Email Settings Test</h2>
  <p>これは TACAI Payroll JP からのテストメールです。</p>
  <p>This is a test email from TACAI Payroll JP.</p>
  <hr>
  <table style="border-collapse:collapse;font-size:13px;">
    <tr><td style="padding:4px 12px 4px 0;color:#6b7280;">送信者 / Sender</td><td>{settings.get('sender_name', 'System Default')} &lt;{settings.get('sender_email', SMTP_FROM)}&gt;</td></tr>
    <tr><td style="padding:4px 12px 4px 0;color:#6b7280;">国 / Country</td><td>{country_code}</td></tr>
    <tr><td style="padding:4px 12px 4px 0;color:#6b7280;">送信日時 / Sent</td><td>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
  </table>
  <p style="color:#059669;font-weight:600;">SMTP 設定は正常に動作しています / SMTP configuration is working correctly.</p>
</body></html>"""

            from_override = _resolve_email_sender(settings)
            cc_list = _resolve_email_cc(settings)

            success_flag, error_msg = _send_email(
                test_to, subject, html_body,
                cc_emails=cc_list if cc_list else None,
                from_override=from_override,
                smtp_override=_resolve_email_smtp(settings),
            )

            _write_email_log(
                to_email=test_to, cc_emails=cc_list if cc_list else [],
                subject=subject, sender_email=from_override[1] if from_override else SMTP_FROM,
                status="sent" if success_flag else "failed",
                error_message="" if success_flag else error_msg, sent_by=user_name,
            )

            if success_flag:
                _write_audit_log(self, "EMAIL_SETTINGS_TEST", "pay_jp_email_settings", country_code,
                                 user_name, after_value={"test_to": test_to, "status": "success"})
                success(self, {"message": "Test email sent successfully", "test_to": test_to})
            else:
                _write_audit_log(self, "EMAIL_SETTINGS_TEST_FAILED", "pay_jp_email_settings", country_code,
                                 user_name, after_value={"test_to": test_to, "status": "failed", "error": error_msg})
                error(self, f"Test email failed: {error_msg}", 500)
        except Exception as e:
            error(self, f"Test email settings failed: {str(e)}", 500)

    def _preview_email_template(self, session, body):
        """Preview how an email will look with the current template settings applied.

        Uses _generate_payslip_html() with sample data so the preview matches
        what real payslips look like (respecting payslip_visible settings).
        Accepts optional payslip_visible_items for real-time preview before save.
        """
        if not self._check_permission(session, "tacaipay_jp.manage"):
            error(self, "Forbidden", 403)
            return
        try:
            body = body or {}
            subject_template = body.get("email_subject_template", "").strip()
            body_template = body.get("email_body_template", "").strip()
            payslip_id = body.get("payslip_id", "").strip()
            visibility_overrides = body.get("payslip_visible_items", None)

            entity_label_text = "TAKK - Tech Alliance株式会社 (Japan)"

            # Get payslip data — use real payslip if specified, otherwise generate sample
            if payslip_id and _PG_AVAILABLE:
                ps_list = _db.load_table("pay_jp_payslips", where={"record_id": payslip_id})
                if ps_list:
                    ps = ps_list[0]
                    payslip_html = _generate_payslip_html(ps, {}, entity_label_text,
                                                          visibility_overrides=visibility_overrides)
                    employee_name = ps.get("employee_name", "山田 太郎")
                    payroll_month = ps.get("payroll_month", "2026-07")
                    entity_name = entity_label_text
                else:
                    payslip_html, employee_name, payroll_month, entity_name = _generate_sample_payslip(
                        entity_label_text, visibility_overrides)
            else:
                payslip_html, employee_name, payroll_month, entity_name = _generate_sample_payslip(
                    entity_label_text, visibility_overrides)

            # Build a pseudo settings dict for the resolver functions
            settings = {
                "email_subject_template": subject_template,
                "email_body_template": body_template,
            }

            # Resolve subject
            default_subject = DEFAULT_PAYSLIP_SUBJECT.format(payroll_month=payroll_month, employee_name=employee_name)
            subject = _resolve_email_subject(settings, {
                "employee_name": employee_name,
                "payroll_month": payroll_month,
                "entity_label": entity_name,
            }, default_subject)

            # Resolve body
            html_body = _resolve_email_body(settings, payslip_html)

            success(self, {
                "subject": subject,
                "html": html_body,
                "employee_name": employee_name,
                "payroll_month": payroll_month,
                "entity_name": entity_name,
                "is_sample": not payslip_id,
            })
        except Exception as e:
            error(self, f"Preview template failed: {str(e)}", 500)

    # ── Standalone Batch Send Endpoints (for payslip list page) ──
    def _send_selected_payslips_standalone(self, session, body):
        """Send selected payslips by record_id list (no batch context required)."""
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        if not self._check_permission(session, "tacaipay_jp.approve"):
            error(self, "Forbidden", 403)
            return
        try:
            record_ids = (body or {}).get("record_ids", [])
            if not record_ids:
                error(self, "No record_ids provided", 400)
                return

            user_name = session.get("email", "system")
            settings = _load_email_settings("JP")
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
                    results.append({"record_id": ps_id, "employee_name": ps.get("employee_name", ""),
                                    "status": "failed", "error": "No email address"})
                    continue

                # Resolve subject
                default_subject = DEFAULT_PAYSLIP_SUBJECT.format(payroll_month=ps.get('payroll_month', ''), employee_name=ps.get('employee_name', ''))
                subject = _resolve_email_subject(settings, ps, default_subject)

                # Resolve body
                html_body = _resolve_email_body(settings, ps.get("html_content", ""))

                # Resolve sender & CC
                from_override = _resolve_email_sender(settings)
                cc_list = _resolve_email_cc(settings)

                success_flag, error_msg = _send_email(
                    to_email, subject, html_body,
                    cc_emails=cc_list if cc_list else None,
                    from_override=from_override,
                    smtp_override=_resolve_email_smtp(settings),
                )

                _write_email_log(
                    payslip_id=ps_id, employee_name=ps.get("employee_name", ""),
                    to_email=to_email, cc_emails=cc_list if cc_list else [],
                    subject=subject, sender_email=from_override[1] if from_override else SMTP_FROM,
                    status="sent" if success_flag else "failed",
                    error_message="" if success_flag else error_msg, sent_by=user_name,
                )

                if success_flag:
                    _db.update_record("pay_jp_payslips", "record_id", ps_id, {
                        "email_status": "sent", "sent_at": now_iso, "sent_by": user_name,
                        "email_error": None, "updated_at": now_iso,
                    })
                    sent_count += 1
                    results.append({"record_id": ps_id, "employee_name": ps.get("employee_name", ""), "status": "sent"})
                else:
                    _db.update_record("pay_jp_payslips", "record_id", ps_id, {
                        "email_status": "failed", "email_error": error_msg, "updated_at": now_iso,
                    })
                    failed_count += 1
                    results.append({"record_id": ps_id, "employee_name": ps.get("employee_name", ""),
                                    "status": "failed", "error": error_msg})

            _write_audit_log(self, "EMAIL_LIST_SELECTED_SENT", "pay_jp_payslips", "batch",
                             user_name, after_value={"sent": sent_count, "failed": failed_count})

            success(self, {"sent": sent_count, "failed": failed_count, "total": len(record_ids), "results": results})
        except Exception as e:
            error(self, f"Send selected payslips failed: {str(e)}", 500)

    def _send_all_payslips_filtered(self, session, body):
        """Send all unsent payslips matching the given filters."""
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        if not self._check_permission(session, "tacaipay_jp.approve"):
            error(self, "Forbidden", 403)
            return
        try:
            user_name = session.get("email", "system")
            settings = _load_email_settings("JP")

            # Build filter conditions matching _list_payslips logic
            payroll_month = (body or {}).get("payroll_month", "").strip()
            search = (body or {}).get("search", "").strip()

            # Query all unsent payslips with optional filters
            where_parts = ["(email_status = 'not_sent' OR email_status IS NULL)"]
            params = []

            if payroll_month:
                where_parts.append("payroll_month = %s")
                params.append(payroll_month)
            if search:
                where_parts.append("(employee_name ILIKE %s OR employee_number ILIKE %s)")
                params.append(f"%{search}%")
                params.append(f"%{search}%")

            where_clause = " AND ".join(where_parts)
            all_ps = _db.load_table("pay_jp_payslips", where=where_clause, params=tuple(params)) if params else \
                     _db.load_table("pay_jp_payslips", where=where_clause)

            all_ps = all_ps or []
            if not all_ps:
                success(self, {"sent": 0, "failed": 0, "total": 0, "message": "No unsent payslips found", "results": []})
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
                    results.append({"record_id": ps_id, "employee_name": ps.get("employee_name", ""),
                                    "status": "failed", "error": "No email address"})
                    continue

                default_subject = DEFAULT_PAYSLIP_SUBJECT.format(payroll_month=ps.get('payroll_month', ''), employee_name=ps.get('employee_name', ''))
                subject = _resolve_email_subject(settings, ps, default_subject)
                html_body = _resolve_email_body(settings, ps.get("html_content", ""))
                from_override = _resolve_email_sender(settings)
                cc_list = _resolve_email_cc(settings)

                success_flag, error_msg = _send_email(
                    to_email, subject, html_body,
                    cc_emails=cc_list if cc_list else None,
                    from_override=from_override,
                    smtp_override=_resolve_email_smtp(settings),
                )

                _write_email_log(
                    payslip_id=ps_id, employee_name=ps.get("employee_name", ""),
                    to_email=to_email, cc_emails=cc_list if cc_list else [],
                    subject=subject, sender_email=from_override[1] if from_override else SMTP_FROM,
                    status="sent" if success_flag else "failed",
                    error_message="" if success_flag else error_msg, sent_by=user_name,
                )

                if success_flag:
                    _db.update_record("pay_jp_payslips", "record_id", ps_id, {
                        "email_status": "sent", "sent_at": now_iso, "sent_by": user_name,
                        "email_error": None, "updated_at": now_iso,
                    })
                    sent_count += 1
                    results.append({"record_id": ps_id, "employee_name": ps.get("employee_name", ""), "status": "sent"})
                else:
                    _db.update_record("pay_jp_payslips", "record_id", ps_id, {
                        "email_status": "failed", "email_error": error_msg, "updated_at": now_iso,
                    })
                    failed_count += 1
                    results.append({"record_id": ps_id, "employee_name": ps.get("employee_name", ""),
                                    "status": "failed", "error": error_msg})

            _write_audit_log(self, "EMAIL_LIST_ALL_SENT", "pay_jp_payslips", "filtered",
                             user_name, after_value={"sent": sent_count, "failed": failed_count})

            success(self, {"sent": sent_count, "failed": failed_count, "total": len(all_ps), "results": results})
        except Exception as e:
            error(self, f"Send all payslips failed: {str(e)}", 500)

    # ── New: Get Payslip HTML ──
    def _get_payslip_html(self, payslip_id):
        """Return payslip HTML — regenerates dynamically to reflect current template settings."""
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        try:
            ps_list = _db.load_table("pay_jp_payslips", where={"record_id": payslip_id})
            if not ps_list:
                error(self, "Payslip not found", 404)
                return
            ps = ps_list[0]

            # Load the salary record for detailed item values.
            # Payslip record_id is PS-JP-* (payslip PK). The salary record uses JPR-* IDs.
            # Relationship: payslip.sheet_id = record.batch_id AND payslip.employee_id = record.employee_id
            record_data = {}
            sheet_id = ps.get("sheet_id", "")
            employee_id = ps.get("employee_id", "")
            if sheet_id and employee_id:
                rec_list = _db.load_table("pay_jp_monthly_salary_records",
                    where="batch_id = %s AND employee_id = %s",
                    params=(sheet_id, employee_id))
                if rec_list:
                    record_data = rec_list[0]

            # Merge: record fields provide detail items, payslip provides identity + totals
            merged = dict(record_data)
            for k in ("employee_name", "employee_number", "payroll_month", "gross_pay", "net_pay",
                       "entity_id", "department_label", "salary_type"):
                if k not in merged or not merged.get(k):
                    merged[k] = ps.get(k, "")

            # Resolve entity label via masterdata internal API
            entity_id = merged.get("entity_id", "")
            entity_label = entity_id  # fallback
            if entity_id:
                try:
                    req = Request(
                        internal_url("masterdata", f"/api/internal/entity/{entity_id}/active"),
                        headers={"Accept": "application/json"},
                        method="GET",
                    )
                    with urlopen(req, timeout=3) as resp:
                        body = json.loads(resp.read().decode("utf-8"))
                    ent = body.get("entity") or {}
                    if ent:
                        entity_label = f"{ent.get('entity_code', '')} - {ent.get('entity_name', '')} ({ent.get('country', '')})"
                except Exception:
                    pass

            # Regenerate HTML dynamically using current template + visibility settings
            html = _generate_payslip_html(merged, {}, entity_label)

            success(self, {"record_id": payslip_id, "html": html})
        except Exception as e:
            error(self, f"Get payslip HTML failed: {str(e)}", 500)

    # ── New: Send single payslip email ──
    def _send_single_payslip(self, session, payslip_id):
        """Send a single payslip by email (uses email settings for sender/CC/template)."""
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

            # Load email settings
            settings = _load_email_settings("JP")

            # Resolve subject
            default_subject = DEFAULT_PAYSLIP_SUBJECT.format(payroll_month=ps.get('payroll_month', ''), employee_name=ps.get('employee_name', ''))
            subject = _resolve_email_subject(settings, ps, default_subject)

            # Resolve body
            html = ps.get("html_content", "") or _generate_payslip_html(ps, {}, ps.get("entity_id", ""))
            html = _resolve_email_body(settings, html)

            # Resolve sender & CC
            from_override = _resolve_email_sender(settings)
            cc_list = _resolve_email_cc(settings)

            success_flag, error_msg = _send_email(
                to_email, subject, html,
                cc_emails=cc_list if cc_list else None,
                from_override=from_override,
                smtp_override=_resolve_email_smtp(settings),
            )

            _write_email_log(
                payslip_id=payslip_id, employee_name=ps.get("employee_name", ""),
                to_email=to_email, cc_emails=cc_list if cc_list else [],
                subject=subject, sender_email=from_override[1] if from_override else SMTP_FROM,
                status="sent" if success_flag else "failed",
                error_message="" if success_flag else error_msg, sent_by=user_name,
            )

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

    # ── Send all payslips for a batch ──
    def _send_all_payslips(self, session, batch_id):
        """Send all unsent payslips for a batch (uses email settings)."""
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        if not self._check_permission(session, "tacaipay_jp.approve"):
            error(self, "Forbidden", 403)
            return
        try:
            user_name = session.get("email", "system")
            settings = _load_email_settings("JP")
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

                default_subject = DEFAULT_PAYSLIP_SUBJECT.format(payroll_month=ps.get('payroll_month', ''), employee_name=ps.get('employee_name', ''))
                subject = _resolve_email_subject(settings, ps, default_subject)
                html = _resolve_email_body(settings, ps.get("html_content", ""))
                from_override = _resolve_email_sender(settings)
                cc_list = _resolve_email_cc(settings)

                success_flag, error_msg = _send_email(
                    to_email, subject, html,
                    cc_emails=cc_list if cc_list else None,
                    from_override=from_override,
                    smtp_override=_resolve_email_smtp(settings),
                )

                _write_email_log(
                    payslip_id=ps_id, employee_name=ps.get("employee_name", ""),
                    to_email=to_email, cc_emails=cc_list if cc_list else [],
                    subject=subject, sender_email=from_override[1] if from_override else SMTP_FROM,
                    status="sent" if success_flag else "failed",
                    error_message="" if success_flag else error_msg, sent_by=user_name,
                )

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

    # ── Send selected payslips ──
    def _send_selected_payslips(self, session, batch_id, body):
        """Send selected payslips by record_id list (uses email settings)."""
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
            settings = _load_email_settings("JP")
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

                default_subject = DEFAULT_PAYSLIP_SUBJECT.format(payroll_month=ps.get('payroll_month', ''), employee_name=ps.get('employee_name', ''))
                subject = _resolve_email_subject(settings, ps, default_subject)
                html = _resolve_email_body(settings, ps.get("html_content", ""))
                from_override = _resolve_email_sender(settings)
                cc_list = _resolve_email_cc(settings)

                success_flag, error_msg = _send_email(
                    to_email, subject, html,
                    cc_emails=cc_list if cc_list else None,
                    from_override=from_override,
                    smtp_override=_resolve_email_smtp(settings),
                )

                _write_email_log(
                    payslip_id=ps_id, employee_name=ps.get("employee_name", ""),
                    to_email=to_email, cc_emails=cc_list if cc_list else [],
                    subject=subject, sender_email=from_override[1] if from_override else SMTP_FROM,
                    status="sent" if success_flag else "failed",
                    error_message="" if success_flag else error_msg, sent_by=user_name,
                )

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
