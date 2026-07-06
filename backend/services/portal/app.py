#!/usr/bin/env python3
"""TACAI Portal local web app.

A lightweight standard-library portal for the future unified TACAI login window.
"""

from __future__ import annotations

import argparse
import html
import json
import os
from datetime import datetime, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import URLError
from urllib.parse import parse_qs, quote, urlencode, urlparse
from urllib.request import Request, urlopen
import sys as _sys

# ── Shared libraries (backend/shared/) ──
_shared_path = Path(__file__).resolve().parents[2] / 'shared'
if str(_shared_path) not in _sys.path:
    _sys.path.insert(0, str(_shared_path))
try:
    import db_utils as _db
except Exception:
    print("[portal] FATAL: db_utils is required. PostgreSQL must be available.", file=_sys.stderr)
    _sys.exit(1)
from cors_middleware import add_cors_headers, handle_preflight

BASE_DIR = Path(__file__).resolve().parents[0]
DATABASE_DIR = BASE_DIR / "database"
FRONTEND_DIR = BASE_DIR / "frontend"
AUDIT_LOG_FILE = DATABASE_DIR / "audit_logs.json"
MODULES_FILE = DATABASE_DIR / "modules.json"
USER_ADMIN_SESSION_COOKIE = "tacai_session_id"
LANGUAGE_COOKIE = "tacai_portal_lang"
# ── PostgreSQL table prefixes ──
MODULE_PREFIX = "pt"
MSG_PREFIX = "msg"
UA_PREFIX = "ua"

MODULE_NAME = "tacai-portal"
TACAI_PUBLIC_HOST = os.environ.get("TACAI_PUBLIC_HOST", "127.0.0.1").strip() or "127.0.0.1"
TACAI_INTERNAL_HOST = os.environ.get("TACAI_INTERNAL_HOST", "127.0.0.1").strip() or "127.0.0.1"
LOCAL_ALLOWED_HOSTS = {"127.0.0.1", "localhost", TACAI_PUBLIC_HOST, TACAI_INTERNAL_HOST}
# ── Shared port/host config (single source of truth) ──
try:
    from config import ALLOWED_PORTS as LOCAL_ALLOWED_PORTS
except ImportError:
    LOCAL_ALLOWED_PORTS = {3000, 4000, 5000, 6000}

# ── API Gateway route table ──
try:
    from config import GATEWAY_ROUTES
except ImportError:
    GATEWAY_ROUTES = {}
CONFIGURED_PUBLIC_HOSTS = {host.strip().lower() for host in os.environ.get("TACAI_ALLOWED_PUBLIC_HOSTS", "").split(",") if host.strip()}


def local_base_url(port: int) -> str:
    return f"http://{TACAI_PUBLIC_HOST}:{port}"


def internal_base_url(port: int) -> str:
    return f"http://{TACAI_INTERNAL_HOST}:{port}"


def public_base_url(env_name: str, fallback_port: int) -> str:
    return os.environ.get(env_name, local_base_url(fallback_port)).strip().rstrip("/")


def base_url_host(value: str) -> str:
    parsed = urlparse(value)
    return (parsed.hostname or "").lower()


_PORTAL_FALLBACK_PORT = int(os.environ.get("PORT", "3000"))
_AUTH_FALLBACK_PORT = int(os.environ.get("AUTH_PORT", "3001"))
PORTAL_BASE_URL = (os.environ.get("PORTAL_BASE_URL") or "").strip().rstrip("/") or public_base_url("PORTAL_PUBLIC_BASE_URL", _PORTAL_FALLBACK_PORT)
USER_ADMIN_BASE_URL = public_base_url("USER_ADMIN_PUBLIC_BASE_URL", _AUTH_FALLBACK_PORT)
USER_ADMIN_INTERNAL_BASE_URL = os.environ.get("USER_ADMIN_INTERNAL_BASE_URL", internal_base_url(_AUTH_FALLBACK_PORT)).strip().rstrip("/")
TACAIMSG_BASE_URL = public_base_url("TACAIMSG_PUBLIC_BASE_URL", 8012)
PUBLIC_ALLOWED_HOSTS = CONFIGURED_PUBLIC_HOSTS | {host for host in [base_url_host(PORTAL_BASE_URL), base_url_host(USER_ADMIN_BASE_URL)] if host}
SUPPORTED_LANGUAGES = {"ja", "zh", "en"}
DEFAULT_LANGUAGE = "ja"
LANGUAGE_LABELS = {
    "ja": "日本語",
    "zh": "中文",
    "en": "English",
}

