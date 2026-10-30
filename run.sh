#!/usr/bin/env bash
# Start the KnowledgeHub AI API locally (port from API_PORT in backend/.env, default 8001).
set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/backend"
cd "$BACKEND_DIR"
[[ -x .venv/bin/uvicorn ]] || { echo "No virtualenv found - run ./setup.sh first."; exit 1; }

PORT="$(grep -E '^API_PORT=' .env 2>/dev/null | cut -d= -f2)"
PORT="${PORT:-8001}"

echo "API:  http://127.0.0.1:$PORT   Docs: http://127.0.0.1:$PORT/docs"
exec .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port "$PORT" "$@"
