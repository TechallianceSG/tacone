#!/usr/bin/env python3
"""TACAI Data Dictionary — standalone JSON API service.

Provides CRUD API for dd_category and dd_data_dictionary (PostgreSQL).
2-level structure: categories (level 1) → entries (level 2).
Accessed via Portal API Gateway at /api/data-dictionary/* → port 8005.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys as _sys
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# ── Shared libraries (backend/shared/) ──
_shared_path = Path(__file__).resolve().parents[2] / 'shared'
if str(_shared_path) not in _sys.path:
    _sys.path.insert(0, str(_shared_path))
import db_utils as _db
from auth_utils import validate_session, has_permission, is_system_admin

MODULE_NAME = "tacai-datadict"
DEFAULT_PORT = 8005
CATEGORY_TABLE = "dd_category"
ENTRY_TABLE = "dd_data_dictionary"
REQUIRED_PERMISSION = "datadict.access"


class DataDictHandler(BaseHTTPRequestHandler):
    server_version = "TACAIDataDict/0.2"

    _CORS_ORIGINS = {
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:4173", "http://127.0.0.1:4173",
        "http://localhost:3000", "http://127.0.0.1:3000",
    }

    def add_cors(self) -> None:
        origin = self.headers.get("Origin", "")
        allowed = origin if origin in self._CORS_ORIGINS else "http://localhost:5173"
        self.send_header("Access-Control-Allow-Origin", allowed)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")
        self.send_header("Access-Control-Allow-Credentials", "true")

    def send_json(self, data: dict | list, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.add_cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, message: str, status: int = 400) -> None:
        self.send_json({"error": message}, status)

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return  # suppress default logging

    def _current_user(self) -> dict | None:
        return validate_session(self.headers.get("Cookie", ""))

    def _require_user(self) -> dict | None:
        user = self._current_user()
        if not user:
            self.send_error_json("Unauthorized — invalid or expired session", 401)
            return None
        if not has_permission(user, REQUIRED_PERMISSION) and not is_system_admin(user):
            self.send_error_json("Forbidden — insufficient permissions", 403)
            return None
        return user

    # ── HTTP routing ──

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self.add_cors()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        params = parse_qs(parsed.query, keep_blank_values=True)

        if path == "/health":
            self.send_json({"status": "ok", "module": MODULE_NAME})
            return

        user = self._require_user()
        if not user:
            return

        # ── Category routes ──
        m_cat_one = re.match(r"^/api/data-dictionary/categories/(\d+)$", path)
        if m_cat_one:
            self._handle_category_get_one(int(m_cat_one.group(1)))
            return

        if path == "/api/data-dictionary/categories":
            self._handle_categories_list(params)
            return

        # ── Entry routes ──
        m_ent_one = re.match(r"^/api/data-dictionary/entries/(\d+)$", path)
        if m_ent_one:
            self._handle_entry_get_one(int(m_ent_one.group(1)))
            return

        if path == "/api/data-dictionary/entries":
            self._handle_entries_list(params)
            return

        self.send_error_json("Not Found", 404)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        user = self._require_user()
        if not user:
            return

        length = int(self.headers.get("Content-Length", "0") or "0")
        body_raw = self.rfile.read(length) if length else b""
        try:
            body = json.loads(body_raw) if body_raw else {}
        except json.JSONDecodeError:
            self.send_error_json("Invalid JSON", 400)
            return

        # ── Category routes ──
        m_cat_one = re.match(r"^/api/data-dictionary/categories/(\d+)$", path)
        if m_cat_one:
            self._handle_category_update(int(m_cat_one.group(1)), body)
            return

        if path == "/api/data-dictionary/categories":
            self._handle_category_create(body)
            return

        # ── Entry routes ──
        m_ent_one = re.match(r"^/api/data-dictionary/entries/(\d+)$", path)
        if m_ent_one:
            self._handle_entry_update(int(m_ent_one.group(1)), body)
            return

        if path == "/api/data-dictionary/entries":
            self._handle_entry_create(body)
            return

        self.send_error_json("Not Found", 404)

    def do_DELETE(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        user = self._require_user()
        if not user:
            return

        # ── Category delete (cascade) ──
        m_cat_one = re.match(r"^/api/data-dictionary/categories/(\d+)$", path)
        if m_cat_one:
            self._handle_category_delete(int(m_cat_one.group(1)))
            return

        # ── Entry delete ──
        m_ent_one = re.match(r"^/api/data-dictionary/entries/(\d+)$", path)
        if m_ent_one:
            self._handle_entry_delete(int(m_ent_one.group(1)))
            return

        self.send_error_json("Not Found", 404)

    # ═══════════════════════════════════════════════════════════
    #  Category Handlers
    # ═══════════════════════════════════════════════════════════

    def _load_all_entries(self) -> list[dict]:
        """Load all entries once for entry_count computation."""
        try:
            return _db.load_table(ENTRY_TABLE)
        except Exception:
            return []

    def _get_entry_count(self, cat_id: int, all_entries: list[dict]) -> int:
        return sum(1 for e in all_entries if e.get("category_id") == cat_id)

    def _handle_categories_list(self, params: dict) -> None:
        """GET /api/data-dictionary/categories — flat list with entry_count."""
        try:
            all_cats = _db.load_table(CATEGORY_TABLE, order_by="display_order")
        except Exception as e:
            self.send_error_json(f"Database error: {e}", 500)
            return

        all_entries = self._load_all_entries()

        for cat in all_cats:
            cat["entry_count"] = self._get_entry_count(cat["id"], all_entries)

        self.send_json({
            "categories": all_cats,
        })

    def _handle_category_get_one(self, cat_id: int) -> None:
        """GET /api/data-dictionary/categories/{id} — single category with entry_count."""
        try:
            all_cats = _db.load_table(CATEGORY_TABLE)
        except Exception as e:
            self.send_error_json(f"Database error: {e}", 500)
            return

        for cat in all_cats:
            if cat.get("id") == cat_id:
                all_entries = self._load_all_entries()
                cat["entry_count"] = self._get_entry_count(cat_id, all_entries)
                self.send_json({"category": cat})
                return
        self.send_error_json("Category not found", 404)

    def _handle_category_create(self, body: dict) -> None:
        """POST /api/data-dictionary/categories — create a new category."""
        category_code = (body.get("category_code") or "").strip()
        if not category_code:
            self.send_error_json("category_code is required", 400)
            return

        now = datetime.now(timezone.utc).isoformat()
        labels = body.get("labels") or ""
        description = body.get("description") or ""
        # Handle legacy JSONB format (dict) → extract first value
        if isinstance(labels, dict):
            labels = next((v for v in labels.values() if v), "")
        if isinstance(description, dict):
            description = next((v for v in description.values() if v), "")

        record = {
            "category_code": category_code,
            "labels": labels,
            "description": description,
            "display_order": body.get("display_order", 0),
            "is_active": body.get("is_active", True),
            "created_at": now,
            "updated_at": now,
        }

        try:
            _db.insert_record(CATEGORY_TABLE, record)
        except Exception as e:
            self.send_error_json(f"Failed to create category: {e}", 500)
            return

        self.send_json({"category": record}, 201)

    def _handle_category_update(self, cat_id: int, body: dict) -> None:
        """POST /api/data-dictionary/categories/{id} — update a category.

        If is_active is set to False, cascades deactivation to all entries.
        """
        try:
            all_cats = _db.load_table(CATEGORY_TABLE)
        except Exception as e:
            self.send_error_json(f"Database error: {e}", 500)
            return

        target = None
        for cat in all_cats:
            if cat.get("id") == cat_id:
                target = cat
                break
        if target is None:
            self.send_error_json("Category not found", 404)
            return

        now = datetime.now(timezone.utc).isoformat()
        # Handle legacy dict format → string
        for k in ("labels", "description"):
            if k in body and isinstance(body[k], dict):
                body[k] = next((v for v in body[k].values() if v), "")
        for key in ("category_code", "labels", "description",
                     "display_order", "is_active"):
            if key in body:
                target[key] = body[key]
        target["updated_at"] = now

        try:
            _db.update_record(CATEGORY_TABLE, "id", cat_id, target)
        except Exception as e:
            self.send_error_json(f"Failed to update category: {e}", 500)
            return

        # Cascade: if deactivating category, deactivate all its entries
        if body.get("is_active") is False:
            try:
                all_entries = _db.load_table(ENTRY_TABLE)
                cascade_count = 0
                for entry in all_entries:
                    if entry.get("category_id") == cat_id and entry.get("is_active", True):
                        _db.update_record(ENTRY_TABLE, "id", entry["id"],
                                          {"is_active": False, "updated_at": now})
                        cascade_count += 1
                target["_cascaded_entries"] = cascade_count
            except Exception:
                pass  # cascade failure is non-fatal

        self.send_json({"category": target})

    def _handle_category_delete(self, cat_id: int) -> None:
        """DELETE /api/data-dictionary/categories/{id} — permanent delete with cascade."""
        try:
            all_cats = _db.load_table(CATEGORY_TABLE)
        except Exception as e:
            self.send_error_json(f"Database error: {e}", 500)
            return

        found = any(cat.get("id") == cat_id for cat in all_cats)
        if not found:
            self.send_error_json("Category not found", 404)
            return

        # Cascade-delete all entries in this category
        deleted_entries = 0
        try:
            all_entries = _db.load_table(ENTRY_TABLE)
            for entry in all_entries:
                if entry.get("category_id") == cat_id:
                    _db.delete_record(ENTRY_TABLE, "id", entry["id"])
                    deleted_entries += 1
        except Exception as e:
            self.send_error_json(f"Failed to delete entries: {e}", 500)
            return

        # Delete the category itself
        try:
            _db.delete_record(CATEGORY_TABLE, "id", cat_id)
        except Exception as e:
            self.send_error_json(f"Failed to delete category: {e}", 500)
            return

        self.send_json({
            "success": True,
            "message": f"Category {cat_id} and {deleted_entries} entries deleted",
        })

    # ═══════════════════════════════════════════════════════════
    #  Entry Handlers
    # ═══════════════════════════════════════════════════════════

    def _handle_entries_list(self, params: dict) -> None:
        """GET /api/data-dictionary/entries — list with filters & pagination."""
        try:
            all_rows = _db.load_table(ENTRY_TABLE, order_by="category_id, display_order")
        except Exception as e:
            self.send_error_json(f"Database error: {e}", 500)
            return

        total_all = len(all_rows)

        # ── Filters ──
        cat_id_str = (params.get("category_id", [""])[0] or "").strip()
        q = (params.get("q", [""])[0] or "").strip().lower()
        show_inactive = (params.get("show_inactive", [""])[0] or "").strip() == "1"

        filtered = []
        for row in all_rows:
            if not show_inactive and not row.get("is_active", True):
                continue
            if cat_id_str:
                try:
                    if row.get("category_id") != int(cat_id_str):
                        continue
                except ValueError:
                    continue
            if q:
                labels_str = json.dumps(row.get("labels", {}), ensure_ascii=False).lower()
                search_text = f"{row.get('entry_code', '')} {labels_str}".lower()
                if q not in search_text:
                    continue
            filtered.append(row)

        total_filtered = len(filtered)

        # ── Pagination ──
        try:
            page = int(params.get("page", ["1"])[0])
        except (ValueError, IndexError):
            page = 1
        try:
            page_size = int(params.get("page_size", ["20"])[0])
        except (ValueError, IndexError):
            page_size = 20
        page = max(1, page)
        page_size = max(1, min(100, page_size))
        start = (page - 1) * page_size
        paged = filtered[start:start + page_size]

        self.send_json({
            "items": paged,
            "total": total_filtered,
            "total_all": total_all,
            "page": page,
            "page_size": page_size,
        })

    def _handle_entry_get_one(self, entry_id: int) -> None:
        """GET /api/data-dictionary/entries/{id} — single entry."""
        try:
            all_rows = _db.load_table(ENTRY_TABLE)
        except Exception as e:
            self.send_error_json(f"Database error: {e}", 500)
            return
        for row in all_rows:
            if row.get("id") == entry_id:
                self.send_json({"entry": row})
                return
        self.send_error_json("Entry not found", 404)

    def _handle_entry_create(self, body: dict) -> None:
        """POST /api/data-dictionary/entries — create entry."""
        category_id = body.get("category_id")
        entry_code = (body.get("entry_code") or "").strip()

        if not category_id:
            self.send_error_json("category_id is required", 400)
            return
        if not entry_code:
            self.send_error_json("entry_code is required", 400)
            return

        # Validate category exists
        try:
            all_cats = _db.load_table(CATEGORY_TABLE)
        except Exception as e:
            self.send_error_json(f"Database error: {e}", 500)
            return
        if not any(c.get("id") == category_id for c in all_cats):
            self.send_error_json(f"Category with id {category_id} not found", 400)
            return

        now = datetime.now(timezone.utc).isoformat()
        labels = body.get("labels") or ""
        if isinstance(labels, dict):
            labels = next((v for v in labels.values() if v), "")
        record = {
            "category_id": category_id,
            "entry_code": entry_code,
            "labels": labels,
            "display_order": body.get("display_order", 0),
            "is_active": body.get("is_active", True),
            "created_at": now,
            "updated_at": now,
        }

        try:
            _db.insert_record(ENTRY_TABLE, record)
        except Exception as e:
            self.send_error_json(f"Failed to create entry: {e}", 500)
            return

        self.send_json({"entry": record}, 201)

    def _handle_entry_update(self, entry_id: int, body: dict) -> None:
        """POST /api/data-dictionary/entries/{id} — update entry."""
        try:
            all_rows = _db.load_table(ENTRY_TABLE)
        except Exception as e:
            self.send_error_json(f"Database error: {e}", 500)
            return

        target = None
        for row in all_rows:
            if row.get("id") == entry_id:
                target = row
                break
        if target is None:
            self.send_error_json("Entry not found", 404)
            return

        # If category_id is being changed, validate new category exists
        if "category_id" in body:
            try:
                all_cats = _db.load_table(CATEGORY_TABLE)
            except Exception as e:
                self.send_error_json(f"Database error: {e}", 500)
                return
            if not any(c.get("id") == body["category_id"] for c in all_cats):
                self.send_error_json(f"Category with id {body['category_id']} not found", 400)
                return

        now = datetime.now(timezone.utc).isoformat()
        # Handle legacy dict format → string
        if "labels" in body and isinstance(body["labels"], dict):
            body["labels"] = next((v for v in body["labels"].values() if v), "")
        for key in ("category_id", "entry_code", "labels", "display_order",
                     "is_active"):
            if key in body:
                target[key] = body[key]
        target["updated_at"] = now

        try:
            _db.update_record(ENTRY_TABLE, "id", entry_id, target)
        except Exception as e:
            self.send_error_json(f"Failed to update entry: {e}", 500)
            return

        self.send_json({"entry": target})

    def _handle_entry_delete(self, entry_id: int) -> None:
        """DELETE /api/data-dictionary/entries/{id} — permanent delete."""
        try:
            all_rows = _db.load_table(ENTRY_TABLE)
        except Exception as e:
            self.send_error_json(f"Database error: {e}", 500)
            return

        for row in all_rows:
            if row.get("id") == entry_id:
                break
        else:
            self.send_error_json("Entry not found", 404)
            return

        try:
            _db.delete_record(ENTRY_TABLE, "id", entry_id)
        except Exception as e:
            self.send_error_json(f"Failed to delete entry: {e}", 500)
            return

        self.send_json({"success": True, "message": f"Entry {entry_id} deleted"})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TACAI Data Dictionary")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", str(DEFAULT_PORT))))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), DataDictHandler)
    print(f"TACAI Data Dictionary running on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping TACAI Data Dictionary")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
