# Root Cause Analysis — Session Auth Architecture Flaws

> **Date**: 2026-07-03
> **Scope**: Why the TACAI authentication system accumulated 9 critical design flaws before being addressed
> **Method**: 5-Why analysis + pattern classification

---

## Summary of Flaws Found

| # | Flaw | Severity | Symptom |
|---|------|----------|---------|
| 1 | `save_table` DELETE+INSERT on every request | Critical | O(n) DB writes per API call |
| 2 | Invoice `validate_session()` wrong response format | Critical | 100% 401 on all invoice endpoints |
| 3 | No session cache | High | Redundant user_admin calls |
| 4 | Single global DB connection | High | Thread safety + serialization |
| 5 | No circuit breaker | High | user_admin down = full site 401 |
| 6 | `_CORS_ORIGINS` duplicated 9 times | Medium | Maintenance hazard |
| 7 | 4 different 401 response formats | Medium | Debug difficulty |
| 8 | No session cleanup | Medium | Unbounded table growth |
| 9 | 8-hour absolute timeout (no sliding) | Medium | Daily forced re-login |

---

## Root Cause 1: Organic Growth Without Architecture Gates

### 5-Why

**Q: Why did `save_table` DELETE+INSERT run on every API request?**
A: Because `record_session_activity()` called `save_sessions()`, which used `save_table()`.

**Q: Why did `record_session_activity()` call `save_sessions()`?**
A: Because the original implementation treated the sessions file like any other CRUD resource — load all, modify, save all.

**Q: Why was it treated like any other CRUD resource?**
A: Because `load_json_array`/`save_json_array` was a generic helper designed for seed data (roles, permissions, entities) that rarely changes. Sessions were stored the same way because the helper was convenient.

**Q: Why was a generic helper used for a high-frequency write path?**
A: Because when sessions were first implemented, there was no distinction between "configuration data" (loaded once, rarely changed) and "operational data" (written on every request).

**Root Cause**: **No architecture review gate existed.** When a new data type (sessions) was added, it inherited the existing persistence pattern without questioning whether that pattern was appropriate for the access frequency.

### Lesson

Every new data path should be classified by **read/write frequency** before choosing a persistence strategy:

| Frequency | Pattern | Example |
|-----------|---------|---------|
| Read-heavy, rarely written | `save_table` (DELETE+INSERT) is acceptable | Roles, permissions |
| Read-heavy, frequently written | Targeted UPDATE/DELETE required | Sessions, audit logs |
| Write-once, read-many | INSERT on write, indexed SELECT on read | Employees, entities |

---

## Root Cause 2: Copy-Paste Propagation

### 5-Why

**Q: Why did the Invoice service have a bug where `validate_session()` checked for `body.success` and `body.data.valid`?**
A: Because Invoice had its own local copy of `validate_session()` that parsed the response differently from user_admin's actual format.

**Q: Why did Invoice have a local copy instead of importing from `auth_utils`?**
A: Because payroll/jp was created first (by copying from an older service), and Invoice was created by copying from payroll/jp. The shared `auth_utils` existed, but the copy-paste chain didn't use it.

**Q: Why did the copy-paste chain not use the shared library?**
A: Because the development workflow was: "copy the most similar existing service, then modify." The copied code included a local `validate_session()`. No step in the workflow said "check if there's a shared library for this."

**Q: Why wasn't the shared library usage enforced?**
A: Because `auth_utils` was created after several services already existed, and there was no migration plan or linting rule to ensure all services used it.

**Root Cause**: **Copy-paste driven development without DRY enforcement.** The project grew by forking the nearest service, not by composing from shared libraries. Each fork propagated the patterns (and bugs) of its parent.

### The Copy Chain

```
user_admin (original)
  │─ local validate_session ─┐
  │                          ▼
  ├─ employee_admin ─── uses auth_utils (later migrated) ✅
  │
  ├─ payroll/jp ─────── local copy (correct logic, but duplicated) ⚠️
  │                     │
  │                     └─ invoice ─── local copy (BROKEN parsing) ❌
  │
  └─ datadict ───────── uses auth_utils ✅
```

### Lesson

Every shared library needs a **deprecation notice on the old pattern**. When `auth_utils.validate_session` was created, the local copies should have been marked with:

```python
# DEPRECATED: Use auth_utils.validate_session() instead
# TODO: Remove this local copy after all callers migrate
```

---

## Root Cause 3: Naming Mismatch Between Intent and Implementation

### 5-Why

**Q: Why was the session storage misdiagnosed as "JSON file" by multiple analysis agents?**
A: Because the functions are named `load_json_array()` and `save_json_array()`, and the path constants reference `.json` files.

```python
USER_SESSIONS_PATH = DATABASE_DIR / "user_sessions.json"

def load_json_array(path: Path) -> list:
    """Load records from PostgreSQL."""
    return _db.load_table(f"{MODULE_PREFIX}_{path.stem}")
```

