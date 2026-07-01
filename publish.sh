#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# TACAI One-Click Publish Script
# ==============================
# Build the frontend + start backend services + expose via LAN/Cloudflare.
#
# Usage:
#   bash publish.sh [dev|stg|prd] [--tunnel] [--frontend-only] [--status] [--stop]
#
# Examples:
#   bash publish.sh dev             # Build & start DEV (LAN only)
#   bash publish.sh dev --tunnel    # Build & start DEV + Cloudflare tunnel
#   bash publish.sh prd --tunnel    # Build & start PRD + Cloudflare tunnel
#   bash publish.sh --frontend-only # Build frontend only (all envs)
#   bash publish.sh --status        # Show running services
#   bash publish.sh --stop          # Stop all services
# ──────────────────────────────────────────────────────────────────────
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="${ROOT_DIR}/frontend"
GATEWAY_SCRIPT="${ROOT_DIR}/deployment/remote-access/tacai_temp_gateway.py"
START_SCRIPT="${ROOT_DIR}/start_tacai_lan.sh"
LOG_DIR="${ROOT_DIR}/.lan-logs"

ENV="${1:-dev}"
TUNNEL=false
FRONTEND_ONLY=false
SHOW_STATUS=false
STOP_ALL=false

# Parse flags
for arg in "$@"; do
  case "$arg" in
    --tunnel)    TUNNEL=true ;;
    --frontend-only) FRONTEND_ONLY=true ;;
    --status)    SHOW_STATUS=true ;;
    --stop)      STOP_ALL=true ;;
  esac
done

# ── Colors ──────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

banner() {
  echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${CYAN}  TACAI 一键发版 / One-Click Publish${NC}"
  echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo ""
}

# ── Status ──────────────────────────────────────────────────────────
if [[ "${SHOW_STATUS}" == "true" ]]; then
  bash "${START_SCRIPT}" status
  exit 0
fi

# ── Stop ────────────────────────────────────────────────────────────
if [[ "${STOP_ALL}" == "true" ]]; then
  echo -e "${YELLOW}Stopping all services...${NC}"
  bash "${START_SCRIPT}" stop all 2>/dev/null || true
  echo -e "${GREEN}Done.${NC}"
  exit 0
fi

# ── Validate environment ────────────────────────────────────────────
VALID_ENVS=("dev" "stg" "prd")
if [[ ! " ${VALID_ENVS[*]} " == *" ${ENV} "* ]] && [[ "${FRONTEND_ONLY}" == "false" ]]; then
  echo -e "${RED}ERROR: Unknown environment '${ENV}'. Valid: dev, stg, prd${NC}"
  exit 1
fi

banner

# ── Step 1: Check prerequisites ─────────────────────────────────────
echo -e "${YELLOW}[1/4] Checking prerequisites...${NC}"

# Node.js
if ! command -v node &>/dev/null; then
  echo -e "${RED}ERROR: Node.js is required. Install from https://nodejs.org${NC}"
  exit 1
fi
echo "  Node.js:  $(node --version)"

# Python3
if ! command -v python3 &>/dev/null; then
  echo -e "${RED}ERROR: Python 3 is required.${NC}"
  exit 1
fi
echo "  Python:   $(python3 --version)"

# npm dependencies
if [[ ! -d "${FRONTEND_DIR}/node_modules" ]]; then
  echo -e "${YELLOW}  Installing frontend dependencies...${NC}"
  cd "${FRONTEND_DIR}" && npm install
fi
echo "  npm:      ready"

# PostgreSQL check (basic)
if command -v psql &>/dev/null; then
  echo "  PostgreSQL: $(psql --version 2>&1 | head -1)"
else
  echo -e "${YELLOW}  PostgreSQL: psql not found (make sure DB is running)${NC}"
fi

echo ""

# ── Step 2: Build frontend ──────────────────────────────────────────
echo -e "${YELLOW}[2/4] Building frontend (${ENV})...${NC}"

cd "${FRONTEND_DIR}"

case "${ENV}" in
  dev)
    npm run build
    ;;
  stg)
    npm run build:stg
    ;;
  prd)
    npm run build:prd
    ;;
esac

