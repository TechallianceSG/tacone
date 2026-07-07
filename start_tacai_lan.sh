#!/usr/bin/env bash
# =============================================================================
# TACAI Monolith — unified start/stop/restart/status
# =============================================================================
# Usage:
#   bash start_tacai_lan.sh start [dev|stg|prd]    # Start backend (+ frontend in dev)
#   bash start_tacai_lan.sh stop                    # Stop all
#   bash start_tacai_lan.sh restart [env]           # Stop + Start
#   bash start_tacai_lan.sh status                  # Show running processes
#   bash start_tacai_lan.sh frontend                # Start frontend only
#
# Architecture (post-merge):
#   1 FastAPI monolith (backend/app.py)  — all 8 modules, single process
#   1 Vite dev server  (frontend/)       — hot-reload, dev only
# =============================================================================

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${ROOT_DIR}/.lan-logs"
PID_DIR="${LOG_DIR}/pids"
LAN_INTERFACE="${LAN_INTERFACE:-en0}"

ACTION="${1:-start}"
ENV_NAME="${2:-dev}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

mkdir -p "${PID_DIR}"

# ── LAN IP ────────────────────────────────────────────────────────────────

find_lan_ip() {
  local ip=""
  ip="$(ipconfig getifaddr "${LAN_INTERFACE}" 2>/dev/null || true)"
  if [[ -z "${ip}" ]]; then
    local wifi=""
    wifi="$(networksetup -listallhardwareports 2>/dev/null | awk '/Hardware Port: Wi-Fi/{getline; print $2; exit}' || true)"
    [[ -n "${wifi}" ]] && ip="$(ipconfig getifaddr "${wifi}" 2>/dev/null || true)"
  fi
  [[ -z "${ip}" ]] && { echo "ERROR: Cannot detect LAN IP" >&2; exit 1; }
  echo "${ip}"
}

LAN_IP="$(find_lan_ip)"
if [[ -n "${TACAI_PUBLIC_HOST:-}" && "${TACAI_PUBLIC_HOST}" != "127.0.0.1" && "${TACAI_PUBLIC_HOST}" != "localhost" ]]; then
  LAN_IP="${TACAI_PUBLIC_HOST}"
fi

export TACAI_PUBLIC_HOST="${LAN_IP}"
export TACAI_INTERNAL_HOST="127.0.0.1"
export TACAI_ALLOWED_PUBLIC_HOSTS="${LAN_IP},127.0.0.1,localhost"
export PYTHONUNBUFFERED="1"

# ── Load .env for DB config ──────────────────────────────────────────────

load_env() {
  local env_file="${ROOT_DIR}/.env.${1:-dev}"
  if [[ -f "${env_file}" ]]; then
    set -a; source "${env_file}"; set +a
  fi
  export TACAI_DB_ENABLED="${TACAI_DB_ENABLED:-true}"
}
load_env "${ENV_NAME}"

# ── Process helpers ──────────────────────────────────────────────────────

