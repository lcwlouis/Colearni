#!/usr/bin/env bash
# Start frontend + backend for local development.
# Prerequisites: run ./scripts/start-infra.sh first.
# Usage: ./scripts/start-app.sh [--backend|--frontend]
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

red()   { printf "\033[31m%s\033[0m\n" "$*"; }
green() { printf "\033[32m%s\033[0m\n" "$*"; }
dim()   { printf "\033[2m%s\033[0m\n" "$*"; }

RUN_BACKEND=true
RUN_FRONTEND=true

case "${1:-}" in
  --backend)  RUN_FRONTEND=false ;;
  --frontend) RUN_BACKEND=false  ;;
  --help|-h)
    echo "Usage: $0 [--backend|--frontend]"
    echo "  (no flag)   Start both backend and frontend"
    echo "  --backend   Start only the backend (uvicorn)"
    echo "  --frontend  Start only the frontend (next dev)"
    exit 0
    ;;
esac

# ── Preflight checks ────────────────────────────────────────────────
if ! /opt/homebrew/opt/postgresql@16/bin/pg_isready -q 2>/dev/null; then
  red "✗ PostgreSQL is not running. Run ./scripts/start-infra.sh first."
  exit 1
fi
green "✓ PostgreSQL is up"

# ── Database migrations ─────────────────────────────────────────────
echo "  Running database migrations…"
"$ROOT_DIR/.venv/bin/python" -m alembic upgrade head 2>&1 | tail -1
green "✓ Migrations applied"
echo ""

# ── Cleanup on exit ─────────────────────────────────────────────────
PIDS=()
cleanup() {
  echo ""
  dim "Shutting down…"
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null && wait "$pid" 2>/dev/null
  done
}
trap cleanup EXIT INT TERM

# ── Backend ──────────────────────────────────────────────────────────
if $RUN_BACKEND; then
  echo "Starting backend (uvicorn) on port ${APP_PORT:-8000}…"
  "$ROOT_DIR/.venv/bin/uvicorn" apps.api.main:app \
    --reload \
    --host "${APP_HOST:-0.0.0.0}" \
    --port "${APP_PORT:-8000}" &
  PIDS+=($!)
  green "✓ Backend PID $!"
fi

# ── Frontend ─────────────────────────────────────────────────────────
if $RUN_FRONTEND; then
  echo "Starting frontend (next dev) on port 3000…"
  cd "$ROOT_DIR/apps/web"
  npm run dev &
  PIDS+=($!)
  green "✓ Frontend PID $!"
  cd "$ROOT_DIR"
fi

echo ""
green "═══════════════════════════════════════════"
$RUN_BACKEND  && green "  Backend  →  http://localhost:${APP_PORT:-8000}"
$RUN_BACKEND  && green "  API docs →  http://localhost:${APP_PORT:-8000}/docs"
$RUN_FRONTEND && green "  Frontend →  http://localhost:3000"
green "═══════════════════════════════════════════"
echo ""
dim "Press Ctrl+C to stop."

wait
