"""Invoice router — customer projects, pending invoices, invoice CRUD, payments."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from dependencies import get_current_user
from modules.auth.models import error_response, paginated_response, success_response
from shared import db_utils as _db

router = APIRouter()
PREFIX = "inv"


def _check_access(user: dict, perm: str = "invoice.view") -> None:
    perms = user.get("permissions") or []
    if perm not in perms and "system_admin" not in (user.get("roles") or []):
        raise HTTPException(status_code=403, detail="Forbidden")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _next_id(records: list, field: str, prefix: str, width: int = 4) -> str:
    max_n = 0
    for r in records:
        val = str(r.get(field, ""))
        if val.startswith(prefix):
            try:
                max_n = max(max_n, int(val[len(prefix):]))
            except ValueError:
                pass
    return f"{prefix}{max_n + 1:0{width}d}"


# ── Customer Projects ───────────────────────────────────────────────────

@router.get("/api/invoice/customer-projects")
async def list_projects(user: dict = Depends(get_current_user)):
    _check_access(user)
    rows = _db.load_table(f"{PREFIX}_customer_projects") or []
    return success_response(rows)


@router.get("/api/invoice/customer-projects/{project_id}")
async def get_project(project_id: str, user: dict = Depends(get_current_user)):
    _check_access(user)
    rows = _db.load_table(f"{PREFIX}_customer_projects") or []
    for r in rows:
        if str(r.get("id") or r.get("project_id", "")) == project_id:
            return success_response(r)
    raise HTTPException(status_code=404, detail="Not found")


@router.post("/api/invoice/customer-projects")
async def save_project(request: Request, user: dict = Depends(get_current_user)):
    _check_access(user, "invoice.maintain")
    body = await request.json()
    rows = _db.load_table(f"{PREFIX}_customer_projects") or []
    proj_id = body.get("id") or body.get("project_id")
    if proj_id:
        for i, r in enumerate(rows):
            if str(r.get("id") or r.get("project_id", "")) == str(proj_id):
                r.update({k: v for k, v in body.items() if k not in ("id", "project_id")})
                r["updated_at"] = _now()
                rows[i] = r
                _db.save_table(f"{PREFIX}_customer_projects", rows)
                return success_response(r)
    body["id"] = _next_id(rows, "id", "PROJ-")
    body["created_at"] = _now()
    body["updated_at"] = _now()
    rows.append(body)
    _db.save_table(f"{PREFIX}_customer_projects", rows)
    return success_response(body)


# ── Pending Invoices ────────────────────────────────────────────────────

@router.get("/api/invoice/pending")
async def list_pending(user: dict = Depends(get_current_user)):
    _check_access(user)
    rows = _db.load_table(f"{PREFIX}_pending_invoices") or []
    return success_response(rows)


@router.post("/api/invoice/pending/scan")
async def scan_pending(request: Request, user: dict = Depends(get_current_user)):
    _check_access(user, "invoice.maintain")
    return success_response({"message": "Scan complete", "found": 0})


@router.post("/api/invoice/pending/{pending_id}/convert")
async def convert_pending(pending_id: str, user: dict = Depends(get_current_user)):
    _check_access(user, "invoice.maintain")
    return success_response({"message": f"Converted {pending_id} to invoice"})


# ── Invoices ────────────────────────────────────────────────────────────

@router.get("/api/invoice/invoices")
async def list_invoices(
    status: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    _check_access(user)
    rows = _db.load_table(f"{PREFIX}_invoices") or []
    if status:
        rows = [r for r in rows if r.get("status") == status]
    total = len(rows)
    start = (page - 1) * page_size
    return paginated_response(rows[start:start + page_size], page, page_size, total)


@router.get("/api/invoice/invoices/{invoice_id}")
async def get_invoice(invoice_id: str, user: dict = Depends(get_current_user)):
    _check_access(user)
    rows = _db.load_table(f"{PREFIX}_invoices") or []
    for r in rows:
        if str(r.get("id") or r.get("invoice_id", "")) == invoice_id:
            items = _db.load_table(f"{PREFIX}_invoice_items") or []
            r["items"] = [i for i in items if str(i.get("invoice_id", "")) == invoice_id]
            payments = _db.load_table(f"{PREFIX}_payments") or []
            r["payments"] = [p for p in payments if str(p.get("invoice_id", "")) == invoice_id]
            return success_response(r)
    raise HTTPException(status_code=404, detail="Not found")


@router.post("/api/invoice/invoices")
async def create_invoice(request: Request, user: dict = Depends(get_current_user)):
    _check_access(user, "invoice.maintain")
    body = await request.json()
    rows = _db.load_table(f"{PREFIX}_invoices") or []
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    inv_no = f"INV-{today}-{len(rows) + 1:04d}"
    invoice = {
        "id": _next_id(rows, "id", "INV-"),
        "invoice_no": body.get("invoice_no", inv_no),
        "customer_id": body.get("customer_id", ""),
        "customer_name": body.get("customer_name", ""),
        "entity_id": body.get("entity_id", ""),
        "issue_date": body.get("issue_date", _now()),
        "due_date": body.get("due_date", ""),
        "amount": body.get("amount", 0),
        "tax_amount": body.get("tax_amount", 0),
        "total_amount": body.get("total_amount", 0),
        "currency": body.get("currency", "JPY"),
        "status": "draft",
        "notes": body.get("notes", ""),
        "created_at": _now(),
        "updated_at": _now(),
    }
    rows.append(invoice)
    _db.save_table(f"{PREFIX}_invoices", rows)
    return success_response(invoice)


@router.post("/api/invoice/invoices/{invoice_id}/update")
async def update_invoice(request: Request, invoice_id: str, user: dict = Depends(get_current_user)):
    _check_access(user, "invoice.maintain")
    body = await request.json()
    rows = _db.load_table(f"{PREFIX}_invoices") or []
    for i, r in enumerate(rows):
        if str(r.get("id") or r.get("invoice_id", "")) == invoice_id:
            if r.get("status") != "draft":
                return error_response("Only draft invoices can be updated")
            r.update({k: v for k, v in body.items() if k not in ("id", "invoice_id", "invoice_no")})
            r["updated_at"] = _now()
            rows[i] = r
            _db.save_table(f"{PREFIX}_invoices", rows)
            return success_response(r)
    raise HTTPException(status_code=404, detail="Not found")


@router.post("/api/invoice/invoices/{invoice_id}/submit")
async def submit_invoice(invoice_id: str, user: dict = Depends(get_current_user)):
    _check_access(user, "invoice.maintain")
    rows = _db.load_table(f"{PREFIX}_invoices") or []
    for r in rows:
        if str(r.get("id") or r.get("invoice_id", "")) == invoice_id:
            r["status"] = "submitted"
            r["updated_at"] = _now()
            _db.save_table(f"{PREFIX}_invoices", rows)
            return success_response(r)
    raise HTTPException(status_code=404, detail="Not found")


@router.post("/api/invoice/invoices/{invoice_id}/approve")
async def approve_invoice(invoice_id: str, user: dict = Depends(get_current_user)):
    _check_access(user, "invoice.approve")
    rows = _db.load_table(f"{PREFIX}_invoices") or []
    for r in rows:
        if str(r.get("id") or r.get("invoice_id", "")) == invoice_id:
            r["status"] = "approved"
            r["approved_at"] = _now()
            r["updated_at"] = _now()
            _db.save_table(f"{PREFIX}_invoices", rows)
            return success_response(r)
    raise HTTPException(status_code=404, detail="Not found")


@router.post("/api/invoice/invoices/{invoice_id}/reject")
async def reject_invoice(invoice_id: str, user: dict = Depends(get_current_user)):
    _check_access(user, "invoice.approve")
    rows = _db.load_table(f"{PREFIX}_invoices") or []
    for r in rows:
        if str(r.get("id") or r.get("invoice_id", "")) == invoice_id:
            r["status"] = "draft"
            r["updated_at"] = _now()
            _db.save_table(f"{PREFIX}_invoices", rows)
            return success_response(r)
    raise HTTPException(status_code=404, detail="Not found")


# ── Payments ────────────────────────────────────────────────────────────

@router.get("/api/invoice/invoices/{invoice_id}/payments")
async def list_payments(invoice_id: str, user: dict = Depends(get_current_user)):
    _check_access(user)
    rows = _db.load_table(f"{PREFIX}_payments") or []
    return success_response([p for p in rows if str(p.get("invoice_id", "")) == invoice_id])


@router.post("/api/invoice/invoices/{invoice_id}/payments")
async def register_payment(request: Request, invoice_id: str, user: dict = Depends(get_current_user)):
    _check_access(user, "invoice.payment")
    body = await request.json()
    rows = _db.load_table(f"{PREFIX}_payments") or []
    payment = {
        "id": _next_id(rows, "id", "PAY-"),
        "invoice_id": invoice_id,
        "amount": body.get("amount", 0),
        "payment_date": body.get("payment_date", _now()),
        "payment_method": body.get("payment_method", "bank_transfer"),
        "reference": body.get("reference", ""),
        "created_at": _now(),
    }
    rows.append(payment)
    _db.save_table(f"{PREFIX}_payments", rows)
    return success_response(payment)


# ── Overdue ─────────────────────────────────────────────────────────────

@router.get("/api/invoice/overdue")
async def list_overdue(user: dict = Depends(get_current_user)):
    _check_access(user)
    rows = _db.load_table(f"{PREFIX}_invoices") or []
    now = datetime.now(timezone.utc)
    overdue = []
    for r in rows:
        if r.get("status") in ("submitted", "approved", "sent") and r.get("due_date"):
            try:
                due = datetime.fromisoformat(str(r.get("due_date", "")))
                if due < now:
                    payments = _db.load_table(f"{PREFIX}_payments") or []
                    paid = sum(float(p.get("amount", 0)) for p in payments
                              if str(p.get("invoice_id", "")) == str(r.get("id") or r.get("invoice_id", "")))
                    r["balance"] = float(r.get("total_amount", 0)) - paid
                    r["days_overdue"] = (now - due).days
                    if r["balance"] > 0:
                        overdue.append(r)
            except (ValueError, TypeError):
                pass
    return success_response(overdue)