if [[ -f "${FRONTEND_DIR}/dist/index.html" ]]; then
  DIST_SIZE=$(du -sh "${FRONTEND_DIR}/dist" 2>/dev/null | cut -f1)
  echo -e "${GREEN}  Frontend built successfully → frontend/dist/ (${DIST_SIZE})${NC}"
else
  echo -e "${RED}  ERROR: Build failed — frontend/dist/index.html not found${NC}"
  exit 1
fi

echo ""

# ── Step 3: Start backend services ──────────────────────────────────
if [[ "${FRONTEND_ONLY}" == "true" ]]; then
  echo -e "${GREEN}Frontend-only mode — skipping backend startup.${NC}"
  echo ""
  echo "To start services: bash start_tacai_lan.sh start ${ENV}"
  exit 0
fi

echo -e "${YELLOW}[3/4] Starting backend services (${ENV})...${NC}"

# Check .env file exists
if [[ ! -f "${ROOT_DIR}/.env.${ENV}" ]]; then
  echo -e "${RED}  ERROR: .env.${ENV} not found. Run setup first.${NC}"
  exit 1
fi

# Start services
bash "${START_SCRIPT}" start "${ENV}"

echo ""

# ── Step 4: Start Gateway + optional Cloudflare tunnel ──────────────
echo -e "${YELLOW}[4/4] Starting Gateway (port ${TACAI_GATEWAY_PORT:-8010})...${NC}"

# Kill existing gateway if running
GATEWAY_PORT="${TACAI_GATEWAY_PORT:-8010}"
EXISTING_PID=$(lsof -nP -iTCP:"${GATEWAY_PORT}" -sTCP:LISTEN 2>/dev/null | awk 'NR==2 {print $2}' || true)
if [[ -n "${EXISTING_PID}" ]]; then
  echo "  Stopping existing Gateway pid=${EXISTING_PID}"
  kill "${EXISTING_PID}" 2>/dev/null || true
  sleep 1
fi

# Read Portal port from env
PORTAL_PORT=$(grep -E '^PORT=' "${ROOT_DIR}/.env.${ENV}" | head -1 | cut -d= -f2 || echo "3000")
PORTAL_PORT="${PORTAL_PORT:-3000}"

# Start Gateway
mkdir -p "${LOG_DIR}"
GATEWAY_LOG="${LOG_DIR}/gateway.log"
nohup python3 "${GATEWAY_SCRIPT}" --host 0.0.0.0 --port "${GATEWAY_PORT}" --portal-port "${PORTAL_PORT}" \
  >> "${GATEWAY_LOG}" 2>&1 &
GATEWAY_PID="$!"
disown "${GATEWAY_PID}" 2>/dev/null || true
echo "  Gateway pid=${GATEWAY_PID} port=${GATEWAY_PORT} → Portal:${PORTAL_PORT}"

# Cloudflare tunnel (optional)
if [[ "${TUNNEL}" == "true" ]]; then
  echo ""
  echo -e "${YELLOW}Starting Cloudflare tunnel...${NC}"
  bash "${START_SCRIPT}" start-remote "${ENV}"
else
  echo ""
  echo "  Cloudflare tunnel: skipped (use --tunnel to enable)"
fi

# ── Summary ─────────────────────────────────────────────────────────
LAN_IP=$(bash "${START_SCRIPT}" status 2>/dev/null | head -1 | awk '{print $NF}' || echo "localhost")

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  ✅ Publish complete!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  Local:    http://127.0.0.1:${PORTAL_PORT}"
echo "  LAN:      http://${LAN_IP}:${PORTAL_PORT}"
echo "  Gateway:  http://${LAN_IP}:${GATEWAY_PORT}"

if [[ "${TUNNEL}" == "true" ]] && [[ -f "${LOG_DIR}/cloudflared.log" ]]; then
  REMOTE_URL=$(grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' "${LOG_DIR}/cloudflared.log" 2>/dev/null | head -1 || true)
  if [[ -n "${REMOTE_URL}" ]]; then
    echo "  Remote:   ${REMOTE_URL}"
  fi
fi
echo ""
echo "  Manage:  bash start_tacai_lan.sh status"
echo "           bash start_tacai_lan.sh stop ${ENV}"
echo "           bash publish.sh --stop"
echo ""
