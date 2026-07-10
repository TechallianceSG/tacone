"""
TACAI Project: Shared PostgreSQL Database Utility
=================================================
All modules MUST use PostgreSQL — JSON file storage has been removed.

Usage:
    from db_utils import load_table, save_table, insert_record, update_record, delete_record

    # Reads all rows from PostgreSQL table
    records = load_table("ts_timesheet_entries")

    # Writes all rows to PostgreSQL table
    save_table("ts_timesheet_entries", records)

Set TACAI_DB_ENABLED=false to disable (will raise RuntimeError on any DB operation).
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Optional, Union

import psycopg2
import psycopg2.extras
import psycopg2.pool

# ── Configuration (from environment) ────────────────────────
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", ""),
    "port": int(os.environ.get("DB_PORT", "5432")),
    "dbname": os.environ.get("DB_NAME", ""),
    "user": os.environ.get("DB_USER", ""),
    "password": os.environ.get("DB_PASS", ""),
    "connect_timeout": int(os.environ.get("DB_CONNECT_TIMEOUT", "5")),
}

DB_ENABLED = os.environ.get("TACAI_DB_ENABLED", "true").lower() in ("true", "1", "yes")

if DB_ENABLED:
    if not DB_CONFIG["host"] or not DB_CONFIG["dbname"]:
        sys.stderr.write(
            "[db_utils] ERROR: TACAI_DB_ENABLED=true but DB_HOST/DB_NAME not set. "
            "Database is required.\n"
        )
        DB_ENABLED = False


def require_pg() -> bool:
    """Check that PostgreSQL is available at startup. Returns True if ready."""
    if not DB_ENABLED:
        sys.stderr.write(
            "[db_utils] FATAL: TACAI_DB_ENABLED is false. PostgreSQL is required.\n"
        )
        return False
    if not _is_available():
        sys.stderr.write(
            f"[db_utils] FATAL: Cannot connect to PostgreSQL at "
            f"{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}.\n"
        )
        return False
    return True


# ── Connection pool (thread-safe) ───────────────────────────
_pool: Any = None
_pool_lock: Any = None  # threading.Lock, set on first use


def _init_pool():
    """Initialize the connection pool (lazy, thread-safe)."""
    global _pool, _pool_lock
    import threading as _thr
    if _pool_lock is None:
        _pool_lock = _thr.Lock()
    with _pool_lock:
        if _pool is None:
            _pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=2,
                maxconn=int(os.environ.get("DB_POOL_MAX", "10")),
                **DB_CONFIG,
            )
    return _pool


def _get_conn():
    """Get a connection from the pool (thread-safe)."""
    return _init_pool().getconn()


def _put_conn(conn):
    """Return a connection to the pool."""
    global _pool
    if _pool and conn and not conn.closed:
        try:
            _pool.putconn(conn)
        except Exception:
            try:
                conn.close()
            except Exception:
                pass


def _is_available():
    """Check if PostgreSQL is available (with one retry for transient blips)."""
    if not DB_ENABLED:
        return False
    for attempt in (1, 2):
        try:
            conn = _get_conn()
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
            _put_conn(conn)
            return True
        except Exception:
            if attempt == 1:
                import time as _time
                _time.sleep(0.1)  # Brief pause before retry
    return False


def _ensure_pg():
    """Raise RuntimeError if PostgreSQL is not available."""
    if not _is_available():
        raise RuntimeError(
            f"PostgreSQL unavailable at {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}. "
            "All modules require PostgreSQL. Check DB_HOST/DB_NAME/DB_USER/DB_PASS in .env file."
        )


# ── Internal helpers ──────────────────────────────────────────

def _db_op(operation):
    """Execute a DB operation with proper connection lifecycle.

    Usage:
        def my_fn(conn, cur):
            cur.execute(...)
            return result
        return _db_op(my_fn)
    """
    _ensure_pg()
    conn = _get_conn()
    cur = conn.cursor()
    try:
        result = operation(conn, cur)
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        _put_conn(conn)


# ── JSONB column metadata cache ──────────────────────────────
_jsonb_columns: dict[str, set[str]] = {}


def _get_jsonb_columns(table_name: str) -> set[str]:
    """Return the set of JSONB column names for a table (cached)."""
    if table_name in _jsonb_columns:
        return _jsonb_columns[table_name]
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = %s AND data_type = 'jsonb'",
            (table_name,),
        )
        cols = {row[0] for row in cur.fetchall()}
        cur.close()
        _put_conn(conn)
    except Exception:
        cols = set()
    _jsonb_columns[table_name] = cols
    return cols


# ── Core CRUD Operations ────────────────────────────────────

def load_table(table_name: str, where = None,
               order_by: Optional[str] = None,
               params: Optional[tuple] = None) -> list[dict[str, Any]]:
    """Load rows from a PostgreSQL table. Returns list of dicts.

    Args:
        table_name: PostgreSQL table name.
        where: WHERE clause as either:
            - dict: {column: value} → parameterized "col" = %s AND ...
            - str: raw SQL condition (legacy; use only for trusted inputs)
        order_by: ORDER BY clause (column name or raw SQL).
        params: tuple of values for %s placeholders when `where` is a str.
    """
    _ensure_pg()

    conn = _get_conn()
    cur = conn.cursor()
    try:
        sql = f'SELECT * FROM "{table_name}"'
        query_params: tuple = ()

        if where is not None:
            if isinstance(where, dict):
                clauses = [f'"{k}" = %s' for k in where.keys()]
                sql += " WHERE " + " AND ".join(clauses)
                query_params = tuple(where.values())
            elif isinstance(where, str) and where.strip():
                sql += f" WHERE {where}"
                if params:
                    query_params = params

        if order_by:
            sql += f" ORDER BY {order_by}"

        if query_params:
            cur.execute(sql, query_params)
        else:
            cur.execute(sql)

        columns = [desc[0] for desc in cur.description] if cur.description else []
        # Determine which columns are JSONB (from schema metadata, not string guessing)
        jsonb_cols = _get_jsonb_columns(table_name)

        rows = []
        for row in cur.fetchall():
            record = {}
            for i, col in enumerate(columns):
                val = row[i]
                if col in jsonb_cols and isinstance(val, str):
                    try:
                        record[col] = json.loads(val)
                    except (json.JSONDecodeError, ValueError):
                        record[col] = val
                else:
                    record[col] = val
            rows.append(record)
        return rows
    except Exception as e:
        print(f"[db_utils] load_table({table_name}) error: {e}", file=sys.stderr)
        conn.rollback()
        raise
    finally:
        cur.close()
        _put_conn(conn)


def save_table(table_name: str, records: list[dict[str, Any]],
               pk_column: Optional[str] = None) -> int:
    """Replace all rows in a table with the given records.
    Uses DELETE + INSERT within a transaction for atomicity.
    Returns number of rows inserted.
    """
    _ensure_pg()

    conn = _get_conn()
    cur = conn.cursor()
    try:
        if pk_column is None:
            pk_column = _detect_pk(table_name)

        # Delete all existing rows
        cur.execute(f'DELETE FROM "{table_name}"')

        if not records:
            conn.commit()
            return 0

        # Get column info
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = %s ORDER BY ordinal_position
        """, (table_name,))
        valid_cols = {row[0] for row in cur.fetchall()}

        count = 0
        for record in records:
            if not isinstance(record, dict):
                continue
            common = {k: _serialize_for_db(v) for k, v in record.items() if k in valid_cols}
            if not common:
                continue
            cols = list(common.keys())
            vals = [common[c] for c in cols]
            ph = ', '.join(['%s'] * len(cols))
            cn = ', '.join(f'"{c}"' for c in cols)

            if pk_column and pk_column in common:
                cur.execute(
                    f'INSERT INTO "{table_name}" ({cn}) VALUES ({ph}) '
                    f'ON CONFLICT ("{pk_column}") DO UPDATE SET '
                    + ', '.join(f'"{c}" = EXCLUDED."{c}"' for c in cols if c != pk_column),
                    vals
                )
            else:
                cur.execute(f'INSERT INTO "{table_name}" ({cn}) VALUES ({ph})', vals)
            count += 1

        conn.commit()
        return count
    except Exception as e:
        print(f"[db_utils] save_table({table_name}) error: {e}", file=sys.stderr)
        conn.rollback()
        raise
    finally:
        cur.close()
        _put_conn(conn)


