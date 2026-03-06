#!/usr/bin/env bash
# Start infrastructure services (PostgreSQL + Phoenix) natively — no Docker needed.
# Usage: ./scripts/start-infra.sh [--stop]
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PHOENIX_LOG="/tmp/phoenix.log"
PHOENIX_PORT="${PHOENIX_PORT:-6006}"
PHOENIX_DIR="${PHOENIX_WORKING_DIR:-/tmp/phoenix-data}"

red()   { printf "\033[31m%s\033[0m\n" "$*"; }
green() { printf "\033[32m%s\033[0m\n" "$*"; }
dim()   { printf "\033[2m%s\033[0m\n" "$*"; }

# ── Stop mode ────────────────────────────────────────────────────────
if [[ "${1:-}" == "--stop" ]]; then
  echo "Stopping infrastructure…"
  brew services stop postgresql@16 2>/dev/null && green "✓ PostgreSQL stopped" || dim "  PostgreSQL was not running"
  if pgrep -f "phoenix.server" >/dev/null 2>&1; then
    pkill -f "phoenix.server" && green "✓ Phoenix stopped"
  else
    dim "  Phoenix was not running"
  fi
  exit 0
fi

echo "Starting infrastructure…"
echo ""

# ── PostgreSQL ───────────────────────────────────────────────────────
if /opt/homebrew/opt/postgresql@16/bin/pg_isready -q 2>/dev/null; then
  green "✓ PostgreSQL already running on port 5432"
else
  echo "  Starting PostgreSQL 16…"
  brew services start postgresql@16 >/dev/null 2>&1
  for i in $(seq 1 15); do
    if /opt/homebrew/opt/postgresql@16/bin/pg_isready -q 2>/dev/null; then break; fi
    sleep 1
  done
  if /opt/homebrew/opt/postgresql@16/bin/pg_isready -q 2>/dev/null; then
    green "✓ PostgreSQL started on port 5432"
  else
    red "✗ PostgreSQL failed to start — check: brew services info postgresql@16"
    exit 1
  fi
fi

# ── Phoenix ──────────────────────────────────────────────────────────
if curl -s -o /dev/null -w '' "http://localhost:${PHOENIX_PORT}/" 2>/dev/null; then
  green "✓ Phoenix already running on port ${PHOENIX_PORT}"
else
  echo "  Starting Phoenix (observability UI)…"
  mkdir -p "$PHOENIX_DIR"
  PHOENIX_PORT="$PHOENIX_PORT" PHOENIX_WORKING_DIR="$PHOENIX_DIR" \
    nohup "$ROOT_DIR/.venv/bin/phoenix" serve > "$PHOENIX_LOG" 2>&1 &
  for i in $(seq 1 15); do
    if curl -s -o /dev/null -w '' "http://localhost:${PHOENIX_PORT}/" 2>/dev/null; then break; fi
    sleep 1
  done
  if curl -s -o /dev/null -w '' "http://localhost:${PHOENIX_PORT}/" 2>/dev/null; then
    green "✓ Phoenix started on port ${PHOENIX_PORT}  →  http://localhost:${PHOENIX_PORT}"
  else
    red "✗ Phoenix failed to start — check $PHOENIX_LOG"
    exit 1
  fi
fi

echo ""
green "Infrastructure ready."
