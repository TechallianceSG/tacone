# CLAUDE.md

This file provides guidance to Claude Code when working in `/Users/terencewang/Documents/claude-project/TACAI-Core/tacai-portal`.

Project Name: tacai-portal

Before any task:

1. Confirm current project root.
2. Confirm using this project's CLAUDE.md.
3. Do not access sibling projects unless explicitly requested.
4. Do not load memory from other projects.

## Purpose

`tacai-portal` is the future unified login window for TACAI modules.

Primary navigation:

- Dashboard
- Employee Mgmt
- Timesheet
- Payroll
- Expense
- Vendor Payments
- User Management

## Commands

Run locally:

```bash
cd /Users/terencewang/Documents/claude-project/TACAI-Core/tacai-portal
python3 backend/app.py --host 127.0.0.1 --port 3000
```

Health check:

```bash
curl -s http://127.0.0.1:3000/health
```

> Port is environment-aware: 3000 (DEV) / 4000 (STG) / 6000 (PRD).
> Default reads the `PORT` env var; see `TACAI-Core/tacai_config.py` for the single source of truth.

Syntax check:

```bash
cd /Users/terencewang/Documents/claude-project/TACAI-Core/tacai-portal
python3 -m py_compile backend/app.py
```

## Architecture

- `backend/app.py` is a Python standard-library local web app.
- `frontend/app.css` stores the current portal UI styles.
- Portal authentication is validated through User_admin using the `tacai_session_id` cookie and `/api/validate-session`.
- `database/modules.json` stores central module labels, URLs, enabled flags, and required permissions.
- `database/services.json` stores the current local service URL/health reference for Portal, User_admin, and connected modules.
- `database/users.json` is legacy local MVP seed data and is not the primary Portal login path after User_admin session integration.
- `database/audit_logs.json` stores append-only portal audit events.
- `docs/Project_Plan.md` documents planned phases.
- `docs/Integration_Roadmap.md` documents Portal/User_admin/module integration steps.
- `docs/Manual_Test_Checklist.md` documents manual regression checks.
- `docs/Data_Schema.md` documents JSON schemas.

## Local port convention

- TACAI Portal: `3000` (DEV) / `4000` (STG) / `6000` (PRD) — per-environment
- TACAI User Management (`../User_admin`): `3001` (DEV) / `4001` (STG) / `6001` (PRD) — per-environment
- VendorPayables: `8008` (shared, fixed)
- Port config centralized in `TACAI-Core/tacai_config.py`

## User_admin authentication integration

- Portal `/login` redirects to TACAI User Management login at `http://127.0.0.1:<AUTH_PORT>/login?next=...` (AUTH_PORT is 3001 DEV / 4001 STG / 6001 PRD).
- User_admin returns to Portal after successful login and sets the `tacai_session_id` cookie.
- Portal validates `tacai_session_id` by calling User_admin `/api/validate-session`.
- Portal logout posts to `http://127.0.0.1:<AUTH_PORT>/logout?next=...`.
- Ports are environment-aware via `PORT`/`AUTH_PORT` env vars; see `TACAI-Core/tacai_config.py`.

## Connected modules

- `User Management` links to the User_admin app at the environment's auth port.
- `Vendor Payments` links to `http://127.0.0.1:8008/` and uses `vendor_expense.access` for Portal visibility.
- Other module entries remain placeholders until their integration phases are approved.

## Audit rules

All portal state-changing events must append audit logs with these fields:

- `module`
- `record_id`
- `action`
- `user`
- `timestamp`
- `before_value`
- `after_value`

Audit logs must never be deleted and should be treated as read-only history.

## Memory rules

After every major task:

- Update `memory/project_status.md`
- Update the related module memory file if one exists
- Update `memory/decisions.md` if architectural decisions were made
- Update `memory/changelog.md` if system changes occurred
