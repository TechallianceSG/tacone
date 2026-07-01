#!/usr/bin/env python3
"""TACAI Temp Gateway — lightweight external-facing HTTP server.

Serves the built Vue 3 SPA (frontend/dist/) and proxies /api/* requests
to the internal Portal service.  Designed as a fixed-port (8010) entry
point for Cloudflare Tunnel so that the per-environment Portal ports
(3000/4000/6000) don't need to be exposed to the tunnel.

Usage:
    python3 tacai_temp_gateway.py --host 0.0.0.0 --port 8010 [--portal-port 3000]
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

# ── Project root ──────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"
INDEX_HTML = FRONTEND_DIST / "index.html"

# ── MIME type mapping for common static assets ────────────────
mimetypes.init()
MIME_OVERRIDE = {
    ".js": "application/javascript; charset=utf-8",
    ".mjs": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".txt": "text/plain; charset=utf-8",
}


def get_mime(path: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix in MIME_OVERRIDE:
        return MIME_OVERRIDE[suffix]
    mime, _ = mimetypes.guess_type(path)
    return mime or "application/octet-stream"


# ── Allowed origins (CORS) ───────────────────────────────────
def _build_allowed_origins() -> set:
    origins = {
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:4173", "http://127.0.0.1:4173",
        "http://localhost:3000", "http://127.0.0.1:3000",
        "http://localhost:4000", "http://127.0.0.1:4000",
        "http://localhost:6000", "http://127.0.0.1:6000",
        "http://localhost:8010", "http://127.0.0.1:8010",
    }
    # Add LAN IP origins if TACAI_PUBLIC_HOST is set
    public_host = os.environ.get("TACAI_PUBLIC_HOST", "").strip()
    if public_host:
        for port in (3000, 4000, 6000, 8010):
            origins.add(f"http://{public_host}:{port}")
    return origins


ALLOWED_ORIGINS = _build_allowed_origins()


class GatewayHandler(BaseHTTPRequestHandler):
    """Serves SPA static files and proxies /api/* to Portal."""

    server_version = "TACAIGateway/0.1"
    portal_port: int = 3000

    # ── CORS ──────────────────────────────────────────────────

    def add_cors(self, origin: str | None = None) -> None:
        req_origin = origin or self.headers.get("Origin", "")
        allowed = req_origin if req_origin in ALLOWED_ORIGINS else next(iter(ALLOWED_ORIGINS))
        self.send_header("Access-Control-Allow-Origin", allowed)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, PATCH, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With, Cookie, Accept-Language")
        self.send_header("Access-Control-Allow-Credentials", "true")

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.add_cors()
        self.end_headers()

    # ── Static file serving ───────────────────────────────────

    def _serve_static(self) -> bool:
        """Serve a file from frontend/dist/. Returns True if served."""
        if not FRONTEND_DIST.exists():
            return False

        parsed = urlparse(self.path)
        req_path = parsed.path.lstrip("/")

        # /assets/* → static files with caching
        if req_path.startswith("assets/"):
            asset = FRONTEND_DIST / req_path
            if asset.is_file():
                content = asset.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", get_mime(req_path))
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "public, max-age=31536000, immutable")
                self.end_headers()
                self.wfile.write(content)
                return True

        # /favicon.ico → root of dist
        favicon = FRONTEND_DIST / "favicon.ico"
        if req_path == "favicon.ico" and favicon.is_file():
            content = favicon.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "image/x-icon")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return True

        return False

    def _serve_spa_fallback(self) -> bool:
        """Serve index.html as SPA fallback. Returns True if served."""
        if INDEX_HTML.exists():
            content = INDEX_HTML.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(content)
            return True
        return False

    # ── API proxy to Portal ───────────────────────────────────

    def _proxy_api(self, method: str = "GET") -> bool:
        """Proxy /api/* to Portal. Returns True if handled."""
        if not self.path.startswith("/api/"):
            return False

        portal_url = f"http://127.0.0.1:{self.portal_port}{self.path}"

        body = None
        if method in ("POST", "PUT", "PATCH"):
            length = int(self.headers.get("Content-Length", "0") or "0")
            body = self.rfile.read(length) if length else None

        req = Request(portal_url, data=body, method=method)

        # Forward relevant headers
        for header in ("Content-Type", "Accept", "Accept-Language", "Cookie",
                       "Authorization", "X-Requested-With"):
            val = self.headers.get(header)
            if val:
                req.add_header(header, val)

        timeout = 120 if "/import" in self.path else 30

        try:
            with urlopen(req, timeout=timeout) as resp:
                status = resp.status
                resp_headers = dict(resp.headers)
                resp_body = resp.read()
        except HTTPError as e:
            status = e.code
            resp_headers = dict(e.headers)
            resp_body = e.read()
        except (URLError, OSError):
            error_body = json.dumps({
                "error": "Bad Gateway",
                "message": "Portal service is not available",
            }).encode("utf-8")
            self.send_response(HTTPStatus.BAD_GATEWAY)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(error_body)))
            self.end_headers()
            self.wfile.write(error_body)
            return True

        # Relay response
        self.send_response(status)
        self.add_cors()
        skip_headers = {"connection", "keep-alive", "transfer-encoding",
                        "proxy-authenticate", "proxy-authorization", "te", "trailers"}
        for key, val in resp_headers.items():
            if key.lower() not in skip_headers:
                self.send_header(key, val)
        self.end_headers()
        self.wfile.write(resp_body)
        return True

    # ── Health ────────────────────────────────────────────────

    def _serve_health(self) -> bool:
        if self.path == "/health":
            portal_ok = False
            try:
                with urlopen(f"http://127.0.0.1:{self.portal_port}/health", timeout=2) as resp:
                    portal_ok = resp.read().decode().strip() == '{"status": "ok", "module": "tacai-portal"}'
            except Exception:
                pass
            data = {
                "status": "ok" if portal_ok else "degraded",
                "module": "tacai-gateway",
                "portal": "up" if portal_ok else "down",
                "frontend": "built" if INDEX_HTML.exists() else "not_built",
            }
            payload = json.dumps(data).encode("utf-8")
            self.send_response(HTTPStatus.OK if portal_ok else HTTPStatus.SERVICE_UNAVAILABLE)
            self.add_cors()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return True
        return False

    # ── Request routing ───────────────────────────────────────

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        # Suppress default access log for cleaner output
        return

    def do_GET(self) -> None:  # noqa: N802
        if self._serve_health():
            return
        if self._proxy_api("GET"):
            return
        if self._serve_static():
            return
        if self._serve_spa_fallback():
            return
        # Nothing matched
        self.send_response(HTTPStatus.NOT_FOUND)
        self.add_cors()
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        if self._proxy_api("POST"):
            return
        # Non-API POST → SPA fallback (Vue Router handles it)
        self._serve_spa_fallback()

    def do_PUT(self) -> None:  # noqa: N802
        if self._proxy_api("PUT"):
            return
        self.send_response(HTTPStatus.METHOD_NOT_ALLOWED)
        self.add_cors()
        self.end_headers()

    def do_PATCH(self) -> None:  # noqa: N802
        if self._proxy_api("PATCH"):
            return
        self.send_response(HTTPStatus.METHOD_NOT_ALLOWED)
        self.add_cors()
        self.end_headers()

    def do_DELETE(self) -> None:  # noqa: N802
        if self._proxy_api("DELETE"):
            return
        self.send_response(HTTPStatus.METHOD_NOT_ALLOWED)
        self.add_cors()
        self.end_headers()


# ── Entry point ───────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TACAI Temp Gateway")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("TACAI_GATEWAY_PORT", "8010")),
                        help="Listen port (default: 8010 or $TACAI_GATEWAY_PORT)")
    parser.add_argument("--portal-port", type=int,
                        default=int(os.environ.get("PORT", "3000")),
                        help="Portal backend port (default: 3000 or $PORT)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    GatewayHandler.portal_port = args.portal_port

    server = ThreadingHTTPServer((args.host, args.port), GatewayHandler)
    print(f"[gateway] Listening on http://{args.host}:{args.port}")
    print(f"[gateway] Portal backend → http://127.0.0.1:{args.portal_port}")
    print(f"[gateway] Static files  → {FRONTEND_DIST} {'✅' if FRONTEND_DIST.exists() else '❌ (not built)'}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[gateway] Stopping...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
