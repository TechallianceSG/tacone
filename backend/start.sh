#!/usr/bin/env bash
# =============================================================================
# TACAI Backend — FastAPI monolith launcher
# =============================================================================
# Usage:
#   bash start.sh              # dev (default, port 8000)
#   bash start.sh dev          # dev env
#   bash start.sh stg          # staging env
#   bash start.sh prd          # production env
#
# Equivalent to:
#   cd backend && npm start    (if you think of it that way)
# =============================================================================

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_NAME="${1:-dev}"
PORT="${PORT:-8000}"

# Load environment
ENV_FILE="${ROOT_DIR}/.env.${ENV_NAME}"
if [[ -f "${ENV_FILE}" ]]; then
  set -a; source "${ENV_FILE}"; set +a
  echo "[tacai] Loaded ${ENV_FILE}"
else
  echo "[tacai] WARNING: ${ENV_FILE} not found — using existing env"
fi

export TACAI_DB_ENABLED="${TACAI_DB_ENABLED:-true}"
export TACAI_INTERNAL_HOST="127.0.0.1"

echo "[tacai] Starting FastAPI monolith on :${PORT} (${ENV_NAME})..."
cd "${ROOT_DIR}/backend"
python3 -m uvicorn app:app --host 0.0.0.0 --port "${PORT}" --reload
