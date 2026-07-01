"""
TACAI Shared Configuration Module
==================================
Single source of truth for port assignments, service URLs, and allowed hosts/ports.

All TACAI backend modules should import from here instead of hardcoding port
constants.  The start script (start_tacai_lan.sh) and .env.{dev,stg,prd} files
control the runtime values; this module reads those and provides defaults.

Architecture:
  - Portal + User_admin: per-environment (DEV/STG/PRD each get their own instance)
  - Business modules: shared (single instance, fixed ports across all envs)
  - Gateway: single entry point for remote access (port 8010)
  - Vite dev server: 5173 (frontend hot-reload)

Usage:
    from config import (
        ALLOWED_PORTS, ALLOWED_HOSTS,
        get_portal_port, get_auth_port,
        get_service_url, SHARED_SERVICES,
    )
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, NamedTuple, Set


# ── Environment detection ──────────────────────────────────────────────
def _read_env_port(env_var: str, fallback: int) -> int:
    """Read a port from environment variable with fallback."""
    val = os.environ.get(env_var, "").strip()
    if val:
        try:
            return int(val)
        except ValueError:
            pass
    return fallback


# ── Per-environment ports (Portal + User_admin) ────────────────────────
# These are set by start_tacai_lan.sh from .env.{dev,stg,prd}
PORTAL_PORT = _read_env_port("PORT", 3000)
AUTH_PORT = _read_env_port("AUTH_PORT", 3001)

# ── Shared service ports (fixed across all environments) ───────────────
SHARED_PORT = {
    "interview_ready": 8000,
    "payroll_legacy": 8001,
    "timesheet": 8002,
    "expense": 8003,
    "employee_admin": 8004,
    "masterdata": 8007,
    "tacaimsg": 8012,
    "tacaipay_sg": 8016,
    "selfservice": 8018,
}

# Legacy / reserved ports
RESERVED_PORTS = {
    8005,   # Portal legacy default
    8006,   # User_admin legacy default
    8008,   # VendorPayables (planned)
    8009,   # Billing/CustomerBilling (planned)
    8010,   # Gateway
    8011,   # FileAdmin (planned)
    8015,   # TAC Payroll legacy
    8017,   # Reserved
}

# ── All valid local ports ──────────────────────────────────────────────
ALLOWED_PORTS: Set[int] = {
    # Per-environment Portal + Auth
    3000, 3001,   # DEV
    4000, 4001,   # STG
    5000, 5001,   # Reserved (future QA env)
    6000, 6001,   # PRD
    # Shared business services
    *SHARED_PORT.values(),
    # Reserved / planned ports
    *RESERVED_PORTS,
    # Frontend dev server
    5173,  # Vite
    4173,  # Vite preview
}

# ── Allowed hosts for local development ────────────────────────────────
LOCAL_HOSTS = {"127.0.0.1", "localhost"}

PUBLIC_HOST = os.environ.get("TACAI_PUBLIC_HOST", "").strip()
INTERNAL_HOST = os.environ.get("TACAI_INTERNAL_HOST", "127.0.0.1").strip() or "127.0.0.1"

ALLOWED_HOSTS: Set[str] = {*LOCAL_HOSTS, INTERNAL_HOST}
if PUBLIC_HOST and PUBLIC_HOST not in LOCAL_HOSTS:
    ALLOWED_HOSTS.add(PUBLIC_HOST)

# Additional hosts from env
EXTRA_HOSTS = {
    h.strip().lower()
    for h in os.environ.get("TACAI_ALLOWED_PUBLIC_HOSTS", "").split(",")
    if h.strip()
}
ALLOWED_HOSTS |= EXTRA_HOSTS


# ── Service URL helpers ────────────────────────────────────────────────

class ServiceInfo(NamedTuple):
    name: str
    port: int
    relative_dir: str
    command: str


# Shared services definition (used by start_tacai_lan.sh as well)
SHARED_SERVICES: Dict[str, ServiceInfo] = {
    "interview_ready": ServiceInfo("interview_ready", 8000, "InterviewReady", "python3 -m app.cli web --host 0.0.0.0 --port 8000"),
    "payroll_legacy": ServiceInfo("payroll_legacy", 8001, "backup/TACAI-PRJ", "python3 backend/app.py --host 0.0.0.0 --port 8001"),
    "timesheet": ServiceInfo("timesheet", 8002, "backend/services/timesheet", "python3 app.py --host 0.0.0.0 --port 8002"),
    "expense": ServiceInfo("expense", 8003, "backend/services/reimbursement", "python3 app.py --host 0.0.0.0 --port 8003"),
    "employee_admin": ServiceInfo("employee_admin", 8004, "backend/services/employee_admin", "python3 app.py --host 0.0.0.0 --port 8004"),
    "masterdata": ServiceInfo("masterdata", 8007, "backend/services/masterdata", "python3 app.py --host 0.0.0.0 --port 8007"),
    "tacaimsg": ServiceInfo("tacaimsg", 8012, "backend/services/messaging", "python3 app.py --host 0.0.0.0 --port 8012"),
    "tacaipay_sg": ServiceInfo("tacaipay_sg", 8016, "backend/services/payroll/sg", "python3 app.py --host 0.0.0.0 --port 8016"),
    "selfservice": ServiceInfo("selfservice", 8018, "backend/services/self_service", "python3 app.py --host 0.0.0.0 --port 8018"),
}


def get_service_url(service_name: str, host: str | None = None) -> str:
    """Get the base URL for a named service.

    Args:
        service_name: Key in SHARED_PORT or 'portal'/'user_admin'
        host: Host to use (default: TACAI_PUBLIC_HOST or 127.0.0.1)
    """
    if host is None:
        host = PUBLIC_HOST or "127.0.0.1"

    if service_name == "portal":
        port = PORTAL_PORT
    elif service_name == "user_admin":
        port = AUTH_PORT
    else:
        port = SHARED_PORT.get(service_name)
        if port is None:
            raise ValueError(f"Unknown service: {service_name}")

    return f"http://{host}:{port}"


def get_internal_url(service_name: str) -> str:
    """Get the internal (127.0.0.1) URL for a named service."""
    return get_service_url(service_name, host="127.0.0.1")


def get_portal_port() -> int:
    """Current environment's Portal port."""
    return PORTAL_PORT


def get_auth_port() -> int:
    """Current environment's User_admin port."""
    return AUTH_PORT


# ── Environment summary ─────────────────────────────────────────────────

def print_config() -> None:
    """Print current configuration for debugging."""
    print(f"TACAI Config:")
    print(f"  Portal port:  {PORTAL_PORT}")
    print(f"  Auth port:    {AUTH_PORT}")
    print(f"  Public host:  {PUBLIC_HOST or '(auto-detect)'}")
    print(f"  Internal:     {INTERNAL_HOST}")
    print(f"  Allowed ports: {sorted(ALLOWED_PORTS)}")
    print(f"  Shared services: {list(SHARED_PORT.keys())}")


if __name__ == "__main__":
    print_config()
