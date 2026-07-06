# TACAI Session & Authentication Architecture

> **Version**: 2.0 — Industry-Standard Refactor
> **Date**: 2026-07-03
> **Status**: Implemented
>
> This document describes the end-to-end session validation architecture, the
> design decisions behind the 2026-07 refactor, and the patterns that every
> service MUST follow.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Request Flow (per API call)](#2-request-flow-per-api-call)
3. [Component Reference](#3-component-reference)
4. [Design Decisions (2026-07 Refactor)](#4-design-decisions-2026-07-refactor)
5. [Anti-Patterns (DO NOT REINTRODUCE)](#5-anti-patterns-do-not-reintroduce)
6. [Service Implementation Checklist](#6-service-implementation-checklist)
7. [Configuration Reference](#7-configuration-reference)
8. [Troubleshooting 401](#8-troubleshooting-401)

---

## 1. Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                        BROWSER                               │
│  Cookie: tacai_session_id=<random-32-byte-token>             │
│  withCredentials: true (axios)                               │
└────────────────────────┬─────────────────────────────────────┘
                         │ HTTPS / localhost
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                   PORTAL (:3000)                              │
│  API Gateway + SPA static serving                            │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ Proxy: /api/* → GATEWAY_ROUTES lookup → backend service  │ │
│  │ Forwards: Authorization, Cookie, Accept-Language          │ │
│  │ CORS:    shared cors_middleware                           │ │
│  └─────────────────────────────────────────────────────────┘ │
└──┬──────────┬──────────┬──────────┬──────────┬───────────────┘
   │          │          │          │          │
   ▼          ▼          ▼          ▼          ▼
┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────────┐
│:8004 │ │:8005 │ │:8013 │ │:8019 │ │ :8012    │
│empl  │ │dict  │ │pay/jp│ │inv   │ │ msg      │
│admin │ │      │ │      │ │      │ │          │
└──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └────┬─────┘
   │        │        │        │          │
   │   All services call user_admin to validate sessions      │
   │   via shared auth_utils.validate_session()               │
   │        │        │        │          │
   └────────┴────────┴────────┴──────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│                 USER_ADMIN (:3001)                            │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ Session Cache (in-process, TTL 30s)                      │ │
│  │   validate_session() checks cache → user_admin → cache   │ │
│  └─────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ Circuit Breaker (threshold=5, timeout=15s)               │ │
│  │   Protects against user_admin downtime                   │ │
│  └─────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ Session Storage: PostgreSQL "ua_user_sessions"           │ │
│  │   - Targeted queries (WHERE session_id = ?)              │ │
│  │   - Targeted updates (single-row UPDATE)                 │ │
│  │   - Probabilistic cleanup (1% of calls)                  │ │
│  └─────────────────────────────────────────────────────────┘ │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                   PostgreSQL                                  │
│  Connection Pool: ThreadedConnectionPool(min=2, max=10)       │
│  Tables: ua_user_sessions, ua_users, ua_roles, ...           │
└──────────────────────────────────────────────────────────────┘
```

### Key Principles

| # | Principle | Rationale |
|---|-----------|-----------|
| 1 | **Session is server-side, cookie-based** (not JWT) | No token on client; single revocation point |
| 2 | **Every service validates via shared auth_utils** | Single code path for validation logic |
| 3 | **Cache-first, user_admin second** | 30s TTL eliminates redundant round-trips |
| 4 | **Circuit breaker protects the system** | user_admin downtime ≠ full-site 401 |
| 5 | **Targeted SQL, never full-table rewrites** | O(1) per-request DB writes, not O(n) |
| 6 | **Connection pool for thread safety** | HTTThreadingPServer + single connection = unsafe |

---

## 2. Request Flow (per API call)

### 2.1 Happy Path (cache hit)

```
Browser                Portal              Backend           user_admin         PostgreSQL
  │                      │                    │                   │                  │
  │── GET /api/xxx ─────►│                    │                   │                  │
  │   Cookie: tacai_     │── proxy ──────────►│                   │                  │
  │                      │                    │                   │                  │
  │                      │                    │── validate_session(session_id=?)      │
  │                      │                    │   ┌─ cache.get(sid)                  │
  │                      │                    │   │  → HIT! (TTL < 30s)             │
  │                      │                    │   └─ return cached user              │
  │                      │                    │                   │                  │
  │                      │                    │── handle request ───────────────────►│
  │                      │                    │                   │   SELECT/UPDATE   │
  │                      │                    │◄── result ────────│                  │
  │                      │◄── response ───────│                   │                  │
  │◄── 200 OK ──────────│                    │                   │                  │

  Latency: ~2-5ms (no user_admin call)
```

### 2.2 Happy Path (cache miss)

```
Browser                Portal              Backend           user_admin         PostgreSQL
  │                      │                    │                   │                  │
  │── GET /api/xxx ─────►│── proxy ──────────►│                   │                  │
  │                      │                    │── validate_session(session_id=?)      │
  │                      │                    │   ┌─ cache.get(sid) → MISS           │
  │                      │                    │   │─ HTTP POST /api/validate-session ►│
  │                      │                    │   │                │─ validate_sess..►│
  │                      │                    │   │                │  SELECT WHERE     │
  │                      │                    │   │                │  session_id = ?  │
  │                      │                    │   │                │◄─ session, user  │
  │                      │                    │   │                │─ record_activity►│
  │                      │                    │   │                │  UPDATE … WHERE   │
  │                      │                    │   │                │  session_id = ?  │
  │                      │                    │   │◄─ {valid,user}─│                  │
  │                      │                    │   └─ cache.set(sid, user)            │
  │                      │                    │── handle request ───────────────────►│
  │                      │◄── response ───────│                   │                  │
  │◄── 200 OK ──────────│                    │                   │                  │

  Latency: ~10-20ms (cache miss + user_admin call)
```

### 2.3 Circuit Breaker Open (user_admin down)

```
Browser                Portal              Backend           user_admin
  │                      │                    │                   │
  │── GET /api/xxx ─────►│── proxy ──────────►│                   │
  │                      │                    │── validate_session()
  │                      │                    │   ┌─ cache.get(sid) → MISS
  │                      │                    │   │─ circuit breaker → OPEN
  │                      │                    │   └─ return None (fast fail)
  │                      │                    │── 401 Unauthorized
  │                      │◄── 401 ────────────│
  │◄── 401 ──────────────│                    │
  │  → frontend retries session validation   │
  │  → if still fails, redirect to /login    │

  Latency: ~1ms (immediate short-circuit, no 5s timeout hang)
```

---

## 3. Component Reference

### 3.1 `auth_utils.py` — Shared Validation (THE authority)

**Path**: `backend/shared/auth_utils.py`
**Imported by**: ALL backend services

```python
from auth_utils import validate_session, has_permission, is_system_admin

# Pattern A: Raw cookie header (employee_admin, datadict)
user = validate_session(self.headers.get("Cookie", ""))

# Pattern B: Explicit session_id (payroll/jp, invoice, messaging)
cookies = SimpleCookie(self.headers.get("Cookie", ""))
user = validate_session(session_id=cookies["tacai_session_id"].value)
```

**Internal layers** (in order of execution):
1. `_SessionCache.get(sid)` — in-memory TTL cache (30s default)
2. `_CircuitBreaker.is_open` — fast-fail if user_admin is unhealthy
3. `HTTP POST /api/validate-session` — call user_admin (5s timeout)
4. `_SessionCache.set(sid, user)` — populate cache on success
5. `_CircuitBreaker.record_success/failure` — update health state

**Do NOT write a local validate_session() in any service.** This is the single source of truth. Local copies caused the Invoice 401 bug (2026-07).

### 3.2 Session Storage — PostgreSQL `ua_user_sessions`

**Table**: `ua_user_sessions` (managed via `db_utils`)

**Operations** (post-refactor):

| Operation | Before (Anti-pattern) | After (Industry Standard) |
|-----------|----------------------|---------------------------|
| Validate one session | `SELECT *` → iterate all → find one | `SELECT * WHERE session_id = ?` |
| Record activity | `SELECT *` → modify → `DELETE ALL` + `INSERT ALL` | `UPDATE … WHERE session_id = ?` |
| Mark expired | Iterate all → modify → `DELETE ALL` + `INSERT ALL` | `UPDATE … WHERE active=true AND expires_at<=NOW()` |
| Cleanup old | Never done | `DELETE … WHERE active=false AND expires_at < NOW()-7d` (1% chance) |

### 3.3 Connection Pool — `db_utils.py`

```
ThreadedConnectionPool(min=2, max=DB_POOL_MAX=10)
├── Thread 1: conn_1
├── Thread 2: conn_2
├── ...
└── Thread N: waits if all connections busy
```

Every DB function follows the pattern:
```python
conn = _get_conn()      # borrow from pool
try:
    ... do work ...
    conn.commit()
except:
    conn.rollback()
finally:
    _put_conn(conn)     # return to pool (ALWAYS)
```

### 3.4 Circuit Breaker — `auth_utils.py`

```
State machine:
  CLOSED (normal)
    │  failures >= threshold (5)
    ▼
  OPEN (fast-fail, no user_admin calls)
    │  timeout (15s) elapsed
    ▼
  HALF-OPEN (allow 1 probe request)
    │  success → CLOSED
    │  failure → OPEN
```

### 3.5 Session Lifecycle

```
LOGIN                           ACTIVE                          EXPIRED/CLEANUP
  │                               │                                  │
  │ POST /api/auth/login          │                                  │
  │ → create session              │                                  │
  │ → expires_at = now + 480min   │                                  │
  │                               │                                  │
  │                               │ Each API request:                │
  │                               │ → validate_session()             │
  │                               │ → cache hit/miss                 │
  │                               │ → record_session_activity()      │
  │                               │   → UPDATE last_seen_at          │
  │                               │   → SLIDING: expires_at += 480m  │
  │                               │                                  │
  │                               │                                  │
  LOGOUT                         IDLE > 480min                      >7 DAYS INACTIVE
  │                               │                                  │
  │ → active = false              │ → active = false                  │ → DELETE
  │ → logout_time = now           │ → logout_time = expires_at        │   (probabilistic)
```

---

## 4. Design Decisions (2026-07 Refactor)

### Decision 1: Cookie-based sessions, not JWT

**Chosen**: Server-side session with `secrets.token_urlsafe(32)` as session ID
**Rejected**: JWT with client-side token storage

**Rationale**:
- Single revocation point (delete session record = immediate logout)
- No token size overhead in headers (JWTs grow with claims)
- No key rotation complexity
- Cookie is HttpOnly → XSS cannot steal it
- Trade-off: Every validation requires a DB/cache lookup (mitigated by cache)

### Decision 2: In-memory cache (30s TTL) instead of Redis

**Chosen**: Per-process `dict` with TTL in `auth_utils`
**Rejected**: External Redis/memcached

**Rationale**:
- Zero infrastructure dependency
- 30s staleness is acceptable (worst case: 30s delay on logout/revocation)
- 500-entry cap with auto-pruning prevents memory leaks
- Trade-off: Cache is per-process (each backend service has its own). Acceptable because cache miss just calls user_admin.

### Decision 3: Circuit breaker instead of retry-with-backoff

**Chosen**: Fail-fast circuit breaker after 5 consecutive failures
**Rejected**: Exponential backoff retry loop in every service

**Rationale**:
- Retry storms during user_admin outage amplify load
- Circuit breaker eliminates the 5s timeout hang for every request
- Frontend already has session-refresh retry (client.ts interceptor)
- Trade-off: During circuit-open, cache misses return 401. Acceptable — 30s TTL covers most requests.

### Decision 4: Targeted SQL instead of ORM

**Chosen**: Raw parameterized SQL via `db_utils`
**Rejected**: SQLAlchemy ORM

**Rationale**:
- Project constraint: Python stdlib + psycopg2 only
- `db_utils` CRUD helpers provide enough abstraction
- Direct SQL makes performance characteristics obvious (no N+1 surprises)
- Trade-off: No migration framework. Manual SQL for schema changes.

### Decision 5: Sliding expiration instead of absolute + refresh token

**Chosen**: Extend `expires_at` on every activity
**Rejected**: Fixed expiration + separate refresh token

**Rationale**:
- Single token model is simpler to implement and debug
- "Idle timeout" semantics match user expectation (active users don't get logged out)
- No refresh token to leak or manage
- Trade-off: Long-lived session if user has constant activity. Mitigated by 480min max idle.

---

## 5. Anti-Patterns (DO NOT REINTRODUCE)

### Anti-Pattern 1: Local copy of `validate_session()`

```python
# ❌ NEVER DO THIS
def validate_session(session_id):
    req = Request(f"{USER_ADMIN_URL}/api/validate-session", ...)
    resp = urlopen(req)
    body = json.loads(resp.read())
    if body.get("success") and body.get("data", {}).get("valid"):  # WRONG FORMAT
        return body["data"]
```

**Why it's wrong**: Response parsing drifts from user_admin's actual format.
**What to do**: `from auth_utils import validate_session`

### Anti-Pattern 2: Full-table rewrite for single-row update

```python
# ❌ NEVER DO THIS
sessions = load_sessions()        # SELECT ALL
for s in sessions:
    if s["id"] == target:
        s["field"] = new_value    # modify one
save_sessions(sessions)           # DELETE ALL + INSERT ALL
```

**Why it's wrong**: O(n) DB writes for an O(1) operation. At 100 sessions, 100x more DB load.
**What to do**: `_db.update_record("table", "id", target, {"field": new_value})`

### Anti-Pattern 3: Local CORS origins

```python
# ❌ NEVER DO THIS
_CORS_ORIGINS = {"http://localhost:5173", ...}
def _add_cors(handler):
    ...
```

**Why it's wrong**: 9 copies of the same origins. Adding a port requires 9 edits.
**What to do**: `from cors_middleware import add_cors_headers, handle_preflight`

### Anti-Pattern 4: Calling `active_sessions()` for single-session lookup

```python
# ❌ NEVER DO THIS
for session in active_sessions():    # loads ALL sessions
    if session["session_id"] == sid:  # linear scan
        return session
```

**Why it's wrong**: Full table scan for a PK lookup.
**What to do**: `_db.load_table("ua_user_sessions", where={"session_id": sid})`

---

## 6. Service Implementation Checklist

When creating a new backend service, verify EVERY item:

- [ ] Imports `validate_session, has_permission, is_system_admin` from `auth_utils`
- [ ] Imports `add_cors_headers, handle_preflight` from `cors_middleware`
- [ ] Has `_require_auth()` or `_require_user()` that calls `validate_session()`
- [ ] 401 response uses **one** of these formats consistently:
  - `{"error": "Unauthorized"}` (preferred)
  - `{"success": false, "error": "Unauthorized"}` (legacy, existing services only)
- [ ] `do_OPTIONS()` calls `handle_preflight(self)` (3 lines → 1 line)
- [ ] Registered in `GATEWAY_ROUTES` in `backend/shared/config.py`
- [ ] Registered in `SHARED_SERVICES` in `start_tacai_lan.sh`
- [ ] Uses `_db` for all data operations (no JSON file storage)
- [ ] Table names use module prefix (e.g., `pay_jp_`, `inv_`)
- [ ] Audit log includes `module, record_id, action, user, timestamp, before_value, after_value`

---

## 7. Configuration Reference

| Env Variable | Default | Description |
|-------------|---------|-------------|
| `SESSION_CACHE_TTL` | `30` | Session cache TTL in seconds |
| `AUTH_CB_THRESHOLD` | `5` | Circuit breaker failure threshold |
| `AUTH_CB_TIMEOUT` | `15` | Circuit breaker open timeout in seconds |
| `DB_POOL_MAX` | `10` | Max connections in DB pool |
| `AUTH_PORT` | `3001` | user_admin port |
| `TACAI_INTERNAL_HOST` | `127.0.0.1` | Internal host for user_admin calls |
| `SESSION_TIMEOUT_MINUTES` | `480` | Session idle timeout (hardcoded in user_admin) |

---

## 8. Troubleshooting 401

### Symptom: All users getting 401

| Check | Command / Action |
|-------|-----------------|
| Is user_admin running? | `curl http://127.0.0.1:3001/health` |
| Is PostgreSQL running? | `psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "SELECT 1"` |
| Circuit breaker open? | Check logs for "circuit" or 5+ consecutive validate failures |
| Session cache stale? | Restart affected backend service (clears in-memory cache) |

### Symptom: One user getting 401

| Check | Action |
|-------|--------|
| Session expired (>480min idle)? | User must re-login |
| User account locked? | Check `ua_users` for `account_locked = true` |
| Entity deactivated? | Check `md_entities` for user's entity_code active status |
| Session manually invalidated? | Check `ua_user_sessions` for `active = false` |

### Symptom: Intermittent 401

| Check | Action |
|-------|--------|
| DB connection pool exhausted? | Increase `DB_POOL_MAX` |
| user_admin under load? | Check CPU/memory; consider scaling |
| Frontend race condition? | Check browser console for `tacai:session-expired` events |
| Multiple tabs competing? | Session cookie is shared; this is expected |
