"""Messaging router — inbox, workflows, delegations, notifications."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from dependencies import get_current_user
from modules.auth.models import error_response, paginated_response, success_response
from shared import db_utils as _db

router = APIRouter()
PREFIX = "msg"


def _check_access(user: dict, perm: str = "tacaimsg.view") -> None:
    perms = user.get("permissions") or []
    if perm not in perms and "system_admin" not in (user.get("roles") or []):
        raise HTTPException(status_code=403, detail="Forbidden")


# ── Internal API ─────────────────────────────────────────────────────────

@router.get("/api/internal/messages/unread-count")
async def internal_unread_count(user_id: Optional[str] = Query(default=None)):
    """Return unread message count for a user (used by dashboard)."""
    try:
        rows = _db.load_table(f"{PREFIX}_messages") or []
        if user_id:
            count = sum(1 for r in rows if r.get("recipient_user_id") == user_id and not r.get("read", False))
        else:
            count = sum(1 for r in rows if not r.get("read", False))
        return {"unread_count": count}
    except Exception:
        return {"unread_count": 0}


# ── Inbox ────────────────────────────────────────────────────────────────

@router.get("/api/v1/messages/inbox")
async def inbox(
    msg_type: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    keyword: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    """Get message inbox for current user."""
    _check_access(user)
    try:
        rows = _db.load_table(f"{PREFIX}_messages") or []
    except Exception:
        rows = []
    user_id = str(user.get("user_id", ""))
    rows = [r for r in rows if r.get("recipient_user_id") == user_id]
    if msg_type:
        rows = [r for r in rows if r.get("msg_type") == msg_type]
    if status:
        rows = [r for r in rows if r.get("status") == status]
    if keyword:
        kw = keyword.lower()
        rows = [r for r in rows if kw in str(r.get("title", "")).lower() or kw in str(r.get("content", "")).lower()]
    rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    total = len(rows)
    start = (page - 1) * page_size
    return paginated_response(rows[start:start + page_size], page, page_size, total)


@router.get("/api/v1/messages/{msg_id}")
async def get_message(msg_id: str, user: dict = Depends(get_current_user)):
    _check_access(user)
    try:
        rows = _db.load_table(f"{PREFIX}_messages", where={"id": msg_id})
    except Exception:
        raise HTTPException(status_code=500, detail="Database error")
    if not rows:
        raise HTTPException(status_code=404, detail="Not found")
    msg = rows[0]
    # Auto-mark as read
    if not msg.get("read"):
        from datetime import datetime, timezone
        msg["read"] = True
        msg["read_at"] = datetime.now(timezone.utc).isoformat()
        _db.update_record(f"{PREFIX}_messages", "id", msg_id, msg)
    return success_response(msg)


@router.post("/api/v1/messages/{msg_id}/read")
async def mark_read(msg_id: str, user: dict = Depends(get_current_user)):
    _check_access(user)
    from datetime import datetime, timezone
    try:
        timestamp = datetime.now(timezone.utc).isoformat()
        _db.update_record(f"{PREFIX}_messages", "id", msg_id, {"read": True, "read_at": timestamp})
    except Exception:
        raise HTTPException(status_code=500, detail="Database error")
    return success_response({"message": "Marked as read"})


@router.post("/api/v1/messages/read-all")
async def mark_all_read(request: Request, user: dict = Depends(get_current_user)):
    """Mark all messages as read for current user."""
    _check_access(user)
    user_id = str(user.get("user_id", ""))
    from datetime import datetime, timezone
    timestamp = datetime.now(timezone.utc).isoformat()
    try:
        rows = _db.load_table(f"{PREFIX}_messages") or []
        count = 0
        for r in rows:
            if r.get("recipient_user_id") == user_id and not r.get("read"):
                r["read"] = True
                r["read_at"] = timestamp
                count += 1
        _db.save_table(f"{PREFIX}_messages", rows)
        return success_response({"marked": count})
    except Exception:
        raise HTTPException(status_code=500, detail="Database error")


# ── Workflows ────────────────────────────────────────────────────────────

@router.get("/api/workflows")
async def list_workflows(
    status: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    """List workflows."""
    _check_access(user, "tacaimsg.workflow")
    try:
        rows = _db.load_table(f"{PREFIX}_workflows") or []
    except Exception:
        rows = []
    if status:
        rows = [r for r in rows if r.get("status") == status]
    rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    total = len(rows)
    start = (page - 1) * page_size
    return paginated_response(rows[start:start + page_size], page, page_size, total)


# ── Delegations ──────────────────────────────────────────────────────────

@router.get("/api/delegations")
async def list_delegations(user: dict = Depends(get_current_user)):
    _check_access(user, "tacaimsg.delegate")
    try:
        rows = _db.load_table(f"{PREFIX}_delegations") or []
    except Exception:
        rows = []
    return success_response(rows)


# ── Health ───────────────────────────────────────────────────────────────

@router.get("/api/messages/health")
async def messages_health():
    return {"status": "ok", "module": "tacai-messaging"}
