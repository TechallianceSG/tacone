"""
TACAI Shared Configuration Module
==================================
Single source of truth for host/port configuration.

Architecture:
  - FastAPI monolith: single backend process (default port 8000)
  - Vite dev server: 5173 (frontend hot-reload)

Usage:
    from config import ALLOWED_PORTS, ALLOWED_HOSTS, get_portal_port, get_auth_port
"""

from __future__ import annotations

import os
from typing import Set


# ── Environment helpers ──────────────────────────────────────────────────

def _read_env_port(env_var: str, fallback: int) -> int:
    """Read a port from environment variable with fallback."""
    val = os.environ.get(env_var, "").strip()
    if val:
        try:
            return int(val)
        except ValueError:
            pass
    return fallback


# ── Per-environment ports ────────────────────────────────────────────────
PORTAL_PORT = _read_env_port("PORT", 3000)
AUTH_PORT = _read_env_port("AUTH_PORT", 3001)

# ── Host configuration ───────────────────────────────────────────────────
INTERNAL_HOST = os.environ.get("TACAI_INTERNAL_HOST", "127.0.0.1").strip() or "127.0.0.1"
PUBLIC_HOST = os.environ.get("TACAI_PUBLIC_HOST", "").strip()

LOCAL_HOSTS = {"127.0.0.1", "localhost"}

ALLOWED_HOSTS: Set[str] = {*LOCAL_HOSTS, INTERNAL_HOST}
if PUBLIC_HOST and PUBLIC_HOST not in LOCAL_HOSTS:
    ALLOWED_HOSTS.add(PUBLIC_HOST)

EXTRA_HOSTS = {
    h.strip().lower()
    for h in os.environ.get("TACAI_ALLOWED_PUBLIC_HOSTS", "").split(",")
    if h.strip()
}
ALLOWED_HOSTS |= EXTRA_HOSTS

# ── Allowed local ports ──────────────────────────────────────────────────
ALLOWED_PORTS: Set[int] = {
    # Backend API (FastAPI monolith)
    8000,
    # Per-environment ports (legacy, kept for compatibility)
    3000, 4000, 5000, 6000,
    3001, 4001, 5001, 6001,
    # Frontend dev server
    5173,  # Vite
    4173,  # Vite preview
    # Gateway (cloudflared tunnel)
    8010,
}


# ── Helpers ──────────────────────────────────────────────────────────────

def get_portal_port() -> int:
    """Current environment's Portal port."""
    return PORTAL_PORT


def get_auth_port() -> int:
    """Current environment's User_admin port."""
    return AUTH_PORT


def print_config() -> None:
    """Print current configuration for debugging."""
    print(f"TACAI Config:")
    print(f"  Portal port:  {PORTAL_PORT}")
    print(f"  Auth port:    {AUTH_PORT}")
    print(f"  Public host:  {PUBLIC_HOST or '(auto-detect)'}")
    print(f"  Internal:     {INTERNAL_HOST}")
    print(f"  Allowed ports: {sorted(ALLOWED_PORTS)}")


if __name__ == "__main__":
    print_config()
