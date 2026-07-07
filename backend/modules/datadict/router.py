"""Data Dictionary router — 2-level CRUD: categories + entries."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from dependencies import get_current_user
from modules.auth.models import error_response, paginated_response, success_response
from shared import db_utils as _db

router = APIRouter()
CAT_TABLE = "dd_category"
ENT_TABLE = "dd_data_dictionary"


def _require(user: dict):
    if "datadict.access" not in (user.get("permissions") or []) and "system_admin" not in (user.get("roles") or []):
        raise HTTPException(status_code=403, detail="Forbidden")


# ── Categories ───────────────────────────────────────────────────────────

@router.get("/api/data-dictionary/categories")
async def list_categories(user: dict = Depends(get_current_user)):
    _require(user)
    categories = _db.load_table(CAT_TABLE) or []
    entries = _db.load_table(ENT_TABLE) or []
    result = []
    for cat in categories:
        count = sum(1 for e in entries if str(e.get("category_id")) == str(cat.get("id")))
        result.append({**cat, "entry_count": count})
    return success_response(result)


@router.get("/api/data-dictionary/categories/{cat_id}")
async def get_category(cat_id: int, user: dict = Depends(get_current_user)):
    _require(user)
    cats = _db.load_table(CAT_TABLE) or []
    for c in cats:
        if c.get("id") == cat_id:
            entries = _db.load_table(ENT_TABLE) or []
            count = sum(1 for e in entries if str(e.get("category_id")) == str(cat_id))
            return success_response({**c, "entry_count": count})
    raise HTTPException(status_code=404, detail="Not found")


@router.post("/api/data-dictionary/categories")
async def create_category(request: Request, user: dict = Depends(get_current_user)):
    _require(user)
    body = await request.json()
    cats = _db.load_table(CAT_TABLE) or []
    new_id = max([c.get("id", 0) for c in cats], default=0) + 1
    cat = {"id": new_id, "category_code": body.get("category_code", ""),
           "labels": body.get("labels", {}), "display_order": body.get("display_order", 0),
           "is_active": body.get("is_active", True)}
    cats.append(cat)
    _db.save_table(CAT_TABLE, cats)
    return success_response(cat)


@router.post("/api/data-dictionary/categories/{cat_id}")
async def update_category(request: Request, cat_id: int, user: dict = Depends(get_current_user)):
    _require(user)
    body = await request.json()
    cats = _db.load_table(CAT_TABLE) or []
    for i, c in enumerate(cats):
        if c.get("id") == cat_id:
            c.update({k: v for k, v in body.items() if k != "id"})
            cats[i] = c
            _db.save_table(CAT_TABLE, cats)
            return success_response(c)
    raise HTTPException(status_code=404, detail="Not found")


@router.delete("/api/data-dictionary/categories/{cat_id}")
async def delete_category(cat_id: int, user: dict = Depends(get_current_user)):
    _require(user)
    cats = _db.load_table(CAT_TABLE) or []
    cats = [c for c in cats if c.get("id") != cat_id]
    _db.save_table(CAT_TABLE, cats)
    entries = _db.load_table(ENT_TABLE) or []
    entries = [e for e in entries if str(e.get("category_id")) != str(cat_id)]
    _db.save_table(ENT_TABLE, entries)
    return success_response({"message": "Deleted"})


# ── Entries ──────────────────────────────────────────────────────────────

@router.get("/api/data-dictionary/entries")
async def list_entries(
    category_id: Optional[int] = Query(default=None),
    q: Optional[str] = Query(default=None),
    show_inactive: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    user: dict = Depends(get_current_user),
):
    _require(user)
    entries = _db.load_table(ENT_TABLE) or []
    if category_id is not None:
        entries = [e for e in entries if str(e.get("category_id")) == str(category_id)]
    if not show_inactive:
        entries = [e for e in entries if e.get("is_active", True)]
    if q:
        ql = q.lower()
        entries = [e for e in entries if ql in str(e.get("labels", {})).lower() or ql in str(e.get("entry_code", "")).lower()]
    total = len(entries)
    start = (page - 1) * page_size
    return paginated_response(entries[start:start + page_size], page, page_size, total)


@router.get("/api/data-dictionary/entries/{entry_id}")
async def get_entry(entry_id: int, user: dict = Depends(get_current_user)):
    _require(user)
    entries = _db.load_table(ENT_TABLE) or []
    for e in entries:
        if e.get("id") == entry_id:
            return success_response(e)
    raise HTTPException(status_code=404, detail="Not found")


@router.post("/api/data-dictionary/entries")
async def create_entry(request: Request, user: dict = Depends(get_current_user)):
    _require(user)
    body = await request.json()
    entries = _db.load_table(ENT_TABLE) or []
    new_id = max([e.get("id", 0) for e in entries], default=0) + 1
    entry = {"id": new_id, "category_id": body.get("category_id"),
             "entry_code": body.get("entry_code", ""), "labels": body.get("labels", {}),
             "display_order": body.get("display_order", 0), "is_active": body.get("is_active", True)}
    entries.append(entry)
    _db.save_table(ENT_TABLE, entries)
    return success_response(entry)


@router.post("/api/data-dictionary/entries/{entry_id}")
async def update_entry(request: Request, entry_id: int, user: dict = Depends(get_current_user)):
    _require(user)
    body = await request.json()
    entries = _db.load_table(ENT_TABLE) or []
    for i, e in enumerate(entries):
        if e.get("id") == entry_id:
            e.update({k: v for k, v in body.items() if k != "id"})
            entries[i] = e
            _db.save_table(ENT_TABLE, entries)
            return success_response(e)
    raise HTTPException(status_code=404, detail="Not found")


@router.delete("/api/data-dictionary/entries/{entry_id}")
async def delete_entry(entry_id: int, user: dict = Depends(get_current_user)):
    _require(user)
    entries = _db.load_table(ENT_TABLE) or []
    entries = [e for e in entries if e.get("id") != entry_id]
    _db.save_table(ENT_TABLE, entries)
    return success_response({"message": "Deleted"})
