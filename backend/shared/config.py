"""
TACAI Shared Configuration Module
==================================
Single source of truth for port assignments, service URLs, gateway routes,
and allowed hosts/ports.

All TACAI backend modules should import from here instead of hardcoding port
constants.  The start script (start_tacai_lan.sh) and .env.{dev,stg,prd} files
control the runtime values; this module reads those and provides defaults.

Architecture:
  - Portal (:3000): unified API Gateway — single entry point for the SPA frontend
  - User_admin: per-environment (DEV/STG/PRD each get their own instance)
  - Business modules: shared (single instance, fixed ports across all envs)
  - GATEWAY_ROUTES: path-prefix → internal-port mapping for Portal forwarding
  - Vite dev server: 5173 (frontend hot-reload)

Usage:
    from config import (
        ALLOWED_PORTS, ALLOWED_HOSTS, GATEWAY_ROUTES,
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
    "employee_admin": 8004,
    "datadict": 8005,
    "masterdata": 8007,
    "tacaimsg": 8012,
    "tacaipay_jp": 8013,
    "tacaiinvoice": 8019,
}

# Currently all internal services use fixed ports; no reserved ports needed.
RESERVED_PORTS: set[int] = set()

# ── API Gateway route table ──────────────────────────────────────────
# Maps API path prefix → internal backend port.
# Portal (:3000) is the single entry point; it forwards requests to
# internal services based on this table.  /api/portal/* is handled
# natively by Portal itself and is NOT listed here.
GATEWAY_ROUTES: Dict[str, int] = {
    # ── User_admin (AUTH_PORT) ──
    '/api/auth/':           AUTH_PORT,
    '/api/public/':         AUTH_PORT,
    '/api/users/':          AUTH_PORT,
    '/api/roles/':          AUTH_PORT,
    '/api/permissions/':    AUTH_PORT,
    '/api/audit-logs/':     AUTH_PORT,
    '/api/login-sessions/': AUTH_PORT,
    '/api/dashboard/':      AUTH_PORT,
    # ── Business services (shared ports) ──
    '/api/employees/':       SHARED_PORT['employee_admin'],
    '/api/data-dictionary/': SHARED_PORT['datadict'],
    '/api/masterdata/':      SHARED_PORT['masterdata'],
    '/api/master-data/':     SHARED_PORT['masterdata'],
    '/api/messages/':        SHARED_PORT['tacaimsg'],
    # ── Payroll ──
    '/api/payroll/jp/':     SHARED_PORT['tacaipay_jp'],
    '/api/payroll/':        SHARED_PORT['tacaipay_jp'],
    # ── Invoice ──
    '/api/invoice/':        SHARED_PORT['tacaiinvoice'],
}

# ── All valid local ports ──────────────────────────────────────────────
# With the API Gateway pattern, only Portal ports need external access.
# Internal service ports are only accessed by Portal via localhost.
ALLOWED_PORTS: Set[int] = {
    # Per-environment Portal
    3000, 4000, 5000, 6000,
    # Auth (needed for direct session validation in dev)
    3001, 4001, 5001, 6001,
    # Frontend dev server
    5173,  # Vite
    4173,  # Vite preview
    # Gateway (cloudflared tunnel)
    8010,  # TACAI_GATEWAY_PORT
    # Internal shared services (accessed via localhost)
    8004, 8005, 8007, 8012, 8013, 8019,
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
    "employee_admin": ServiceInfo("employee_admin", 8004, "backend/services/employee_admin", "python3 app.py --host 0.0.0.0 --port 8004"),
    "datadict": ServiceInfo("datadict", 8005, "backend/services/datadict", "python3 app.py --host 0.0.0.0 --port 8005"),
    "masterdata": ServiceInfo("masterdata", 8007, "backend/services/masterdata", "python3 app.py --host 0.0.0.0 --port 8007"),
    "tacaimsg": ServiceInfo("tacaimsg", 8012, "backend/services/messaging", "python3 app.py --host 0.0.0.0 --port 8012"),
    "tacaipay_jp": ServiceInfo("tacaipay_jp", 8013, "backend/services/payroll/jp", "python3 app.py --host 0.0.0.0 --port 8013"),
    "tacaiinvoice": ServiceInfo("tacaiinvoice", 8019, "backend/services/invoice", "python3 app.py --host 0.0.0.0 --port 8019"),
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
