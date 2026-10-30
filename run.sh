#!/usr/bin/env bash
# Start KnowledgeHub AI locally.
#   ./run.sh        API (port from API_PORT in backend/.env, default 8001) + web app (port 3000)
#   ./run.sh api    API only
#   ./run.sh web    web app only (expects the API to be running)
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
WEB_PORT="${WEB_PORT:-3000}"
MODE="${1:-all}"

API_PORT="$(grep -E '^API_PORT=' "$BACKEND_DIR/.env" 2>/dev/null | cut -d= -f2)"
API_PORT="${API_PORT:-8001}"

start_api() {
  [[ -x "$BACKEND_DIR/.venv/bin/uvicorn" ]] || { echo "No virtualenv found - run ./setup.sh first."; exit 1; }
  echo "API:  http://127.0.0.1:$API_PORT   Docs: http://127.0.0.1:$API_PORT/docs"
  cd "$BACKEND_DIR" && exec .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port "$API_PORT"
}

start_web() {
  [[ -d "$FRONTEND_DIR/node_modules" ]] || { echo "Frontend not installed - run ./setup.sh first."; exit 1; }
  echo "App:  http://localhost:$WEB_PORT  (talks to the API at http://127.0.0.1:$API_PORT)"
  cd "$FRONTEND_DIR" && BACKEND_URL="http://127.0.0.1:$API_PORT" ${1:-} node_modules/.bin/next dev -p "$WEB_PORT"
}

case "$MODE" in
  api) start_api ;;
  web) start_web exec ;;
  all)
    # Own process group for the API, so one signal stops uvicorn and its reload worker together.
    set -m
    start_api &
    API_PID=$!
    set +m
    cleanup() { kill -TERM -- "-$API_PID" 2>/dev/null || true; }
    trap cleanup EXIT
    trap 'exit 130' INT TERM
    start_web
    ;;
  *) echo "Usage: ./run.sh [api|web]"; exit 1 ;;
esac