TRANSLATIONS = {
    "ja": {
        "app.title": "TACAI Portal",
        "app.subtitle": "TACAI 業務モジュールへの統一入口",
        "login.title": "TACAI Portal",
        "login.subtitle": "TACAI の各業務システムへ安全にアクセスするための統一ログイン入口です。",
        "login.auth_note": "認証は TACAI User Management が担当します。ログイン後、あなたの権限に応じたモジュールだけを表示します。",
        "login.button": "TACAI User Management でログイン",
        "login.hint": "ログイン完了後、Portal ダッシュボードへ自動的に戻ります。",
        "unavailable.title": "User Management に接続できません",
        "unavailable.subtitle": "Portal は User_admin でログイン状態を確認しますが、現在サービスに接続できません。",
        "unavailable.hint": "ローカル検証では、先に以下のコマンドで User_admin を起動してください。",
        "unavailable.retry": "Portal を再試行",
        "dashboard.eyebrow": "Unified Entry",
        "dashboard.title": "ダッシュボード",
        "dashboard.hero_title": "TACAI Portal へようこそ",
        "dashboard.hero_text": "TACAI Portal は Employee Mgmt、Timesheet、Payroll、Expense、Message Center、User Management などの業務モジュールを一か所から開くための入口です。表示されるモジュールは User Management の権限設定に基づきます。",
        "dashboard.empty": "利用可能なモジュールがありません。システム管理者へお問い合わせください。",
        "logout": "ログアウト",
        "future_module.eyebrow": "Module Entry",
        "future_module.title_suffix": "TACAI Portal",
        "future_module.reserved": "このモジュール入口は準備済みです",
        "future_module.text": "Portal のナビゲーション構造を維持し、今後のモジュール統合に備えています。",
        "back_dashboard": "ダッシュボードへ戻る",
        "not_found.title": "ページが見つかりません",
        "not_found.text": "指定された Portal ページは存在しません。",
        "forbidden.title": "アクセスできません",
        "forbidden.text": "リクエスト元を確認できないため、操作を拒否しました。",
        "language.label": "表示言語",
        "entity.current": "現在の法人",
        "entity.required.title": "法人コンテキストが必要です",
        "entity.required.text": "現在のセッションには法人情報がありません。User Management から法人コードを指定して再ログインしてください。",
    },
    "zh": {
        "app.title": "TACAI Portal",
        "app.subtitle": "TACAI 业务模块统一入口",
        "login.title": "TACAI Portal",
        "login.subtitle": "用于安全进入 TACAI 各业务系统的统一登录入口。",
        "login.auth_note": "身份认证由 TACAI User Management 负责。登录后，Portal 会按照你的权限显示可访问模块。",
        "login.button": "使用 TACAI User Management 登录",
        "login.hint": "登录完成后会自动返回 Portal 仪表盘。",
        "unavailable.title": "无法连接 User Management",
        "unavailable.subtitle": "Portal 需要通过 User_admin 验证登录状态，但当前服务不可达。",
        "unavailable.hint": "本地验证时，请先用以下命令启动 User_admin。",
        "unavailable.retry": "重试 Portal",
        "dashboard.eyebrow": "统一入口",
        "dashboard.title": "仪表盘",
        "dashboard.hero_title": "欢迎使用 TACAI Portal",
        "dashboard.hero_text": "TACAI Portal 是 Employee Mgmt、Timesheet、Payroll、Expense、Message Center、User Management 等业务模块的统一入口。页面只会显示 User Management 权限设置允许你访问的模块。",
        "dashboard.empty": "当前没有可用模块。请联系系统管理员。",
        "logout": "退出登录",
        "future_module.eyebrow": "模块入口",
        "future_module.title_suffix": "TACAI Portal",
        "future_module.reserved": "此模块入口已预留",
        "future_module.text": "该页面用于保持 Portal 导航结构完整，并为后续模块集成做好准备。",
        "back_dashboard": "返回仪表盘",
        "not_found.title": "页面不存在",
        "not_found.text": "请求的 Portal 页面不存在。",
        "forbidden.title": "访问被拒绝",
        "forbidden.text": "请求来源未通过本地安全检查，操作已被拒绝。",
        "language.label": "显示语言",
        "entity.current": "当前法人",
        "entity.required.title": "需要法人上下文",
        "entity.required.text": "当前会话没有法人信息。请从 User Management 使用法人代码重新登录。",
    },
    "en": {
        "app.title": "TACAI Portal",
        "app.subtitle": "Unified entry point for TACAI business modules",
        "login.title": "TACAI Portal",
        "login.subtitle": "A secure unified login entry for TACAI business systems.",
        "login.auth_note": "Authentication is handled by TACAI User Management. After sign-in, Portal shows only the modules allowed by your permissions.",
        "login.button": "Sign in with TACAI User Management",
        "login.hint": "After login, User Management returns you to the Portal dashboard.",
        "unavailable.title": "User Management is unavailable",
        "unavailable.subtitle": "Portal validates your login through User_admin, but the service is not reachable right now.",
        "unavailable.hint": "For local testing, start User_admin first with the command below.",
        "unavailable.retry": "Retry Portal",
        "dashboard.eyebrow": "Unified Entry",
        "dashboard.title": "Dashboard",
        "dashboard.hero_title": "Welcome to TACAI Portal",
        "dashboard.hero_text": "TACAI Portal is the unified entry point for Employee Mgmt, Timesheet, Payroll, Expense, Message Center, User Management, and other TACAI modules. The modules shown here are filtered by User Management permissions.",
        "dashboard.empty": "No available modules. Please contact a system administrator.",
        "logout": "Logout",
        "future_module.eyebrow": "Module Entry",
        "future_module.title_suffix": "TACAI Portal",
        "future_module.reserved": "This module entry is ready",
        "future_module.text": "This page keeps the Portal navigation structure ready for future module integration.",
        "back_dashboard": "Back to dashboard",
        "not_found.title": "Page not found",
        "not_found.text": "The requested Portal page does not exist.",
        "forbidden.title": "Access denied",
        "forbidden.text": "The request origin could not be verified, so the action was rejected.",
        "language.label": "Language",
        "entity.current": "Current Entity",
        "entity.required.title": "Entity context required",
        "entity.required.text": "This session does not include Entity context. Please sign in again through User Management with an Entity Code.",
    },
}