**Q: Why are PostgreSQL functions named after JSON operations?**
A: Because the system originally used JSON files, then migrated to PostgreSQL. The function names were kept for backward compatibility.

**Q: Why weren't the function names updated during migration?**
A: Because renaming would require updating every call site, and the migration was treated as "make it work" rather than "make it clean."

**Root Cause**: **Migration without refactoring.** The database migration changed the storage engine but left the abstraction layer's naming intact. This created a permanent knowledge gap between what the code appears to do and what it actually does.

### Lesson

When migrating storage engines, rename the abstraction layer to reflect the new reality:

```python
# Before (misleading)
load_json_array(path)    # Actually uses PostgreSQL!
save_json_array(path, r) # Actually uses PostgreSQL!

# After (honest)
load_table_by_path(path)
save_table_by_path(path, records)
```

---

## Root Cause 4: No Load Testing

### 5-Why

**Q: Why wasn't the O(n) session write performance caught earlier?**
A: Because it was never tested under load.

**Q: Why was load testing never done?**
A: Because the project prioritized feature velocity over non-functional requirements. The development loop was: write code → manual click test → commit.

**Q: Why was manual click testing considered sufficient?**
A: Because with 1 developer and 2-3 test accounts, the session table never exceeded 10 rows. The O(n) behavior was invisible at n=10.

**Root Cause**: **No performance testing in the development lifecycle.** The system was only tested at n=1 (single developer). Production-like load (n=50+ sessions, n=10+ concurrent users) was never simulated.

### The Multiplication Effect

At small scale (development), the flaws were invisible:

| Metric | Dev (n=3) | Production (n=100) | Blowup |
|--------|-----------|---------------------|--------|
| Sessions in table | 3 | 100 | 33× |
| DB rows inserted per request | 3 | 100 | 33× |
| `active_sessions()` scan time | ~1ms | ~50ms | 50× |
| `save_table()` write time | ~5ms | ~200ms | 40× |
| **Auth latency per request** | **~10ms** | **~300ms** | **30×** |

### Lesson

Every data path that scales with user count must be tested at projected production scale. A simple script that creates 100 fake sessions and runs 100 validation requests would have caught the O(n) problem immediately.

---

## Root Cause 5: Single-Threaded Thinking in a Multi-Threaded Context

### 5-Why

**Q: Why was there a single global DB connection?**
A: Because the initial implementation used `_conn = None` as a module-level singleton.

**Q: Why was a singleton chosen?**
A: Because early prototypes used `BaseHTTPRequestHandler` (single-threaded), and the singleton pattern worked correctly there.

**Q: Why wasn't it changed when the server was upgraded to `ThreadingHTTPServer`?**
A: Because the threading upgrade was a one-line change (`HTTPServer` → `ThreadingHTTPServer`) that didn't trigger a review of downstream thread-safety implications.

**Root Cause**: **Infrastructure upgrade without dependency analysis.** Changing the concurrency model of the HTTP server (single-threaded → multi-threaded) should have triggered a review of all shared state: DB connections, file handles, in-memory caches.

### Lesson

When changing the concurrency model of a component, audit all shared state that component accesses:

```
ThreadingHTTPServer upgrade checklist:
□ DB connection: is it thread-safe? → NO (psycopg2 connections aren't)
□ File I/O: is there locking? → Check
□ Global variables: are they mutated? → Check
□ Caches: are they thread-safe? → Check
```

---

## Systemic Fixes (Beyond the Code)

| # | Fix | How It Prevents Recurrence |
|---|------|---------------------------|
| 1 | **Architecture doc** (`SESSION_AUTH_ARCHITECTURE.md`) | New developers read the design before coding |
| 2 | **Anti-pattern catalog** (Section 5 of architecture doc) | Explicit "never do this" with code examples |
| 3 | **Service checklist** (Section 6 of architecture doc) | Every new service verified against 10 items |
| 4 | **Shared library as single source of truth** | `auth_utils.validate_session()` is THE function |
| 5 | **Data path classification** (this document) | Choose persistence strategy based on access frequency |

---

## What We Did Well

To be fair, the project also made several good architectural decisions:

1. **Monorepo with clear service boundaries** — Each service is independent and can be restarted individually.
2. **API Gateway pattern** — Portal provides a single entry point, simplifying CORS and routing.
3. **Shared libraries for cross-cutting concerns** — `auth_utils`, `db_utils`, `cors_middleware`, `api_utils` exist and are the right abstractions. The problem was adoption, not design.
4. **Cookie-based sessions** — HttpOnly + SameSite=Lax is the correct security posture for a SPA.
5. **Flat JSON convention** — Consistent API contract between frontend and backend.
6. **Environment-based configuration** — `.env.dev` / `.env.stg` / `.env.prd` separation is correct.

The architecture's skeleton was sound. The problems were in the **muscles and circulatory system** — the runtime behavior of the implementation didn't match the static structure's quality.