is_running() {
  local pid="$1"
  [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null
}

pid_file_for() {
  echo "${PID_DIR}/$1.pid"
}

read_pid() {
  local f="$(pid_file_for "$1")"
  [[ -f "${f}" ]] && cat "${f}" || echo ""
}

write_pid() {
  echo "$2" > "$(pid_file_for "$1")"
}

remove_pid() {
  rm -f "$(pid_file_for "$1")"
}

# ── Backend ──────────────────────────────────────────────────────────────

start_backend() {
  local pid="$(read_pid backend)"
  if is_running "${pid}"; then
    echo "  Backend already running (PID ${pid}, port ${BACKEND_PORT})"
    return
  fi

  echo "  Starting FastAPI monolith on :${BACKEND_PORT}..."
  cd "${ROOT_DIR}/backend"
  nohup python3 -m uvicorn app:app --host 0.0.0.0 --port "${BACKEND_PORT}" \
    > "${LOG_DIR}/backend.log" 2>&1 &
  local new_pid=$!
  write_pid backend "${new_pid}"
  sleep 5

  if is_running "${new_pid}"; then
    echo "  ✓ Backend started (PID ${new_pid})"
  else
    echo "  ✗ Backend failed to start — check ${LOG_DIR}/backend.log"
    remove_pid backend
    return 1
  fi
}

stop_backend() {
  local pid="$(read_pid backend)"
  if is_running "${pid}"; then
    echo "  Stopping backend (PID ${pid})..."
    kill "${pid}" 2>/dev/null || true
    sleep 1
    is_running "${pid}" && kill -9 "${pid}" 2>/dev/null || true
    echo "  ✓ Backend stopped"
  else
    echo "  Backend not running"
  fi
  remove_pid backend
}

# ── Frontend ─────────────────────────────────────────────────────────────

start_frontend() {
  local pid="$(read_pid frontend)"
  if is_running "${pid}"; then
    echo "  Frontend already running (PID ${pid}, port ${FRONTEND_PORT})"
    return
  fi

  echo "  Starting Vite dev server on :${FRONTEND_PORT}..."
  cd "${ROOT_DIR}/frontend"
  nohup npx vite --host 0.0.0.0 --port "${FRONTEND_PORT}" \
    > "${LOG_DIR}/frontend.log" 2>&1 &
  local new_pid=$!
  write_pid frontend "${new_pid}"
  sleep 2

  if is_running "${new_pid}"; then
    echo "  ✓ Frontend started (PID ${new_pid}) → http://${LAN_IP}:${FRONTEND_PORT}"
  else
    echo "  ✗ Frontend failed to start — check ${LOG_DIR}/frontend.log"
    remove_pid frontend
    return 1
  fi
}

stop_frontend() {
  local pid="$(read_pid frontend)"
  if is_running "${pid}"; then
    echo "  Stopping frontend (PID ${pid})..."
    kill "${pid}" 2>/dev/null || true
    sleep 1
    is_running "${pid}" && kill -9 "${pid}" 2>/dev/null || true
    echo "  ✓ Frontend stopped"
  else
    echo "  Frontend not running"
  fi
  remove_pid frontend
}

# ── Status ────────────────────────────────────────────────────────────────

show_status() {
  echo ""
  echo "══════════════════════════════════════════════"
  echo "  TACAI Monolith Status"
  echo "══════════════════════════════════════════════"
  echo "  LAN IP:   ${LAN_IP}"
  echo "  Env:      ${ENV_NAME}"
  echo ""

  local be_pid="$(read_pid backend)"
  if is_running "${be_pid}"; then
    echo "  Backend   ✓ running (PID ${be_pid}, port ${BACKEND_PORT})"
    echo "            → http://${LAN_IP}:${BACKEND_PORT}/health"
  else
    echo "  Backend   ✗ not running"
  fi

  local fe_pid="$(read_pid frontend)"
  if is_running "${fe_pid}"; then
    echo "  Frontend  ✓ running (PID ${fe_pid}, port ${FRONTEND_PORT})"
    echo "            → http://${LAN_IP}:${FRONTEND_PORT}"
  else
    echo "  Frontend  ✗ not running"
  fi

  # Quick health check
  if is_running "${be_pid}"; then
    local hc=""
    sleep 1
    hc="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${BACKEND_PORT}/health" 2>/dev/null || echo "000")"
    echo ""
    echo "  Health:   HTTP ${hc}"
  fi
  echo "══════════════════════════════════════════════"
  echo ""
}

# ── Main ──────────────────────────────────────────────────────────────────

case "${ACTION}" in
  start)
    echo "=== TACAI Monolith — Starting (${ENV_NAME}) ==="
    start_backend
    start_frontend
    show_status
    ;;
  stop)
    echo "=== TACAI Monolith — Stopping ==="
    stop_frontend
    stop_backend
    ;;
  restart)
    echo "=== TACAI Monolith — Restarting (${ENV_NAME}) ==="
    stop_frontend
    stop_backend
    sleep 1
    start_backend
    start_frontend
    show_status
    ;;
  status)
    show_status
    ;;
  frontend)
    start_frontend
    ;;
  backend)
    start_backend
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status|frontend|backend} [dev|stg|prd]"
    echo ""
    echo "  start [env]   Start backend + frontend"
    echo "  stop          Stop everything"
    echo "  restart [env] Stop then start"
    echo "  status        Show running processes"
    echo "  frontend      Start frontend (Vite) only"
    echo "  backend       Start backend (FastAPI) only"
    exit 2
    ;;
esac