DEFAULT_MODULES = [
    {
        "module_key": "dashboard",
        "label": "Dashboard",
        "labels": {"ja": "ダッシュボード", "zh": "仪表盘", "en": "Dashboard"},
        "description": "統合ダッシュボード / Unified dashboard",
        "descriptions": {
            "ja": "TACAI モジュールの統合ホーム",
            "zh": "TACAI 模块统一首页",
            "en": "Unified home for TACAI modules",
        },
        "url": "/dashboard",
        "status": "Portal home",
        "statuses": {"ja": "Portal ホーム", "zh": "Portal 首页", "en": "Portal home"},
        "required_permission": "",
        "enabled": True,
    },
    {
        "module_key": "tacaimsg",
        "label": "Message Center",
        "labels": {"ja": "メッセージセンター", "zh": "消息中心", "en": "Message Center"},
        "description": "メッセージ通知・承認ワークフロー",
        "descriptions": {
            "ja": "メッセージ受信箱、承認ワークフロー、通知管理",
            "zh": "消息收件箱、审批工作流、通知管理",
            "en": "Message inbox, approval workflows, and notification management",
        },
        "url": f"{TACAIMSG_BASE_URL}/dashboard",
        "status": "Connected module",
        "statuses": {"ja": "連携済み", "zh": "已连接模块", "en": "Connected module"},
        "required_permission": "tacaimsg.access",
        "enabled": True,
    },
    {
        # TODO: Self-service backend is not yet implemented (port 8018).
        # Disabled until the service is deployed. See config.py / start_tacai_lan.sh.
        "module_key": "selfservice",
        "label": "Employee Self-Service",
        "labels": {"ja": "従業員セルフサービス", "zh": "员工自助", "en": "Employee Self-Service"},
        "description": "休暇申請・承認管理",
        "descriptions": {
            "ja": "休暇申請（私用・病気・振替）、上司承認、HR承認、自動タイムアウト",
            "zh": "请假申请（事假/病假/调休）、主管审批、HR审批、超时自动处理",
            "en": "Leave requests (personal/sick/compensatory), supervisor approval, HR approval, auto-timeout",
        },
        "url": f"{public_base_url('SELFSERVICE_PUBLIC_BASE_URL', 8018)}/dashboard",
        "status": "Planned",
        "statuses": {"ja": "計画中", "zh": "计划中", "en": "Planned"},
        "required_permission": "selfservice.access",
        "enabled": False,
    },
    {
        "module_key": "employee_management",
        "label": "Employee Mgmt",
        "labels": {"ja": "従業員管理", "zh": "员工管理", "en": "Employee Mgmt"},
        "description": "従業員マスタ管理・入社手続き",
        "descriptions": {
            "ja": "従業員情報の一元管理、入社オンボーディング、書類管理、レポート",
            "zh": "员工信息统一管理、入职流程、文档管理、报表",
            "en": "Centralized employee master data, onboarding, document management, and reports",
        },
        "url": "/employees",
        "status": "Connected module",
        "statuses": {"ja": "連携済み", "zh": "已连接模块", "en": "Connected module"},
        "required_permission": "employee_management.access",
        "enabled": True,
    },
    {
        "module_key": "masterdata",
        "label": "Master Data",
        "labels": {"ja": "マスタデータ管理", "zh": "主数据管理", "en": "Master Data"},
        "description": "法人・部門・チームの組織マスタ管理",
        "descriptions": {
            "ja": "法人、部門、チームの組織マスタデータを一元的に管理",
            "zh": "统一管理法人、部门、团队组织主数据",
            "en": "Centralized management of Entity, Department, and Team master data",
        },
        "url": "/entities",
        "status": "Connected module",
        "statuses": {"ja": "連携済み", "zh": "已连接模块", "en": "Connected module"},
        "required_permission": "masterdata.access",
        "enabled": True,
    },
    {
        "module_key": "user_management",
        "label": "User Management",
        "labels": {"ja": "ユーザー管理", "zh": "用户管理", "en": "User Management"},
        "description": "ユーザー・ロール・権限管理",
        "descriptions": {
            "ja": "ユーザー、ロール、権限、セッションを管理",
            "zh": "管理用户、角色、权限和会话",
            "en": "Manage users, roles, permissions, and sessions",
        },
        "url": f"{USER_ADMIN_BASE_URL}/dashboard",
        "status": "Connected module",
        "statuses": {"ja": "連携済み", "zh": "已连接模块", "en": "Connected module"},
        "required_permission": "user_management.access",
        "enabled": True,
    },
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path, default):
    """Read records from PostgreSQL. Table name = MODULE_PREFIX + filename stem."""
    table_name = f"{MODULE_PREFIX}_{path.stem}"
    try:
        result = _db.load_table(table_name)
        return result if result is not None else default
    except Exception:
        print(f"[tacai-portal] ERROR loading table {table_name}", file=_sys.stderr)
        return default


def get_msg_center_unread_count(user_id: str) -> int:
    """Count unread messages for a user via targeted DB query.

    Uses parameterized WHERE clause to avoid loading all messages into memory.
    TODO: Replace with GET /api/internal/messages/unread-count?user_id=...
          once messaging service exposes an internal (no-auth) endpoint.
    """
    try:
        rows = _db.load_table(
            f"{MSG_PREFIX}_messages",
            where={"recipient_user_id": str(user_id), "status": "unread"},
        )
        return len(rows)
    except Exception:
        print("[tacai-portal] WARNING: Could not count unread messages", file=_sys.stderr)
        return 0


def normalize_lang(value: str | None) -> str:
    if value in SUPPORTED_LANGUAGES:
        return value
    return DEFAULT_LANGUAGE


def translate(lang: str, key: str) -> str:
    normalized = normalize_lang(lang)
    return TRANSLATIONS.get(normalized, {}).get(key) or TRANSLATIONS["en"].get(key, key)


def localized_value(item: dict, plural_field: str, fallback_field: str, lang: str) -> str:
    values = item.get(plural_field, {})
    if isinstance(values, dict):
        value = values.get(normalize_lang(lang)) or values.get("en") or values.get(DEFAULT_LANGUAGE)
        if value:
            return str(value)
    return str(item.get(fallback_field, ""))


def module_label(item: dict, lang: str) -> str:
    return localized_value(item, "labels", "label", lang)


def module_description(item: dict, lang: str) -> str:
    return localized_value(item, "descriptions", "description", lang)


def module_status(item: dict, lang: str) -> str:
    return localized_value(item, "statuses", "status", lang)


def current_entity(user: dict) -> dict:
    entity = user.get("entity") if isinstance(user.get("entity"), dict) else {}
    if entity:
        return entity
    entity_id = str(user.get("entity_id", "")).strip()
    entity_code = str(user.get("entity_code", "")).strip()
    if not entity_id or not entity_code:
        return {}
    return {
        "entity_id": entity_id,
        "entity_code": entity_code,
        "entity_name_en": str(user.get("entity_name", "")),
    }


