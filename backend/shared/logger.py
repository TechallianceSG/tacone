"""
TACAI Shared Logger
===================
Lightweight structured logging for Python stdlib-based services.
Zero external dependencies — wraps print() with ISO-8601 timestamps,
log levels, and optional JSON output for log aggregation.

Usage:
    from logger import info, warning, error, debug

    info("payroll_jp", "Batch calculated", batch_id="BAT-001", rows=42)
    error("user_admin", "Session validation failed", session_id=sid, reason="expired")

Environment:
    LOG_LEVEL  — minimum level to emit (DEBUG, INFO, WARNING, ERROR; default: INFO)
    LOG_FORMAT — "text" (human-readable) or "json" (machine-parseable; default: "text")
"""

from __future__ import annotations

import json
import os
import sys as _sys
from datetime import datetime, timezone

_LEVELS = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40}
_MIN_LEVEL = _LEVELS.get(
    os.environ.get("LOG_LEVEL", "INFO").upper(), 20,
)
_LOG_FORMAT = os.environ.get("LOG_FORMAT", "text").lower()


def _emit(level: str, module: str, message: str, **fields) -> None:
    if _LEVELS.get(level, 20) < _MIN_LEVEL:
        return
    ts = datetime.now(timezone.utc).isoformat()
    if _LOG_FORMAT == "json":
        record = {
            "ts": ts, "level": level, "module": module,
            "message": message, **fields,
        }
        print(json.dumps(record, ensure_ascii=False, default=str), file=_sys.stderr)
    else:
        extra = " ".join(f"{k}={v}" for k, v in fields.items())
        line = f"[{ts}] {level:<7} [{module}] {message}"
        if extra:
            line += f"  {extra}"
        print(line, file=_sys.stderr)


def debug(module: str, message: str, **fields) -> None:
    _emit("DEBUG", module, message, **fields)


def info(module: str, message: str, **fields) -> None:
    _emit("INFO", module, message, **fields)


def warning(module: str, message: str, **fields) -> None:
    _emit("WARNING", module, message, **fields)


def error(module: str, message: str, **fields) -> None:
    _emit("ERROR", module, message, **fields)
