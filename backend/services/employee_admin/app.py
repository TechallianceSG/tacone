#!/usr/bin/env python3
"""TACAI Employee Admin — local web app.

Provides CRUD API for emp_employees (PostgreSQL).
Accessed via Portal API Gateway at /api/employees/* → port 8004.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys as _sys
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

# ── Shared libraries (backend/shared/) ──
_shared_path = Path(__file__).resolve().parents[2] / 'shared'
if str(_shared_path) not in _sys.path:
    _sys.path.insert(0, str(_shared_path))
import db_utils as _db
from auth_utils import validate_session, has_permission, is_system_admin
from cors_middleware import add_cors_headers, handle_preflight
from api_utils import send_json, success, error, paginated
from config import internal_url

MODULE_NAME = "tacai-employee-admin"
DEFAULT_PORT = 8004
REQUIRED_PERMISSION = "employee_management.access"

# ── Cross-service data access with TTL caching ──
# Calls masterdata's internal (no-auth, localhost-only) endpoints instead of
# reading md_entities/md_departments/md_teams directly from the database.

_CROSS_SERVICE_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_CROSS_SERVICE_CACHE_TTL = 60  # seconds


def _cached_masterdata(endpoint: str) -> list[dict[str, Any]]:
    """Call a masterdata internal API endpoint with TTL caching."""
    import time as _time
    now = _time.monotonic()
    entry = _CROSS_SERVICE_CACHE.get(endpoint)
    if entry is not None:
        ts, data = entry
        if now - ts < _CROSS_SERVICE_CACHE_TTL:
            return data
    try:
        req = Request(
            internal_url("masterdata", endpoint),
            headers={"Accept": "application/json"},
            method="GET",
        )
        with urlopen(req, timeout=3) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        data = body.get("entities") or body.get("departments") or body.get("teams") or []
    except Exception:
        if entry is not None:
            return entry[1]  # Graceful degradation: return stale cache
        return []
    _CROSS_SERVICE_CACHE[endpoint] = (now, data)
    return data


def _resolve_entity_labels(employees: list) -> list:
    """Enrich employee records with entity labels from masterdata internal API."""
    entities = _cached_masterdata("/api/internal/entities/active")
    if not entities:
        return employees
    entity_map = {e.get("entity_id", ""): e for e in entities}
    for emp in employees:
        emp_data = emp.get("employment") or {}
        eid = emp_data.get("entity_id", "")
        ent = entity_map.get(eid, {})
        if ent:
            emp_data["entity_code"] = ent.get("entity_code", "")
            emp_data["entity_name"] = ent.get("entity_name_en", "") or ent.get("entity_name_zh", "") or ent.get("entity_name_ja", "")
    return employees


def _resolve_org_labels(employees: list) -> list:
    """Enrich employee records with department & team labels from masterdata internal API."""
    departments = _cached_masterdata("/api/internal/departments")
    teams = _cached_masterdata("/api/internal/teams")
    if not departments and not teams:
        return employees
    dept_map = {d.get("department_id", ""): d for d in departments}
    team_map = {t.get("team_id", ""): t for t in teams}
    for emp in employees:
        emp_data = emp.get("employment") or {}
        did = emp_data.get("department_id", "")
        dept = dept_map.get(did, {})
        if dept:
            emp_data["department_code"] = dept.get("department_code", "")
            emp_data["department_name"] = dept.get("department_name_en", "") or dept.get("department_name_zh", "") or dept.get("department_name_ja", "")
        tid = emp_data.get("team_id", "")
        team = team_map.get(tid, {})
        if team:
            emp_data["team_code"] = team.get("team_code", "")
            emp_data["team_name"] = team.get("team_name_en", "") or team.get("team_name_zh", "") or team.get("team_name_ja", "")
    return employees


class EmployeeAdminHandler(BaseHTTPRequestHandler):
    server_version = "TACAIEmployeeAdmin/0.1"

    # Response helpers from api_utils (standard format)
    # send_json, success, error, paginated are imported as module-level functions

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return  # suppress default logging

    def _current_user(self) -> dict | None:
        return validate_session(self.headers.get("Cookie", ""))

    def _require_user(self) -> dict | None:
        """Validate session and check permission. Returns user or sends 401/403."""
        user = self._current_user()
        if not user:
            error(self, "Unauthorized", 401)
            return None
        if not has_permission(user, REQUIRED_PERMISSION) and not is_system_admin(user):
            error(self, "Forbidden — insufficient permissions", 403)
            return None
        return user

    # ── API Routing ──

    def do_OPTIONS(self) -> None:  # noqa: N802
        handle_preflight(self)

    def _is_localhost(self) -> bool:
        client = (self.client_address[0] if self.client_address else "")
        return client in ("127.0.0.1", "::1", "localhost")

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        params = parse_qs(parsed.query, keep_blank_values=True)

        # Health check (no auth required)
        if path == "/health":
            send_json(self, {"success": True, "status": "ok", "module": MODULE_NAME})
            return

        # ── Internal API endpoints (no auth, localhost-only) ──
        if self._is_localhost() and path.startswith("/api/internal/employees"):
            self._handle_internal_employee_api(path, params)
            return

        # All employee routes require auth
        user = self._require_user()
        if not user:
            return

        # GET /api/employees — list with pagination & filters
        if path == "/api/employees" or path == "/api/employees/":
            self._handle_list(params)
            return

        # GET /api/employees/{employee_id} — single employee
        m = re.match(r"^/api/employees/([A-Za-z0-9_-]+)$", path)
        if m:
            self._handle_get_one(m.group(1))
            return

        error(self, "Not Found", 404)

    def _handle_internal_employee_api(self, path: str, params: dict) -> None:
        """Handle internal API calls from other TACAI services (no auth).

        Endpoints:
          GET /api/internal/employees
              ?employee_ids=ID1,ID2,...   — batch lookup (comma-separated)
              ?employee_number=PREFIX     — search by employee number prefix
              ?include_payroll=true       — include payroll JSONB sub-object
              (no params)                 — return all employees

          GET /api/internal/employees/{employee_id}
              ?include_payroll=true       — include payroll JSONB sub-object
        """
        import re as _re

        include_payroll = params.get("include_payroll", ["false"])[0].lower() == "true"

        # GET /api/internal/employees?employee_ids=...&employee_number=...
        if path == "/api/internal/employees":
            ids_param = params.get("employee_ids", [""])[0]
            enum = params.get("employee_number", [""])[0]
            try:
                rows = _db.load_table("emp_employees")
            except Exception:
                error(self, "Database unavailable", 500)
                return

            # Batch filter by IDs
            if ids_param:
                id_set = set(i.strip() for i in ids_param.split(",") if i.strip())
                rows = [r for r in rows if str(r.get("employee_id", "")) in id_set]

            # Filter by employee number prefix
            if enum:
                rows = [r for r in rows if str(r.get("employee_number", "")).startswith(enum)]

            # Strip payroll field unless explicitly requested (reduces payload for most callers)
            if not include_payroll:
                for r in rows:
                    r.pop("payroll", None)

            success(self, {"employees": rows})
            return

        # GET /api/internal/employees/{employee_id}
        m = _re.match(r"^/api/internal/employees/([A-Za-z0-9_-]+)$", path)
        if m:
            eid = m.group(1)
            try:
                rows = _db.load_table("emp_employees", where={"employee_id": eid})
            except Exception:
                error(self, "Database unavailable", 500)
                return
            if rows:
                emp = rows[0]
                if not include_payroll:
                    emp.pop("payroll", None)
                success(self, {"employee": emp})
            else:
                error(self, "Not found", 404)
            return

        error(self, "Internal endpoint not found", 404)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        # All employee routes require auth
        user = self._require_user()
        if not user:
            return

        length = int(self.headers.get("Content-Length", "0") or "0")
        body_raw = self.rfile.read(length) if length else b""
        try:
            body = json.loads(body_raw) if body_raw else {}
        except json.JSONDecodeError:
            error(self, "Invalid JSON", 400)
            return

        # POST /api/employees — create
        if path == "/api/employees" or path == "/api/employees/":
            self._handle_create(body)
            return

        # POST /api/employees/{employee_id} — update
        m = re.match(r"^/api/employees/([A-Za-z0-9_-]+)$", path)
        if m:
            self._handle_update(m.group(1), body)
            return

        error(self, "Not Found", 404)

    def do_DELETE(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        # All employee routes require auth
        user = self._require_user()
        if not user:
            return

        # DELETE /api/employees/{employee_id} — soft delete
        m = re.match(r"^/api/employees/([A-Za-z0-9_-]+)$", path)
        if m:
            self._handle_delete(m.group(1))
            return

        error(self, "Not Found", 404)

    # ── Handlers ──

    def _handle_list(self, params: dict) -> None:
        try:
            all_rows = _db.load_table("emp_employees")
        except Exception as e:
            error(self, f"Database error: {e}", 500)
            return

        # Exclude soft-deleted
        all_rows = [r for r in all_rows if not (r.get("metadata") or {}).get("deleted", False)]
        total_all = len(all_rows)

        # ── Filters ──
        q = (params.get("q", [""])[0] or "").strip().lower()
        entity_id = (params.get("entity_id", [""])[0] or "").strip()
        country_code = (params.get("country_code", [""])[0] or "").strip()
        department_id = (params.get("department_id", [""])[0] or "").strip()
        team_id = (params.get("team_id", [""])[0] or "").strip()
        status = (params.get("status", [""])[0] or "").strip()
        show_resigned = (params.get("show_resigned", [""])[0] or "").strip() == "1"
        employment_type = (params.get("employment_type", [""])[0] or "").strip()
        japanese_level = (params.get("japanese_level", [""])[0] or "").strip()
        english_level = (params.get("english_level", [""])[0] or "").strip()
        skill = (params.get("skill", [""])[0] or "").strip().lower()

        filtered_rows = []
        for emp in all_rows:
            profile = emp.get("profile") or {}
            employment = emp.get("employment") or {}
            language = emp.get("language_profile") or {}
            skills = emp.get("skills_profile") or {}

            # Text search: name, email, employee_number, employee_id
            if q:
                name = (profile.get("name") or {}).get("display_name", "") or ""
                given = (profile.get("name") or {}).get("given_name", "") or ""
                family = (profile.get("name") or {}).get("family_name", "") or ""
                romaji = (profile.get("name") or {}).get("romaji_name", "") or ""
                email = profile.get("email", "") or ""
                emp_no = (emp.get("employee_number") or "").lower()
                emp_id = (emp.get("employee_id") or "").lower()
                search_text = f"{name} {given} {family} {romaji} {email} {emp_no} {emp_id}".lower()
                if q not in search_text:
                    continue

            # Entity filter (exact match)
            if entity_id and employment.get("entity_id", "") != entity_id:
                continue

            # Country filter — via entity's country from md_entities
            if country_code:
                emp_entity_id = employment.get("entity_id", "")
                # Resolve via entity code prefix: ENT-0001 = TAKK (JP), ENT-0002 = TASG (SG), etc.
                # For now, check entity_code prefix or country
                entity_country = _get_entity_country(emp_entity_id)
                if entity_country and entity_country != country_code:
                    continue

            # Department filter
            if department_id and employment.get("department_id", "") != department_id:
                continue

            # Team filter
            if team_id and employment.get("team_id", "") != team_id:
                continue

            # Status filter
            emp_status = (employment.get("status") or "").lower()
            if status and emp_status != status.lower():
                continue

            # Resigned filter
            if not show_resigned and emp_status == "resigned":
                continue

            # Employment type
            if employment_type:
                emp_type = employment.get("employment_type", "") or (employment.get("contract") or {}).get("employment_type", "") or ""
                if emp_type.lower() != employment_type.lower():
                    continue

            # Japanese level
            if japanese_level:
                jp = (language.get("japanese_level") or "").upper()
                if jp != japanese_level.upper():
                    continue

            # English level
            if english_level:
                en = (language.get("english_level") or "").lower()
                if en != english_level.lower():
                    continue

            # Skill search
            if skill:
                primary = (skills.get("primary_skill") or "").lower()
                secondary = (skills.get("secondary_skill") or "").lower()
                it_skills = " ".join(skills.get("it_skills") or []).lower()
                eng_skills = " ".join(skills.get("engineering_skills") or []).lower()
                all_skills = f"{primary} {secondary} {it_skills} {eng_skills}"
                if skill not in all_skills:
                    continue

            filtered_rows.append(emp)

        is_filtered = bool(q or entity_id or country_code or department_id or team_id or status or employment_type or japanese_level or english_level or skill)
        total_filtered = len(filtered_rows)

        # ── Pagination ──
        try:
            page = int(params.get("page", ["1"])[0])
        except ValueError:
            page = 1
        try:
            page_size = int(params.get("page_size", ["20"])[0])
        except ValueError:
            page_size = 20
        page = max(1, page)
        page_size = max(1, min(100, page_size))
        start = (page - 1) * page_size
        paged = filtered_rows[start:start + page_size]

        # Enrich with entity, department, and team labels
        paged = _resolve_entity_labels(paged)
        paged = _resolve_org_labels(paged)

        paginated(self, paged, page, page_size, total_filtered, total_all, is_filtered)

    def _handle_get_one(self, employee_id: str) -> None:
        try:
            all_rows = _db.load_table("emp_employees")
        except Exception as e:
            error(self, f"Database error: {e}", 500)
            return

        for emp in all_rows:
            if emp.get("employee_id") == employee_id:
                enriched = _resolve_entity_labels([emp])
                enriched = _resolve_org_labels(enriched)
                success(self, enriched[0])
                return

        error(self, "Employee not found", 404)

    @staticmethod
    def _unflatten_body(body: dict) -> dict:
        """Convert flat dot-notation keys to nested dicts.

        "profile.name.display_name" → {"profile": {"name": {"display_name": ...}}}
        Keys without dots pass through unchanged.
        """
        result: dict = {}
        for key, value in body.items():
            if '.' not in key:
                if isinstance(value, dict) and isinstance(result.get(key), dict):
                    result[key] = {**result[key], **value}
                else:
                    result[key] = value
            else:
                parts = key.split('.')
                cur = result
                for part in parts[:-1]:
                    if part not in cur:
                        cur[part] = {}
                    cur = cur[part]
                cur[parts[-1]] = value
        return result

    def _handle_create(self, body: dict) -> None:
        body = self._unflatten_body(body)
        import secrets
        try:
            all_rows = _db.load_table("emp_employees")
        except Exception as e:
            error(self, f"Database error: {e}", 500)
            return

        # Generate employee_id
        existing_ids = [r.get("employee_id", "") for r in all_rows]
        max_num = 0
        for eid in existing_ids:
            m = re.match(r"^EMP-(\d+)$", eid)
            if m:
                max_num = max(max_num, int(m.group(1)))
        new_id = f"EMP-{max_num + 1:04d}"

        now = _db._now_iso() if hasattr(_db, '_now_iso') else __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()

        new_emp = {
            "employee_id": new_id,
            "employee_number": body.get("employee_number") or new_id,
            "profile": body.get("profile", {}),
            "employment": body.get("employment", {}),
            "payroll": body.get("payroll", {}),
            "visa": body.get("visa", {}),
            "dispatch_compliance": body.get("dispatch_compliance", {}),
            "language_profile": body.get("language_profile", {}),
            "skills_profile": body.get("skills_profile", {}),
            "documents": body.get("documents"),
            "employment_history": body.get("employment_history"),
            "visa_history": body.get("visa_history"),
            "dispatch_assignment_history": body.get("dispatch_assignment_history"),
            "metadata": {
                "deleted": False,
                "created_at": now,
                "created_by": body.get("created_by", "admin"),
                "updated_at": now,
            },
        }

        _db.insert_record("emp_employees", new_emp)
        enriched = _resolve_entity_labels([new_emp])
        enriched = _resolve_org_labels(enriched)
        success(self, enriched[0], 201)

    def _handle_update(self, employee_id: str, body: dict) -> None:
        """Update an existing employee record (partial update)."""
        body = self._unflatten_body(body)
        try:
            all_rows = _db.load_table("emp_employees")
        except Exception as e:
            error(self, f"Database error: {e}", 500)
            return

        target = None
        for emp in all_rows:
            if emp.get("employee_id") == employee_id:
                target = emp
                break

        if target is None:
            error(self, "Employee not found", 404)
            return

        if (target.get("metadata") or {}).get("deleted", False):
            error(self, "Cannot update a deleted employee", 409)
            return

        now = __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()

        # Merge updates into existing record (shallow merge for top-level keys,
        # deep merge for nested dicts)
        for key, value in body.items():
            if key == "employee_id":
                continue  # never change the primary key
            if isinstance(value, dict) and isinstance(target.get(key), dict):
                # Deep merge nested objects
                target[key] = {**target[key], **value}
            else:
                target[key] = value

        # Update metadata timestamp
        metadata = target.get("metadata") or {}
        metadata["updated_at"] = now
        target["metadata"] = metadata

        try:
            _db.update_record("emp_employees", "employee_id", employee_id, target)
        except Exception as e:
            error(self, f"Failed to update: {e}", 500)
            return

        enriched = _resolve_entity_labels([target])
        enriched = _resolve_org_labels(enriched)
        success(self, enriched[0])

    def _handle_delete(self, employee_id: str) -> None:
        """Soft-delete an employee by setting metadata.deleted=true."""
        try:
            all_rows = _db.load_table("emp_employees")
        except Exception as e:
            error(self, f"Database error: {e}", 500)
            return

        target = None
        for emp in all_rows:
            if emp.get("employee_id") == employee_id:
                target = emp
                break

        if target is None:
            error(self, "Employee not found", 404)
            return

        if (target.get("metadata") or {}).get("deleted", False):
            error(self, "Employee already deleted", 409)
            return

        now = __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()
        metadata = target.get("metadata") or {}
        metadata["deleted"] = True
        metadata["updated_at"] = now

        try:
            _db.update_record("emp_employees", "employee_id", employee_id, {"metadata": metadata})
        except Exception as e:
            error(self, f"Failed to delete: {e}", 500)
            return

        success(self, {"message": f"Employee {employee_id} deleted"})


# ── Module-level cache for entity country lookup ──
_entity_country_cache: dict | None = None


def _get_entity_country(entity_id: str) -> str:
    global _entity_country_cache
    if _entity_country_cache is None:
        try:
            entities = _cached_masterdata("/api/internal/entities/active")
            _entity_country_cache = {
                e.get("entity_id", ""): (e.get("country") or "").upper()
                for e in entities
            }
        except Exception:
            _entity_country_cache = {}
    return _entity_country_cache.get(entity_id, "")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TACAI Employee Admin")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", str(DEFAULT_PORT))))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), EmployeeAdminHandler)
    print(f"TACAI Employee Admin running on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping TACAI Employee Admin")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
