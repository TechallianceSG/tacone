#!/usr/bin/env python3
"""TACAI Invoice Management Service.

Handles 5 core workflows:
  Flow 1: Customer Project Configuration (main recipient, CC, auto-fill)
  Flow 2: Monthly Dispatch Reminders (auto-scan, pending list, reminders)
  Flow 3: Invoice Creation (select project, auto-fill items, submit)
  Flow 4: Approval & Sending (finance review, manager approval, email)
  Flow 5: Payment Reconciliation (register payment, balance, overdue)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, date, timedelta, timezone
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

# ── Shared libraries ──
import sys as _sys
_shared_path = Path(__file__).resolve().parents[2] / 'shared'
if str(_shared_path) not in _sys.path:
    _sys.path.insert(0, str(_shared_path))

try:
    import db_utils as _db
    _PG_AVAILABLE = _db.DB_ENABLED if hasattr(_db, 'DB_ENABLED') else True
except Exception:
    _PG_AVAILABLE = False


_CORS_ORIGINS = {
    "http://localhost:5173", "http://127.0.0.1:5173",
    "http://localhost:4173", "http://127.0.0.1:4173",
    "http://localhost:3000", "http://127.0.0.1:3000",
}

def _add_cors_headers(handler):
    origin = handler.headers.get("Origin", "")
    allowed = origin if origin in _CORS_ORIGINS else "http://localhost:5173"
    handler.send_header("Access-Control-Allow-Origin", allowed)
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")
    handler.send_header("Access-Control-Allow-Credentials", "true")
    handler.send_header("Access-Control-Max-Age", "86400")

def send_json(handler, data, status=200):
    body = json.dumps(data, ensure_ascii=False, default=str).encode('utf-8')
    handler.send_response(status)
    _add_cors_headers(handler)
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
MODULE_PREFIX = "inv"
MODULE_NAME = "tacaiinvoice"
DEFAULT_PORT = 8019
USER_ADMIN_SESSION_COOKIE = "tacai_session_id"
REQUIRED_MODULE_PERMISSION = "invoice.access"
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


def generate_invoice_number(prefix: str = "INV") -> str:
    """Generate sequential invoice number: INV-20260701-XXXX"""
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    seq = uuid.uuid4().hex[:4].upper()
    return f"{prefix}-{today}-{seq}"


class InvoiceHandler(BaseHTTPRequestHandler):

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
        _add_cors_headers(self)
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

        # Flow 1: Customer Projects
        if path == "/api/invoice/customer-projects":
            self._list("inv_customer_projects")
        # Flow 2: Pending Invoices
        elif path == "/api/invoice/pending":
            self._list("inv_pending_invoices")
        # Flow 3: Invoices
        elif path == "/api/invoice/invoices":
            self._list_invoices(session)
        # Flow 5: Overdue
        elif path == "/api/invoice/overdue":
            self._list_overdue()
        # Detail routes
        elif path.startswith("/api/invoice/customer-projects/"):
            self._detail("inv_customer_projects", "project_id", path.split("/")[-1])
        elif path.startswith("/api/invoice/invoices/") and "/payments" in path:
            invoice_id = path.split("/")[4]
            self._list_payments(invoice_id)
        elif path.startswith("/api/invoice/invoices/") and "/reconciliation" in path:
            invoice_id = path.split("/")[4]
            self._get_reconciliation(invoice_id)
        elif path.startswith("/api/invoice/invoices/") and "/email-logs" in path:
            invoice_id = path.split("/")[4]
            self._list_email_logs(invoice_id)
        elif path.startswith("/api/invoice/invoices/") and "/approvals" in path:
            invoice_id = path.split("/")[4]
            self._list_approvals(invoice_id)
        elif path.startswith("/api/invoice/invoices/"):
            self._detail("inv_invoices", "invoice_id", path.split("/")[-1])
        elif path.startswith("/api/invoice/pending/"):
            self._detail("inv_pending_invoices", "pending_id", path.split("/")[-1])
        else:
            error(self, "Not Found", 404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"
        session = self._require_auth()
        if not session:
            return
        body = parse_json_body(self)

        # Flow 1: Save project
        if path == "/api/invoice/customer-projects":
            self._save_project(session, body)

        # Flow 2: Pending operations
        elif path == "/api/invoice/pending/scan":
            self._scan_pending(session, body)
        elif path.startswith("/api/invoice/pending/") and path.endswith("/convert"):
            pending_id = path.split("/")[-2]
            self._convert_pending(session, pending_id, body)
        elif path.startswith("/api/invoice/pending/") and path.endswith("/remind"):
            pending_id = path.split("/")[-2]
            self._remind_pending(session, pending_id)

        # Flow 3: Invoice CRUD
        elif path == "/api/invoice/invoices":
            self._create_invoice(session, body)
        elif path.startswith("/api/invoice/invoices/") and path.endswith("/update"):
            invoice_id = path.split("/")[-2]
            self._update_invoice(session, invoice_id, body)
        elif path.startswith("/api/invoice/invoices/") and path.endswith("/submit"):
            invoice_id = path.split("/")[-2]
            self._submit_invoice(session, invoice_id, body)

        # Flow 4: Approval & Sending
        elif path.startswith("/api/invoice/invoices/") and path.endswith("/approve"):
            invoice_id = path.split("/")[-2]
            self._approve_invoice(session, invoice_id, body)
        elif path.startswith("/api/invoice/invoices/") and path.endswith("/reject"):
            invoice_id = path.split("/")[-2]
            self._reject_invoice(session, invoice_id, body)
        elif path.startswith("/api/invoice/invoices/") and path.endswith("/send-email"):
            invoice_id = path.split("/")[-2]
            self._send_invoice_email(session, invoice_id, body)

        # Flow 5: Payment & Reconciliation
        elif path.startswith("/api/invoice/invoices/") and path.endswith("/payments"):
            invoice_id = path.split("/")[-2]
            self._register_payment(session, invoice_id, body)
        elif path.startswith("/api/invoice/invoices/") and path.endswith("/reconcile"):
            invoice_id = path.split("/")[-2]
            self._reconcile(session, invoice_id)
        else:
            error(self, "Not Found", 404)

    # ── Generic DB helpers ──
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
            if row:
                # For invoice detail, also include items and approval history
                if table == "inv_invoices":
                    invoice = row[0]
                    invoice["items"] = _db.load_table("inv_invoice_items", where={"invoice_id": pk_val})
                    invoice["approvals"] = _db.load_table("inv_approval_records", where={"invoice_id": pk_val})
                    invoice["payments"] = _db.load_table("inv_payments", where={"invoice_id": pk_val})
                    invoice["email_logs"] = _db.load_table("inv_email_logs", where={"invoice_id": pk_val})
                    success(self, invoice)
                else:
                    success(self, row[0])
            else:
                error(self, "Not Found", 404)
        except Exception as e:
            error(self, f"Database error: {str(e)}", 500)

    # ── Flow 1: Customer Projects ──
    def _save_project(self, session, body):
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        if not self._check_permission(session, "invoice.maintain"):
            error(self, "Forbidden", 403)
            return
        try:
            project_id = body.get("project_id") or f"PRJ-{uuid.uuid4().hex[:12].upper()}"
            body["project_id"] = project_id
            existing = _db.load_table("inv_customer_projects", where={"project_id": project_id})
            user_email = session.get("user", {}).get("email", "system")

            if existing:
                body["updated_at"] = datetime.now(timezone.utc).isoformat()
                body["updated_by"] = user_email
                _db.update_record("inv_customer_projects", "project_id", project_id, body)
            else:
                body["created_at"] = datetime.now(timezone.utc).isoformat()
                body["created_by"] = user_email
                body["updated_at"] = datetime.now(timezone.utc).isoformat()
                _db.insert_record("inv_customer_projects", body)

            # Audit log
            _db.insert_record("inv_audit_logs", {
                "audit_id": f"AUD-{uuid.uuid4().hex[:12].upper()}",
                "module": "invoice",
                "record_id": project_id,
                "record_type": "customer_project",
                "action": "update" if existing else "create",
                "user": user_email,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            success(self, {"project_id": project_id})
        except Exception as e:
            error(self, f"Save failed: {str(e)}", 500)

    # ── Flow 2: Pending Invoice Operations ──
    def _scan_pending(self, session, body):
        """Auto-scan for billable periods and generate pending invoice list."""
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        if not self._check_permission(session, "invoice.maintain"):
            error(self, "Forbidden", 403)
            return
        try:
            # Scan active customer projects
            projects = _db.load_table("inv_customer_projects", where={"active": True})
            created = 0
            today = date.today()
            period_start = today.replace(day=1)  # First of current month

            for proj in projects:
                # Check if a pending invoice already exists for this period
                existing = _db.load_table("inv_pending_invoices", where={
                    "project_id": proj.get("project_id", ""),
                    "status": "pending",
                })
                if existing:
                    continue

                pending_id = f"PEN-{uuid.uuid4().hex[:12].upper()}"
                _db.insert_record("inv_pending_invoices", {
                    "pending_id": pending_id,
                    "project_id": proj.get("project_id", ""),
                    "customer_id": proj.get("customer_id", ""),
                    "customer_name": proj.get("customer_name", ""),
                    "project_code": proj.get("project_code", ""),
                    "project_name": proj.get("project_name", ""),
                    "period_start": period_start.isoformat(),
                    "period_end": today.isoformat(),
                    "estimated_amount": 0,
                    "currency": proj.get("default_currency", "JPY"),
                    "employee_count": 0,
                    "status": "pending",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                })
                created += 1

            success(self, {"scanned": len(projects), "created": created})
        except Exception as e:
            error(self, f"Scan failed: {str(e)}", 500)

    def _convert_pending(self, session, pending_id, body):
        """Convert a pending invoice to a draft invoice."""
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        if not self._check_permission(session, "invoice.maintain"):
            error(self, "Forbidden", 403)
            return
        try:
            pending_list = _db.load_table("inv_pending_invoices", where={"pending_id": pending_id})
            if not pending_list:
                error(self, "Pending invoice not found", 404)
                return
            pending = pending_list[0]

            # Load project config for auto-fill
            project_list = _db.load_table("inv_customer_projects", where={"project_id": pending.get("project_id", "")})
            project = project_list[0] if project_list else {}

            invoice_id = f"INV-{uuid.uuid4().hex[:12].upper()}"
            invoice_number = generate_invoice_number(project.get("invoice_prefix", "INV"))
            due_days = int(project.get("payment_terms_days", 30) or 30)
            today = date.today()

            invoice = {
                "invoice_id": invoice_id,
                "invoice_number": invoice_number,
                "project_id": pending.get("project_id", ""),
                "customer_id": pending.get("customer_id", ""),
                "customer_name": pending.get("customer_name", ""),
                "entity_id": project.get("entity_id", ""),
                "invoice_date": today.isoformat(),
                "due_date": (today + timedelta(days=due_days)).isoformat(),
                "period_start": pending.get("period_start", ""),
                "period_end": pending.get("period_end", ""),
                "currency": pending.get("currency", "JPY"),
                "subtotal": 0,
                "tax_rate": project.get("default_tax_rate", "10%"),
                "tax_amount": 0,
                "total_amount": 0,
                "status": "draft",
                "main_recipient_name": project.get("main_recipient_name", ""),
                "main_recipient_email": project.get("main_recipient_email", ""),
                "cc_recipients": project.get("cc_recipients", "[]"),
                "notes": pending.get("notes", ""),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": session.get("user", {}).get("email", "system"),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            _db.insert_record("inv_invoices", invoice)

            # Update pending status
            _db.update_record("inv_pending_invoices", "pending_id", pending_id, {
                "status": "converted",
                "converted_to_invoice_id": invoice_id,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })

            success(self, invoice)
        except Exception as e:
            error(self, f"Convert failed: {str(e)}", 500)

    def _remind_pending(self, session, pending_id):
        """Send reminder notification via messaging service."""
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        try:
            _db.update_record("inv_pending_invoices", "pending_id", pending_id, {
                "status": "reminded",
                "reminder_sent_at": datetime.now(timezone.utc).isoformat(),
                "reminder_sent_by": session.get("user", {}).get("email", "system"),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            # TODO: integrate with messaging service to send actual notification
            success(self, {"pending_id": pending_id, "status": "reminded"})
        except Exception as e:
            error(self, f"Remind failed: {str(e)}", 500)

    # ── Flow 3: Invoice CRUD ──
    def _list_invoices(self, session):
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        try:
            status_filter = get_query_param(self, "status", "")
            where = {"status": status_filter} if status_filter else None
            rows = _db.load_table("inv_invoices", where=where, order_by="created_at DESC")
            success(self, {"items": rows, "total": len(rows)})
        except Exception as e:
            error(self, f"Database error: {str(e)}", 500)

    def _create_invoice(self, session, body):
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        if not self._check_permission(session, "invoice.maintain"):
            error(self, "Forbidden", 403)
            return
        try:
            invoice_id = body.get("invoice_id") or f"INV-{uuid.uuid4().hex[:12].upper()}"
            project_id = body.get("project_id", "")

            # Auto-fill from project config
            if project_id:
                project_list = _db.load_table("inv_customer_projects", where={"project_id": project_id})
                if project_list:
                    proj = project_list[0]
                    body.setdefault("customer_id", proj.get("customer_id", ""))
                    body.setdefault("customer_name", proj.get("customer_name", ""))
                    body.setdefault("main_recipient_name", proj.get("main_recipient_name", ""))
                    body.setdefault("main_recipient_email", proj.get("main_recipient_email", ""))
                    body.setdefault("cc_recipients", proj.get("cc_recipients", "[]"))
                    body.setdefault("currency", proj.get("default_currency", "JPY"))
                    body.setdefault("tax_rate", proj.get("default_tax_rate", "10%"))

            invoice_number = generate_invoice_number(body.get("invoice_prefix", "INV"))

            invoice = {
                "invoice_id": invoice_id,
                "invoice_number": body.get("invoice_number", invoice_number),
                "project_id": project_id,
                "customer_id": body.get("customer_id", ""),
                "customer_name": body.get("customer_name", ""),
                "entity_id": body.get("entity_id", ""),
                "invoice_date": body.get("invoice_date", date.today().isoformat()),
                "due_date": body.get("due_date", ""),
                "period_start": body.get("period_start", ""),
                "period_end": body.get("period_end", ""),
                "currency": body.get("currency", "JPY"),
                "subtotal": float(body.get("subtotal", 0) or 0),
                "tax_rate": body.get("tax_rate", "10%"),
                "tax_amount": float(body.get("tax_amount", 0) or 0),
                "total_amount": float(body.get("total_amount", 0) or 0),
                "status": "draft",
                "main_recipient_name": body.get("main_recipient_name", ""),
                "main_recipient_email": body.get("main_recipient_email", ""),
                "cc_recipients": body.get("cc_recipients", "[]"),
                "notes": body.get("notes", ""),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": session.get("user", {}).get("email", "system"),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            _db.insert_record("inv_invoices", invoice)

            # Save line items
            items = body.get("items", [])
            for i, item in enumerate(items):
                item_id = f"ITM-{uuid.uuid4().hex[:12].upper()}"
                _db.insert_record("inv_invoice_items", {
                    "item_id": item_id,
                    "invoice_id": invoice_id,
                    "description": item.get("description", ""),
                    "employee_id": item.get("employee_id", ""),
                    "employee_name": item.get("employee_name", ""),
                    "quantity": float(item.get("quantity", 1) or 1),
                    "unit_price": float(item.get("unit_price", 0) or 0),
                    "amount": float(item.get("amount", 0) or 0),
                    "tax_rate": item.get("tax_rate", ""),
                    "sort_order": item.get("sort_order", i),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })

            success(self, invoice)
        except Exception as e:
            error(self, f"Create invoice failed: {str(e)}", 500)

    def _update_invoice(self, session, invoice_id, body):
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        if not self._check_permission(session, "invoice.maintain"):
            error(self, "Forbidden", 403)
            return
        try:
            invoice = _db.load_table("inv_invoices", where={"invoice_id": invoice_id})
            if not invoice:
                error(self, "Invoice not found", 404)
                return
            if invoice[0].get("status") != "draft":
                error(self, "Only draft invoices can be updated", 400)
                return

            body["updated_at"] = datetime.now(timezone.utc).isoformat()
            body["updated_by"] = session.get("user", {}).get("email", "system")
            _db.update_record("inv_invoices", "invoice_id", invoice_id, body)
            success(self, {"invoice_id": invoice_id})
        except Exception as e:
            error(self, f"Update failed: {str(e)}", 500)

    def _submit_invoice(self, session, invoice_id, body):
        """Submit invoice for approval."""
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        if not self._check_permission(session, "invoice.maintain"):
            error(self, "Forbidden", 403)
            return
        try:
            _db.update_record("inv_invoices", "invoice_id", invoice_id, {
                "status": "pending_approval",
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "updated_by": session.get("user", {}).get("email", "system"),
            })

            # Create approval record
            _db.insert_record("inv_approval_records", {
                "approval_id": f"APR-{uuid.uuid4().hex[:12].upper()}",
                "invoice_id": invoice_id,
                "approver_user_id": "",
                "approver_name": session.get("user", {}).get("email", "system"),
                "action": "submitted",
                "comment": body.get("comment", ""),
                "acted_at": datetime.now(timezone.utc).isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

            # TODO: Send approval notification via messaging service
            success(self, {"invoice_id": invoice_id, "status": "pending_approval"})
        except Exception as e:
            error(self, f"Submit failed: {str(e)}", 500)

    # ── Flow 4: Approval & Sending ──
    def _approve_invoice(self, session, invoice_id, body):
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        if not self._check_permission(session, "invoice.approve"):
            error(self, "Forbidden", 403)
            return
        try:
            _db.update_record("inv_invoices", "invoice_id", invoice_id, {
                "status": "approved",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            _db.insert_record("inv_approval_records", {
                "approval_id": f"APR-{uuid.uuid4().hex[:12].upper()}",
                "invoice_id": invoice_id,
                "approver_user_id": session.get("user", {}).get("user_id", ""),
                "approver_name": session.get("user", {}).get("email", "system"),
                "action": "approved",
                "comment": body.get("comment", ""),
                "acted_at": datetime.now(timezone.utc).isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            success(self, {"invoice_id": invoice_id, "status": "approved"})
        except Exception as e:
            error(self, f"Approve failed: {str(e)}", 500)

    def _reject_invoice(self, session, invoice_id, body):
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        if not self._check_permission(session, "invoice.approve"):
            error(self, "Forbidden", 403)
            return
        try:
            _db.update_record("inv_invoices", "invoice_id", invoice_id, {
                "status": "draft",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            _db.insert_record("inv_approval_records", {
                "approval_id": f"APR-{uuid.uuid4().hex[:12].upper()}",
                "invoice_id": invoice_id,
                "approver_user_id": session.get("user", {}).get("user_id", ""),
                "approver_name": session.get("user", {}).get("email", "system"),
                "action": "rejected",
                "comment": body.get("comment", ""),
                "acted_at": datetime.now(timezone.utc).isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            success(self, {"invoice_id": invoice_id, "status": "rejected"})
        except Exception as e:
            error(self, f"Reject failed: {str(e)}", 500)

    def _send_invoice_email(self, session, invoice_id, body):
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        if not self._check_permission(session, "invoice.send"):
            error(self, "Forbidden", 403)
            return
        try:
            invoice = _db.load_table("inv_invoices", where={"invoice_id": invoice_id})
            if not invoice:
                error(self, "Invoice not found", 404)
                return
            inv = invoice[0]
            recipient = inv.get("main_recipient_email", "")

            # Log email
            log_id = f"EML-{uuid.uuid4().hex[:12].upper()}"
            _db.insert_record("inv_email_logs", {
                "log_id": log_id,
                "invoice_id": invoice_id,
                "recipient": recipient,
                "cc_recipients": inv.get("cc_recipients", "[]"),
                "email_type": "invoice",
                "status": "sent",
                "sent_at": datetime.now(timezone.utc).isoformat(),
                "attachment_file": f"invoice_{inv.get('invoice_number', invoice_id)}.html",
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

            # Update invoice status
            _db.update_record("inv_invoices", "invoice_id", invoice_id, {
                "status": "sent",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })

            # TODO: Actual email sending via masterdata SMTP or messaging service
            success(self, {"invoice_id": invoice_id, "status": "sent", "recipient": recipient})
        except Exception as e:
            error(self, f"Send email failed: {str(e)}", 500)

    def _list_email_logs(self, invoice_id):
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        try:
            logs = _db.load_table("inv_email_logs", where={"invoice_id": invoice_id}, order_by="created_at DESC")
            success(self, {"items": logs, "total": len(logs)})
        except Exception as e:
            error(self, f"Database error: {str(e)}", 500)

    def _list_approvals(self, invoice_id):
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        try:
            records = _db.load_table("inv_approval_records", where={"invoice_id": invoice_id}, order_by="created_at DESC")
            success(self, {"items": records, "total": len(records)})
        except Exception as e:
            error(self, f"Database error: {str(e)}", 500)

    # ── Flow 5: Payment & Reconciliation ──
    def _register_payment(self, session, invoice_id, body):
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        if not self._check_permission(session, "invoice.payment"):
            error(self, "Forbidden", 403)
            return
        try:
            payment_id = f"PAY-{uuid.uuid4().hex[:12].upper()}"
            payment = {
                "payment_id": payment_id,
                "invoice_id": invoice_id,
                "payment_date": body.get("payment_date", date.today().isoformat()),
                "amount": float(body.get("amount", 0) or 0),
                "currency": body.get("currency", "JPY"),
                "payment_method": body.get("payment_method", "bank_transfer"),
                "reference_number": body.get("reference_number", ""),
                "bank_name": body.get("bank_name", ""),
                "notes": body.get("notes", ""),
                "status": "confirmed",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": session.get("user", {}).get("email", "system"),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            _db.insert_record("inv_payments", payment)

            # Auto-reconcile
            self._reconcile_invoice(invoice_id)

            success(self, payment)
        except Exception as e:
            error(self, f"Register payment failed: {str(e)}", 500)

    def _list_payments(self, invoice_id):
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        try:
            payments = _db.load_table("inv_payments", where={"invoice_id": invoice_id}, order_by="payment_date DESC")
            success(self, {"items": payments, "total": len(payments)})
        except Exception as e:
            error(self, f"Database error: {str(e)}", 500)

    def _get_reconciliation(self, invoice_id):
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        try:
            recs = _db.load_table("inv_reconciliation", where={"invoice_id": invoice_id})
            if recs:
                success(self, recs[0])
            else:
                # Calculate on-the-fly
                result = self._reconcile_invoice(invoice_id)
                success(self, result)
        except Exception as e:
            error(self, f"Database error: {str(e)}", 500)

    def _reconcile(self, session, invoice_id):
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        try:
            result = self._reconcile_invoice(invoice_id)
            success(self, result)
        except Exception as e:
            error(self, f"Reconcile failed: {str(e)}", 500)

    def _reconcile_invoice(self, invoice_id) -> dict:
        """Calculate balance, status, overdue days."""
        invoices = _db.load_table("inv_invoices", where={"invoice_id": invoice_id})
        if not invoices:
            return {"invoice_id": invoice_id, "error": "Not found"}
        inv = invoices[0]
        invoice_total = float(inv.get("total_amount", 0) or 0)

        payments = _db.load_table("inv_payments", where={"invoice_id": invoice_id})
        total_paid = sum(float(p.get("amount", 0) or 0) for p in payments)
        balance = round(invoice_total - total_paid, 2)

        if balance <= 0:
            status = "overpaid" if balance < 0 else "paid"
        elif total_paid > 0:
            status = "partial"
        else:
            status = "unpaid"

        # Calculate overdue days
        due_date_str = inv.get("due_date", "")
        overdue_days = 0
        if due_date_str and balance > 0:
            try:
                due_date = date.fromisoformat(due_date_str)
                overdue_days = max(0, (date.today() - due_date).days)
            except ValueError:
                pass

        last_payment_date = ""
        if payments:
            last_payment_date = payments[0].get("payment_date", "")

        reconciliation = {
            "invoice_id": invoice_id,
            "invoice_total": invoice_total,
            "total_paid": total_paid,
            "balance": balance,
            "status": status,
            "last_payment_date": last_payment_date,
            "overdue_days": overdue_days,
        }

        # Upsert reconciliation record
        existing = _db.load_table("inv_reconciliation", where={"invoice_id": invoice_id})
        rec = {
            "reconciliation_id": existing[0]["reconciliation_id"] if existing else f"REC-{uuid.uuid4().hex[:12].upper()}",
            "invoice_id": invoice_id,
            "invoice_total": invoice_total,
            "total_paid": total_paid,
            "balance": balance,
            "status": status,
            "last_payment_date": last_payment_date,
            "overdue_days": overdue_days,
            "reconciled_at": datetime.now(timezone.utc).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if existing:
            _db.update_record("inv_reconciliation", "invoice_id", invoice_id, rec)
        else:
            _db.insert_record("inv_reconciliation", rec)

        # Update invoice status if fully paid
        if balance <= 0 and inv.get("status") not in ("paid", "cancelled"):
            _db.update_record("inv_invoices", "invoice_id", invoice_id, {
                "status": "paid",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })

        return reconciliation

    def _list_overdue(self):
        if not _PG_AVAILABLE:
            error(self, "Database not available", 503)
            return
        try:
            all_invoices = _db.load_table("inv_invoices", where={"status": "sent"}, order_by="due_date ASC")
            overdue = []
            today = date.today()
            for inv in all_invoices:
                due_str = inv.get("due_date", "")
                if not due_str:
                    continue
                try:
                    due_date = date.fromisoformat(due_str)
                    overdue_days = (today - due_date).days
                    if overdue_days > 0 and inv.get("status") not in ("paid", "cancelled"):
                        reconciliation = _db.load_table("inv_reconciliation", where={"invoice_id": inv.get("invoice_id")})
                        balance = reconciliation[0].get("balance", inv.get("total_amount", 0)) if reconciliation else inv.get("total_amount", 0)
                        if float(balance or 0) > 0:
                            inv["overdue_days"] = overdue_days
                            inv["balance"] = balance
                            overdue.append(inv)
                except ValueError:
                    pass
            success(self, {"items": overdue, "total": len(overdue)})
        except Exception as e:
            error(self, f"Database error: {str(e)}", 500)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[{MODULE_NAME}] {self.address_string()} - {format % args}", file=_sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="TACAI Invoice Management Service")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Bind port")
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), InvoiceHandler)
    print(f"[{MODULE_NAME}] Running on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(f"\n[{MODULE_NAME}] Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