def insert_record(table_name: str, record: dict[str, Any],
                  pk_column: Optional[str] = None) -> bool:
    """Insert a single record. Returns True on success."""
    _ensure_pg()

    conn = _get_conn()
    cur = conn.cursor()
    try:
        if pk_column is None:
            pk_column = _detect_pk(table_name)

        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = %s ORDER BY ordinal_position
        """, (table_name,))
        valid_cols = {row[0] for row in cur.fetchall()}

        common = {k: _serialize_for_db(v) for k, v in record.items() if k in valid_cols}
        if not common:
            return False
        cols = list(common.keys())
        vals = [common[c] for c in cols]
        ph = ', '.join(['%s'] * len(cols))
        cn = ', '.join(f'"{c}"' for c in cols)

        if pk_column and pk_column in common:
            cur.execute(
                f'INSERT INTO "{table_name}" ({cn}) VALUES ({ph}) '
                f'ON CONFLICT ("{pk_column}") DO UPDATE SET '
                + ', '.join(f'"{c}" = EXCLUDED."{c}"' for c in cols if c != pk_column),
                vals
            )
        else:
            cur.execute(f'INSERT INTO "{table_name}" ({cn}) VALUES ({ph})', vals)
        conn.commit()
        return True
    except Exception as e:
        print(f"[db_utils] insert_record({table_name}) error: {e}", file=sys.stderr)
        conn.rollback()
        raise
    finally:
        cur.close()
        _put_conn(conn)


def update_record(table_name: str, pk_column: str, pk_value: Any,
                  updates: dict[str, Any]) -> bool:
    """Update a single record by primary key. Returns True on success."""
    _ensure_pg()

    conn = _get_conn()
    cur = conn.cursor()
    try:
        set_clause = ', '.join(f'"{k}" = %s' for k in updates.keys())
        vals = [_serialize_for_db(v) for v in updates.values()]
        vals.append(pk_value)
        cur.execute(
            f'UPDATE "{table_name}" SET {set_clause} WHERE "{pk_column}" = %s',
            vals
        )
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        print(f"[db_utils] update_record({table_name}) error: {e}", file=sys.stderr)
        conn.rollback()
        raise
    finally:
        cur.close()
        _put_conn(conn)


def delete_record(table_name: str, pk_column: str, pk_value: Any) -> bool:
    """Delete a single record by primary key. Returns True on success."""
    _ensure_pg()

    conn = _get_conn()
    cur = conn.cursor()
    try:
        cur.execute(f'DELETE FROM "{table_name}" WHERE "{pk_column}" = %s', (pk_value,))
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        print(f"[db_utils] delete_record({table_name}) error: {e}", file=sys.stderr)
        conn.rollback()
        raise
    finally:
        cur.close()
        _put_conn(conn)


# ── Helpers ─────────────────────────────────────────────────

def _detect_pk(table_name: str) -> Optional[str]:
    """Auto-detect primary key column for a table."""
    conn = None
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
            WHERE tc.constraint_type = 'PRIMARY KEY'
              AND tc.table_name = %s
        """, (table_name,))
        row = cur.fetchone()
        return row[0] if row else None
    except Exception:
        return None
    finally:
        _put_conn(conn)


