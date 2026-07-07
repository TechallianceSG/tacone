#!/usr/bin/env python3
"""TACAI API — FastAPI Monolith Entry Point.

Unified backend serving all TACAI modules from a single process.
Previously 9 independent http.server processes; now one FastAPI app.

Usage:
    cd backend
    python3 app.py --host 127.0.0.1 --port 8000
    uvicorn app:app --host 127.0.0.1 --port 8000 --reload
"""

from __future__ import annotations

import argparse
import os
import sys as _sys
from pathlib import Path

# ── Ensure shared/ is on sys.path ──
_shared_path = Path(__file__).resolve().parent / 'shared'
if str(_shared_path) not in _sys.path:
    _sys.path.insert(0, str(_shared_path))

# ── Validate database at startup ──
import db_utils as _db
if not _db.require_pg():
    print("[tacai] FATAL: PostgreSQL is required. Check DB_HOST/DB_NAME/DB_USER/DB_PASS env vars.", file=_sys.stderr)
    _sys.exit(1)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ── App ──────────────────────────────────────────────────────────────────

app = FastAPI(
    title="TACAI API",
    description="TACAI Business Platform — unified API",
    version="3.0.0",
)

# ── CORS ─────────────────────────────────────────────────────────────────

CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# Add public host origins from env
_public_host = os.environ.get("TACAI_PUBLIC_HOST", "").strip()
if _public_host:
    CORS_ORIGINS.extend([
        f"http://{_public_host}:5173",
        f"http://{_public_host}:4173",
        f"http://{_public_host}:3000",
    ])

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With", "Cookie", "Accept", "Accept-Language"],
    expose_headers=["Set-Cookie", "X-TACAI-Module-Version"],
)


# ── Global exception handler ─────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all for unhandled exceptions — return JSON, not HTML."""
    import traceback
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "Internal server error", "detail": str(exc)},
    )


# ── Health check ─────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "module": "tacai-api", "version": "3.0.0"}


# ── Include module routers ───────────────────────────────────────────────
# Import order matters: auth first (other modules depend on it)

from modules.auth.router import router as auth_router
from modules.masterdata.router import router as masterdata_router
from modules.employees.router import router as employees_router
from modules.datadict.router import router as datadict_router
from modules.payroll_jp.router import router as payroll_jp_router
from modules.payroll_sg.router import router as payroll_sg_router
from modules.invoice.router import router as invoice_router
from modules.messaging.router import router as messaging_router

app.include_router(auth_router)
app.include_router(masterdata_router)
app.include_router(employees_router)
app.include_router(datadict_router)
app.include_router(payroll_jp_router)
app.include_router(payroll_sg_router)
app.include_router(invoice_router)
app.include_router(messaging_router)


# ── Main ─────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TACAI API Server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    parser.add_argument("--reload", action="store_true", default=False)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    import uvicorn
    uvicorn.run(
        "app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