def has_entity_context(user: dict | None) -> bool:
    entity = current_entity(user or {})
    return bool(entity.get("entity_id") and entity.get("entity_code"))


def current_entity_label(user: dict, lang: str = DEFAULT_LANGUAGE) -> str:
    entity = current_entity(user)
    entity_code = str(entity.get("entity_code", "")).strip()
    entity_name = str(entity.get(f"entity_name_{normalize_lang(lang)}") or entity.get("entity_name_en") or entity.get("entity_name") or "").strip()
    if entity_code and entity_name:
        return f"{entity_code} - {entity_name}"
    return entity_code or entity_name


def with_lang(path_or_url: str, lang: str) -> str:
    normalized = normalize_lang(lang)
    parsed = urlparse(path_or_url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    query["lang"] = [normalized]
    return parsed._replace(query=urlencode(query, doseq=True)).geturl()


def public_local_url(url: str, request_host: str | None = None) -> str:
    parsed = urlparse(url)
    if parsed.scheme in {"http", "https"} and parsed.hostname in {"127.0.0.1", "localhost"} and parsed.port in LOCAL_ALLOWED_PORTS:
        # When the user accesses via 127.0.0.1 / localhost, keep module links
        # on 127.0.0.1 so session cookies (host-scoped) continue to work.
        if request_host and request_host in {"127.0.0.1", "localhost"}:
            return parsed._replace(netloc=f"127.0.0.1:{parsed.port}").geturl()
        env_by_port = {
            # Planned / future services (not yet deployed)
            8000: "INTERVIEW_READY_PUBLIC_BASE_URL",   # planned
            8001: "PAYROLL_PUBLIC_BASE_URL",            # planned
            8002: "TIMESHEET_PUBLIC_BASE_URL",          # planned
            8003: "EXPENSE_PUBLIC_BASE_URL",             # planned
            8016: "TACAIPAYSG_PUBLIC_BASE_URL",          # planned (SG payroll)
            8018: "SELFSERVICE_PUBLIC_BASE_URL",         # planned
            # Active shared services
            8004: "EMPLOYEE_ADMIN_PUBLIC_BASE_URL",
            8005: "DATADICT_PUBLIC_BASE_URL",
            8007: "MASTERDATA_PUBLIC_BASE_URL",
            8012: "TACAIMSG_PUBLIC_BASE_URL",
            # Dynamic per-environment ports
            **{_PORTAL_FALLBACK_PORT: "PORTAL_PUBLIC_BASE_URL", _AUTH_FALLBACK_PORT: "USER_ADMIN_PUBLIC_BASE_URL"},
        }
        env_name = env_by_port.get(parsed.port)
        if env_name and os.environ.get(env_name, "").strip():
            base = os.environ[env_name].strip().rstrip("/")
            path = parsed.path if parsed.path else ""
            return f"{base}{path}" + (("?" + parsed.query) if parsed.query else "")
        return parsed._replace(netloc=f"{TACAI_PUBLIC_HOST}:{parsed.port}").geturl()
    return url


def _resolve_host(request_host: str | None = None) -> str:
    """Return the effective host for public-facing URLs.

    When the user accesses via 127.0.0.1 / localhost, keep all links on
    127.0.0.1 so session cookies (host-scoped) continue to work.
    Otherwise use the configured TACAI_PUBLIC_HOST (LAN IP) for cross-device
    access.
    """
    if request_host and request_host in {"127.0.0.1", "localhost"}:
        return "127.0.0.1"
    return TACAI_PUBLIC_HOST


def portal_url(path: str, lang: str, request_host: str | None = None) -> str:
    host = _resolve_host(request_host)
    port = urlparse(PORTAL_BASE_URL).port or 8005
    return f"http://{host}:{port}{with_lang(path, lang)}"


# ── Vue 3 SPA frontend login URL (unified single login page) ──

VUE_DEV_SERVER_URL = os.environ.get("VUE_DEV_SERVER_URL", "http://localhost:5173").rstrip("/")


def vue_login_url(lang: str, redirect_path: str | None = None) -> str:
    """Return the Vue 3 SPA login page URL (unified single login page)."""
    params: dict[str, str] = {"lang": normalize_lang(lang)}
    if redirect_path:
        params["redirect"] = redirect_path
    qs = urlencode(params)
    return f"{VUE_DEV_SERVER_URL}/login?{qs}"


def user_admin_login_url(lang: str, request_host: str | None = None) -> str:
    """Deprecated — login now handled by Vue 3 SPA. Use vue_login_url()."""
    return vue_login_url(lang, "/dashboard")


def user_admin_logout_url(lang: str, request_host: str | None = None) -> str:
    """Logout via User_admin, then redirect to Vue 3 SPA login."""
    host = _resolve_host(request_host)
    port = urlparse(USER_ADMIN_BASE_URL).port or 8006
    base = f"http://{host}:{port}"
    next_url = vue_login_url(lang)
    return f"{base}/logout?next={quote(next_url, safe='')}"


def language_switcher(current_path: str, lang: str) -> str:
    parsed = urlparse(current_path)
    query = parse_qs(parsed.query, keep_blank_values=True)
    links = []
    for code in ("ja", "zh", "en"):
        query["lang"] = [code]
        href = parsed.path + "?" + urlencode(query, doseq=True)
        classes = "active" if code == normalize_lang(lang) else ""
        links.append(
            f'<a class="{classes}" href="{html.escape(href)}">{html.escape(LANGUAGE_LABELS[code])}</a>'
        )
    return f"""
    <div class="language-switcher" aria-label="{html.escape(translate(lang, 'language.label'))}">
      <span>{html.escape(translate(lang, 'language.label'))}</span>
      {' '.join(links)}
    </div>
    """


def load_modules(request_host: str | None = None) -> list[dict]:
    modules = read_json(MODULES_FILE, DEFAULT_MODULES)
    if not isinstance(modules, list):
        return DEFAULT_MODULES
    normalized = []
    for item in modules:
        if not isinstance(item, dict) or not item.get("enabled", True):
            continue
        normalized.append(
            {
                "module_key": str(item.get("module_key", "")),
                "label": str(item.get("label", "")),
                "labels": item.get("labels", {}) if isinstance(item.get("labels", {}), dict) else {},
                "description": str(item.get("description", "")),
                "descriptions": item.get("descriptions", {}) if isinstance(item.get("descriptions", {}), dict) else {},
                "url": public_local_url(str(item.get("url", "#")), request_host),
                "status": str(item.get("status", "")),
                "statuses": item.get("statuses", {}) if isinstance(item.get("statuses", {}), dict) else {},
                "required_permission": str(item.get("required_permission", "")),
                "enabled": bool(item.get("enabled", True)),
            }
        )
    return normalized or DEFAULT_MODULES


def visible_modules_for(user: dict, request_host: str | None = None) -> list[dict]:
    permissions = set(user.get("permissions", []))
    roles = set(user.get("roles", []))
    is_system_admin = "system_admin" in roles
    visible = []
    for item in load_modules(request_host):
        required_permission = item.get("required_permission", "")
        if not required_permission or is_system_admin or required_permission in permissions:
            visible.append(item)
    return visible


def write_json(path: Path, data) -> None:
    """Write records to PostgreSQL. Table name = MODULE_PREFIX + filename stem."""
    table_name = f"{MODULE_PREFIX}_{path.stem}"
    try:
        _db.save_table(table_name, data)
    except Exception:
        print(f"[tacai-portal] ERROR saving table {table_name}", file=_sys.stderr)
        raise


def append_audit_log(
    *,
    record_id: str,
    action: str,
    user: str,
    before_value,
    after_value,
) -> None:
    logs = read_json(AUDIT_LOG_FILE, [])
    logs.append(
        {
            "module": MODULE_NAME,
            "record_id": record_id,
            "action": action,
            "user": user,
            "timestamp": utc_now_iso(),
            "before_value": before_value,
            "after_value": after_value,
        }
    )
    write_json(AUDIT_LOG_FILE, logs)


def page_shell(title: str, body: str, lang: str = DEFAULT_LANGUAGE) -> str:
    return f"""<!doctype html>
<html lang="{html.escape(normalize_lang(lang))}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="/static/app.css">
</head>
<body>
{body}
</body>
</html>
"""


def user_admin_available() -> bool:
    try:
        with urlopen(f"{USER_ADMIN_INTERNAL_BASE_URL}/health", timeout=2) as response:
            return response.read().decode("utf-8").strip() == "OK"
    except (OSError, URLError):
        return False


def render_user_admin_unavailable(lang: str, current_path: str) -> str:
    body = f"""
<main class="login-page">
  <section class="login-card">
    <div class="brand-mark">TACAI</div>
    {language_switcher(current_path, lang)}
    <h1>{html.escape(translate(lang, 'unavailable.title'))}</h1>
    <p class="muted">{html.escape(translate(lang, 'unavailable.subtitle'))}</p>
    <p class="hint">{html.escape(translate(lang, 'unavailable.hint'))}</p>
    <pre>cd TACAI-Core/User_admin
python3 backend/app.py --host 127.0.0.1 --port ${{AUTH_PORT:-3001}}</pre>
    <p><a class="button-link" href="{html.escape(with_lang('/', lang))}">{html.escape(translate(lang, 'unavailable.retry'))}</a></p>
  </section>
</main>
"""
    return page_shell(translate(lang, "unavailable.title"), body, lang)


def validate_user_admin_session(session_id: str) -> dict | None:
    if not session_id:
        return None
    payload = json.dumps({"session_id": session_id}).encode("utf-8")
    request = Request(
        f"{USER_ADMIN_INTERNAL_BASE_URL}/api/validate-session",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, json.JSONDecodeError):
        return None
    if data.get("valid") and isinstance(data.get("user"), dict):
        user = data["user"]
        if isinstance(data.get("session"), dict):
            user["_session"] = data["session"]
        # user_admin's user_context() already resolves roles and permissions
        # via active_user_role_keys() and effective_permissions() — no need
        # for portal to re-read ua_* tables from the database.
        return user
    return None


def render_login(lang: str, current_path: str, error: str = "", request_host: str | None = None) -> str:
    error_html = f'<div class="alert">{html.escape(error)}</div>' if error else ""
    body = f"""
<main class="login-page">
  <section class="login-card">
    <div class="brand-mark">TACAI</div>
    {language_switcher(current_path, lang)}
    <h1>{html.escape(translate(lang, 'login.title'))}</h1>
    <p class="muted">{html.escape(translate(lang, 'login.subtitle'))}</p>
    {error_html}
    <p class="muted">{html.escape(translate(lang, 'login.auth_note'))}</p>
    <p><a class="button-link" href="{html.escape(user_admin_login_url(lang, request_host))}">{html.escape(translate(lang, 'login.button'))}</a></p>
    <p class="hint">{html.escape(translate(lang, 'login.hint'))}</p>
  </section>
</main>
"""
    return page_shell(translate(lang, "login.title"), body, lang)


def current_user_chip(user: dict, lang: str) -> str:
    session = user.get("_session") if isinstance(user.get("_session"), dict) else {}
    account = user.get("username") or user.get("email") or user.get("display_name") or "user"
    display_name = user.get("display_name") or account
    entity_code = user.get("entity_code") or session.get("entity", {}).get("entity_code", "")
    login_time = session.get("login_time_jst") or session.get("login_time") or "-"
    return f'''
    <div class="current-user-chip" title="Login: {html.escape(str(login_time))}">
      <strong>👤 {html.escape(str(account))}</strong>
      <span>{html.escape(str(display_name))}{(' · ' + html.escape(str(entity_code))) if entity_code else ''}</span>
      <small>Login: {html.escape(str(login_time))}</small>
    </div>
    '''


def render_dashboard(user: dict, lang: str, current_path: str, request_host: str | None = None) -> str:
    user_id = str(user.get("user_id", ""))
    unread_count = get_msg_center_unread_count(user_id)
    modules = visible_modules_for(user, request_host)
    cards = "\n".join(
        f"""
      <a class="module-card" href="{html.escape(with_lang(item['url'], lang))}">
        <span class="status">{html.escape(module_status(item, lang))}</span>
        <strong>{html.escape(module_label(item, lang))}{' <span style="background:#dc2626;color:#fff;border-radius:12px;padding:1px 8px;font-size:0.75rem;margin-left:6px;font-weight:700">' + str(unread_count) + '</span>' if item.get('module_key') == 'tacaimsg' and unread_count > 0 else ''}</strong>
        <small>{html.escape(module_description(item, lang))}</small>
      </a>
"""
        for item in modules
    )
    if not cards:
        cards = f'<div class="empty-state">{html.escape(translate(lang, "dashboard.empty"))}</div>'
    entity_label = current_entity_label(user, lang)
    entity_html = f'<span class="signed-in">{html.escape(translate(lang, "entity.current"))}: {html.escape(entity_label)}</span>' if entity_label else ""
    nav = "\n".join(
        f'<a href="{html.escape(with_lang(item["url"], lang))}">{html.escape(module_label(item, lang))}{" 🔴" if item.get("module_key") == "tacaimsg" and unread_count > 0 else ""}</a>' for item in modules
    )
    # Unread badge in header
    unread_badge = ""
    if unread_count > 0:
        unread_badge = f'<a href="{html.escape(with_lang(TACAIMSG_BASE_URL + "/messages/inbox", lang))}" style="background:#dc2626;color:#fff;border-radius:20px;padding:4px 12px;text-decoration:none;font-weight:700;font-size:0.85rem;display:inline-flex;align-items:center;gap:4px" title="Unread messages">📬 {unread_count}</a>'
    body = f"""
<div class="app-shell">
  <aside class="sidebar">
    <div class="sidebar-title">{html.escape(translate(lang, 'app.title'))}</div>
    <p class="sidebar-subtitle">{html.escape(translate(lang, 'app.subtitle'))}</p>
    <nav>
      {nav}
    </nav>
  </aside>
  <main class="content">
    <header class="topbar">
      <div>
        <p class="eyebrow">{html.escape(translate(lang, 'dashboard.eyebrow'))}</p>
        <h1>{html.escape(translate(lang, 'dashboard.title'))}</h1>
      </div>
      <div class="topbar-actions">
        {unread_badge}
        {entity_html}
        {language_switcher(current_path, lang)}
        {current_user_chip(user, lang)}
        <form method="post" action="{user_admin_logout_url(lang, request_host)}">
          <button class="secondary" type="submit">{html.escape(translate(lang, 'logout'))}</button>
        </form>
      </div>
    </header>
    <section class="hero">
      <h2>{html.escape(translate(lang, 'dashboard.hero_title'))}</h2>
      <p>{html.escape(translate(lang, 'dashboard.hero_text'))}</p>
    </section>
    <section class="module-grid">
      {cards}
    </section>
  </main>
</div>
"""
    return page_shell(translate(lang, "dashboard.title"), body, lang)


def render_module_placeholder(user: dict, module_key: str, lang: str, current_path: str, request_host: str | None = None) -> str:
    modules = visible_modules_for(user, request_host)
    item = next((nav_item for nav_item in modules if nav_item["module_key"] == module_key), None)
    title = module_label(item, lang) if item else module_key.replace("-", " ").replace("_", " ").title()
    entity_label = current_entity_label(user, lang)
    entity_html = f'<span class="signed-in">{html.escape(translate(lang, "entity.current"))}: {html.escape(entity_label)}</span>' if entity_label else ""
    nav = "\n".join(
        f'<a href="{html.escape(with_lang(nav_item["url"], lang))}">{html.escape(module_label(nav_item, lang))}</a>' for nav_item in modules
    )
    body = f"""
<div class="app-shell">
  <aside class="sidebar">
    <div class="sidebar-title">{html.escape(translate(lang, 'app.title'))}</div>
    <p class="sidebar-subtitle">{html.escape(translate(lang, 'app.subtitle'))}</p>
    <nav>
      {nav}
    </nav>
  </aside>
  <main class="content">
    <header class="topbar">
      <div>
        <p class="eyebrow">{html.escape(translate(lang, 'future_module.eyebrow'))}</p>
        <h1>{html.escape(title)}</h1>
      </div>
      <div class="topbar-actions">
        {entity_html}
        {language_switcher(current_path, lang)}
        {current_user_chip(user, lang)}
        <form method="post" action="{user_admin_logout_url(lang, request_host)}">
          <button class="secondary" type="submit">{html.escape(translate(lang, 'logout'))}</button>
        </form>
      </div>
    </header>
    <section class="hero">
      <h2>{html.escape(translate(lang, 'future_module.reserved'))}</h2>
      <p>{html.escape(translate(lang, 'future_module.text'))}</p>
      <p><a href="{html.escape(with_lang('/dashboard', lang))}">{html.escape(translate(lang, 'back_dashboard'))}</a></p>
    </section>
  </main>
</div>
"""
    return page_shell(f"{title} - {translate(lang, 'future_module.title_suffix')}", body, lang)


def render_entity_required(lang: str, request_host: str | None = None) -> str:
    body = f"""
<main class="login-page">
  <section class="login-card">
    <div class="brand-mark">TACAI</div>
    <h1>{html.escape(translate(lang, 'entity.required.title'))}</h1>
    <p class="muted">{html.escape(translate(lang, 'entity.required.text'))}</p>
    <p><a class="button-link" href="{html.escape(user_admin_logout_url(lang, request_host))}">{html.escape(translate(lang, 'logout'))}</a></p>
  </section>
</main>
"""
    return page_shell(translate(lang, "entity.required.title"), body, lang)


def render_simple_page(lang: str, title_key: str, text_key: str, status: HTTPStatus) -> tuple[str, HTTPStatus]:
    title = translate(lang, title_key)
    body = f"""
<main class="login-page">
  <section class="login-card">
    <div class="brand-mark">TACAI</div>
    <h1>{html.escape(title)}</h1>
    <p class="muted">{html.escape(translate(lang, text_key))}</p>
    <p><a class="button-link" href="{html.escape(with_lang('/', lang))}">{html.escape(translate(lang, 'back_dashboard'))}</a></p>
  </section>
</main>
"""
    return page_shell(title, body, lang), status


# ── API Gateway: forward requests to internal backend services ──

def _proxy_to_service(target_port: int, path: str, method: str = "GET",
                       req_headers: dict | None = None, body: bytes | None = None,
                       timeout: int = 30) -> tuple[int, dict, bytes]:
    """Forward an API request to an internal backend service.

    Returns (status_code, response_headers_dict, response_body_bytes).
    On connection failure returns (502, {}, error_json_bytes).
    """
    import urllib.request as _ur
    from urllib.error import HTTPError

    target_url = f"http://127.0.0.1:{target_port}{path}"
    try:
        req = _ur.Request(target_url, data=body, method=method)
        # Forward relevant headers
        if req_headers:
            for header in ("Content-Type", "Accept", "Accept-Language", "Cookie", "Authorization", "X-Requested-With"):
                val = req_headers.get(header)
                if val:
                    req.add_header(header, val)
        with _ur.urlopen(req, timeout=timeout) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except HTTPError as e:
        # HTTP error from upstream — relay it
        return e.code, dict(e.headers), e.read()
    except Exception:
        return 502, {"Content-Type": "application/json"}, b'{"error":"Bad Gateway","message":"Backend service unavailable"}'


class PortalHandler(BaseHTTPRequestHandler):
    server_version = "TACAIPortal/0.1"

    # === CORS support via shared cors_middleware ===

    def do_OPTIONS(self) -> None:
        handle_preflight(self)

    def csrf_origin_allowed(self) -> bool:
        source = self.headers.get("Origin") or self.headers.get("Referer")
        if not source:
            return True
        parsed = urlparse(source)
        host = (parsed.hostname or "").lower()
        if host in LOCAL_ALLOWED_HOSTS and parsed.port in LOCAL_ALLOWED_PORTS:
            return True
        return parsed.scheme == "https" and host in PUBLIC_ALLOWED_HOSTS and parsed.port in {None, 443}

    def log_message(self, format: str, *args) -> None:  # noqa: A002 - inherited API name
        return

    @property
    def request_host(self) -> str:
        """Return the request Host header hostname (without port)."""
        raw = self.headers.get("Host", "")
        return raw.split(":", 1)[0] if raw else "127.0.0.1"

    def language_from_request(self, parsed) -> str:
        query = parse_qs(parsed.query, keep_blank_values=True)
        query_lang = query.get("lang", [None])[0]
        if query_lang in SUPPORTED_LANGUAGES:
            return query_lang
        cookie_header = self.headers.get("Cookie", "")
        cookies = SimpleCookie(cookie_header)
        lang_cookie = cookies.get(LANGUAGE_COOKIE)
        if lang_cookie:
            return normalize_lang(lang_cookie.value)
        return DEFAULT_LANGUAGE

    def current_user(self) -> dict | None:
        cookie_header = self.headers.get("Cookie", "")
        cookies = SimpleCookie(cookie_header)
        session_cookie = cookies.get(USER_ADMIN_SESSION_COOKIE)
        if not session_cookie:
            return None
        return validate_user_admin_session(session_cookie.value)

    def send_html(self, html_text: str, status: HTTPStatus = HTTPStatus.OK, lang: str = DEFAULT_LANGUAGE) -> None:
        payload = html_text.encode("utf-8")
        self.send_response(status)
        add_cors_headers(self)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Set-Cookie", f"{LANGUAGE_COOKIE}={normalize_lang(lang)}; SameSite=Lax; Path=/")
        self.end_headers()
        self.wfile.write(payload)

    def send_json(self, data: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        add_cors_headers(self)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def redirect(self, location: str, lang: str = DEFAULT_LANGUAGE) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        add_cors_headers(self)
        self.send_header("Location", location)
        self.send_header("Set-Cookie", f"{LANGUAGE_COOKIE}={normalize_lang(lang)}; SameSite=Lax; Path=/")
        self.end_headers()

    def require_user(self, lang: str, current_path: str) -> dict | None:
        user = self.current_user()
        rh = self.request_host
        if user and has_entity_context(user):
            return user
        if user and not has_entity_context(user):
            self.send_html(render_entity_required(lang, rh), HTTPStatus.FORBIDDEN, lang)
            return None
        if not user_admin_available():
            self.send_html(render_user_admin_unavailable(lang, current_path), HTTPStatus.SERVICE_UNAVAILABLE, lang)
            return None
        self.redirect(vue_login_url(lang, current_path), lang)
        return None

    # ── API Gateway: forward /api/* requests to internal services ──

    def _proxy_gateway(self, method: str = "GET") -> bool:
        """Check if the request path matches a gateway route and proxy it.

        Returns True if the request was handled (gateway route matched),
        False if no gateway route matched (caller should fall through).
        """
        # Normalize: strip query string so /api/employees?page=1 matches /api/employees/
        parsed = urlparse(self.path)
        path_only = parsed.path

        for prefix, port in GATEWAY_ROUTES.items():
            # Match either exact path (without trailing slash) or path with sub-routes
            if path_only == prefix.rstrip('/') or path_only.startswith(prefix):
                # Read body for write methods
                body = None
                if method in ("POST", "PUT", "PATCH"):
                    length = int(self.headers.get("Content-Length", "0") or "0")
                    body = self.rfile.read(length) if length else None

                # Longer timeout for file uploads
                timeout = 120 if path_only.startswith("/api/employees/import") else 30

                status, resp_headers, resp_body = _proxy_to_service(
                    port, self.path, method,
                    req_headers=dict(self.headers),
                    body=body, timeout=timeout,
                )

                # Relay response
                self.send_response(status)
                add_cors_headers(self)
                skip = {"connection", "keep-alive", "transfer-encoding",
                        "proxy-authenticate", "proxy-authorization", "te", "trailers"}
                for key, val in resp_headers.items():
                    if key.lower() in skip:
                        continue
                    self.send_header(key, val)
                self.end_headers()
                self.wfile.write(resp_body)
                return True
        return False

    def _proxy_to_vite(self, method: str = "GET") -> bool:
        """Proxy the current request to the Vite dev server. Returns True on success, False only if Vite is unreachable (connection refused)."""
        import urllib.request as _ur
        from urllib.error import HTTPError
        vite_url = f"{VUE_DEV_SERVER_URL}{self.path}"
        body = None
        if method in ("POST", "PUT", "PATCH"):
            length = int(self.headers.get("Content-Length", "0") or "0")
            body = self.rfile.read(length) if length else None
        req = _ur.Request(vite_url, data=body, method=method)
        for header in ("Content-Type", "Accept", "Accept-Language", "Cookie", "User-Agent"):
            val = self.headers.get(header)
            if val:
                req.add_header(header, val)
        try:
            with _ur.urlopen(req, timeout=30) as resp:
                status = resp.status
                resp_headers = dict(resp.headers)
                resp_body = resp.read()
        except HTTPError as e:
            # HTTP 4xx/5xx are valid responses — relay them, not a proxy failure
            status = e.code
            resp_headers = dict(e.headers)
            resp_body = e.read()
        except URLError:
            # Connection refused / DNS failure — Vite is down
            return False
        except Exception:
            return False
        # Relay response
        self.send_response(status)
        skip_headers = {"connection", "keep-alive", "transfer-encoding", "proxy-authenticate", "proxy-authorization", "te", "trailers"}
        for key, val in resp_headers.items():
            if key.lower() in skip_headers:
                continue
            self.send_header(key, val)
        self.end_headers()
        self.wfile.write(resp_body)
        return True

    def _serve_static_fallback(self) -> None:
        """Serve the Vue 3 SPA from built static files (frontend/dist/)."""
        FRONTEND_DIST = Path(__file__).resolve().parents[5] / "frontend" / "dist"
        parsed = urlparse(self.path)
        req_path = parsed.path.lstrip("/")

        # /assets/* → static files
        if req_path.startswith("assets/") and FRONTEND_DIST.exists():
            asset_path = FRONTEND_DIST / req_path
            if asset_path.is_file():
                content = asset_path.read_bytes()
                suffix = asset_path.suffix
                ct_map = {".css": "text/css", ".js": "application/javascript", ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon", ".woff2": "font/woff2"}
                content_type = ct_map.get(suffix, "application/octet-stream")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return

        # SPA fallback: serve index.html for all non-asset routes
        index_path = FRONTEND_DIST / "index.html"
        if index_path.exists():
            content = index_path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

        # Nothing works
        self.send_html(
            render_simple_page("en", "unavailable.title", "unavailable.text", HTTPStatus.SERVICE_UNAVAILABLE)[0],
            HTTPStatus.SERVICE_UNAVAILABLE, "en",
        )

    def _serve_or_proxy(self, method: str = "GET") -> None:
        """Try Vite proxy first; fall back to static built files if Vite is down."""
        if self._proxy_to_vite(method):
            return
        self._serve_static_fallback()

    def do_GET(self) -> None:  # noqa: N802 - inherited API name
        parsed = urlparse(self.path)
        path = parsed.path
        lang = self.language_from_request(parsed)

        # ── Portal-specific API routes ──
        if path == "/health":
            self.send_json({"status": "ok", "module": MODULE_NAME})
            return

        if path == "/api/portal/modules":
            user = self.current_user()
            modules_data = visible_modules_for(user or {}, self.request_host)
            response: dict = {"modules": modules_data}
            if user:
                response["unread_count"] = get_msg_center_unread_count(str(user.get("user_id", "")))
            self.send_json(response)
            return

        if path == "/api/portal/health":
            self.send_json({"status": "ok", "module": MODULE_NAME})
            return

        if path == "/static/app.css":
            css_path = FRONTEND_DIR / "app.css"
            payload = css_path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/css; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        # ── API Gateway: forward to internal backend services ──
        if self._proxy_gateway("GET"):
            return

        # ── All other requests → Vue 3 SPA (proxy to Vite dev or serve built dist) ──
        self._serve_or_proxy("GET")

    def do_POST(self) -> None:  # noqa: N802 - inherited API name
        parsed = urlparse(self.path)
        path = parsed.path
        lang = self.language_from_request(parsed)

        # ── Portal-specific POST routes (logout) ──
        if path == "/logout":
            self.redirect(user_admin_logout_url(lang, self.request_host), lang)
            return

        # ── API Gateway: forward to internal backend services ──
        if self._proxy_gateway("POST"):
            return

        # ── All other POST requests → Vue 3 SPA (proxy to Vite dev) ──
        self._serve_or_proxy("POST")

    def do_PUT(self) -> None:  # noqa: N802 - inherited API name
        # ── API Gateway: forward to internal backend services ──
        if self._proxy_gateway("PUT"):
            return
        # ── All other PUT requests → proxy to backend ──
        self._serve_or_proxy("PUT")

    def do_DELETE(self) -> None:  # noqa: N802 - inherited API name
        # ── API Gateway: forward to internal backend services ──
        if self._proxy_gateway("DELETE"):
            return
        self.send_response(405)
        self.end_headers()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run TACAI Portal local app")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "3000")))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), PortalHandler)
    print(f"TACAI Portal running on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping TACAI Portal")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