def _serialize_for_db(val: Any) -> Any:
    """Convert Python value to PostgreSQL-compatible format.

    Uses psycopg2 native type adapters where available:
      - None            → SQL NULL
      - bool            → PG BOOLEAN
      - int             → PG INTEGER / BIGINT
      - float           → PG DOUBLE PRECISION
      - Decimal         → PG NUMERIC (exact)
      - datetime / date → PG TIMESTAMPTZ / DATE (native psycopg2 adapter)
      - dict / list     → json.dumps() for PG JSONB
      - unknown types   → str() with stderr warning
    """
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    if isinstance(val, int):
        return val
    if isinstance(val, float):
        return val
    if isinstance(val, Decimal):
        return val
    if isinstance(val, (datetime, date)):
        return val
    if isinstance(val, str):
        return val
    if isinstance(val, (dict, list)):
        return json.dumps(val, ensure_ascii=False, default=str)
    # Unknown type — stringify with a warning for debugging
    print(
        f"[db_utils] WARNING: serializing {type(val).__name__} as string. "
        f"Consider explicit conversion before passing to db_utils.",
        file=sys.stderr,
    )
    return str(val)


# ── Raw SQL helpers (for seed data / migrations) ────────────

def execute(sql: str, params=None):
    """Execute a raw SQL statement (INSERT/UPDATE/DELETE). Returns rowcount."""
    _ensure_pg()
    conn = _get_conn()
    cur = conn.cursor()
    try:
        if params:
            cur.execute(sql, params)
        else:
            cur.execute(sql)
        conn.commit()
        return cur.rowcount
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        _put_conn(conn)


def execute_many(sql: str, params_list: list):
    """Execute a raw SQL statement with many parameter sets. Returns rowcount."""
    _ensure_pg()
    conn = _get_conn()
    cur = conn.cursor()
    try:
        cur.executemany(sql, params_list)
        conn.commit()
        return cur.rowcount
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        _put_conn(conn)


def fetch_all(sql: str, params=None):
    """Execute a raw SELECT and return all rows as list of dicts.

    Note: Does NOT auto-parse JSONB columns (table name unknown).
    Use load_table() for automatic JSONB detection, or call json.loads()
    on specific columns in application code.
    """
    _ensure_pg()
    conn = _get_conn()
    cur = conn.cursor()
    try:
        if params:
            cur.execute(sql, params)
        else:
            cur.execute(sql)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description] if cur.description else []
        return [dict(zip(cols, row)) for row in rows]
    finally:
        cur.close()
        _put_conn(conn)


# ── Startup status ──────────────────────────────────────────

if DB_ENABLED:
    _available = _is_available()
    _status = "connected" if _available else "UNAVAILABLE"
    print(f"[db_utils] PostgreSQL {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']} → {_status}",
          file=sys.stderr)
