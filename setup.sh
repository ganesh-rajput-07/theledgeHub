#!/usr/bin/env bash
# KnowledgeHub AI - one-shot local setup.
# Creates backend/.venv (Python 3.12), installs pinned deps, writes backend/.env,
# starts PostgreSQL + pgvector in Docker, caches the embedding model, installs the
# Next.js frontend, and runs the tests.
#
# Usage:  ./setup.sh               full setup
#         ./setup.sh --no-db       skip Docker/Postgres
#         ./setup.sh --no-model    skip embedding model download
#         ./setup.sh --no-frontend skip the Next.js frontend
set -euo pipefail

PYTHON_VERSION="3.12"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
NODE_MAJOR_MIN=20
VENV_DIR="$BACKEND_DIR/.venv"

WITH_DB=1
WITH_MODEL=1
WITH_FRONTEND=1
for arg in "$@"; do
  case "$arg" in
    --no-db) WITH_DB=0 ;;
    --no-model) WITH_MODEL=0 ;;
    --no-frontend) WITH_FRONTEND=0 ;;
    *) echo "Unknown option: $arg"; exit 1 ;;
  esac
done

info() { printf '\033[1;34m==>\033[0m %s\n' "$1"; }
ok()   { printf '\033[1;32m✔\033[0m  %s\n' "$1"; }
fail() { printf '\033[1;31m✘\033[0m  %s\n' "$1"; exit 1; }

# ---------------------------------------------------------------- uv + Python
info "Checking uv"
if ! command -v uv >/dev/null 2>&1; then
  info "Installing uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
ok "uv $(uv --version | awk '{print $2}')"

info "Ensuring Python $PYTHON_VERSION"
uv python install "$PYTHON_VERSION" >/dev/null
ok "Python $PYTHON_VERSION available"

# ---------------------------------------------------------------- venv + deps
if [[ -d "$VENV_DIR" ]] && ! "$VENV_DIR/bin/python" -c "import sys; assert sys.version_info[:2] == (3, 12)" 2>/dev/null; then
  info "Existing .venv is not Python $PYTHON_VERSION - recreating"
  rm -rf "$VENV_DIR"
fi
if [[ ! -d "$VENV_DIR" ]]; then
  info "Creating virtual environment at backend/.venv"
  uv venv --python "$PYTHON_VERSION" --seed "$VENV_DIR"
fi
ok "Virtual environment ready"

info "Installing dependencies from backend/requirements.txt"
uv pip install --python "$VENV_DIR/bin/python" \
  --index-strategy unsafe-best-match \
  -r "$BACKEND_DIR/requirements.txt"
ok "Dependencies installed"

# ---------------------------------------------------------------- .env
ENV_FILE="$BACKEND_DIR/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  info "Creating backend/.env with generated secrets"
  cp "$BACKEND_DIR/.env.example" "$ENV_FILE"
  JWT_SECRET="$("$VENV_DIR/bin/python" -c 'import secrets; print(secrets.token_urlsafe(48))')"
  FERNET_KEY="$("$VENV_DIR/bin/python" -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
  sed -i "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$JWT_SECRET|" "$ENV_FILE"
  sed -i "s|^ENCRYPTION_KEY=.*|ENCRYPTION_KEY=$FERNET_KEY|" "$ENV_FILE"
  ok ".env created"
else
  ok "backend/.env already exists - left untouched"
fi

# ---------------------------------------------------------------- Postgres + pgvector
if [[ $WITH_DB -eq 1 ]]; then
  info "Starting PostgreSQL + pgvector (Docker)"
  command -v docker >/dev/null 2>&1 || fail "Docker not found. Install Docker or rerun with --no-db."
  docker info >/dev/null 2>&1 || fail "Docker daemon not reachable (is it running / are you in the docker group?)."
  POSTGRES_PORT="$(grep -E '^POSTGRES_PORT=' "$ENV_FILE" | cut -d= -f2)"
  export POSTGRES_PORT
  (cd "$ROOT_DIR" && docker compose up -d --wait db)
  docker exec knowledgehub-db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -qc "CREATE EXTENSION IF NOT EXISTS vector;"' >/dev/null
  ok "Database running on localhost:$POSTGRES_PORT with pgvector enabled"

  info "Applying database migrations"
  (cd "$BACKEND_DIR" && "$VENV_DIR/bin/alembic" upgrade head)
  ok "Database schema up to date"
fi

# ---------------------------------------------------------------- embedding model
if [[ $WITH_MODEL -eq 1 ]]; then
  info "Downloading / caching embedding model (first run only)"
  (cd "$BACKEND_DIR" && "$VENV_DIR/bin/python" - <<'PY'
from sentence_transformers import SentenceTransformer
from app.core.config import get_settings

model = SentenceTransformer(get_settings().embedding_model)
print("embedding shape:", model.encode("Company revenue increased by 20%.").shape)
PY
  )
  ok "Embedding model ready"
fi

# ---------------------------------------------------------------- verify
info "Verifying imports"
"$VENV_DIR/bin/python" -c "import fastapi, sqlalchemy, psycopg, pgvector, pymupdf, docx, pandas, torch, sentence_transformers, rapidocr, openai, anthropic, google.genai, jwt, pwdlib, cryptography; print('all imports OK')"

# OCR is pure pip: OpenCV-headless + ONNX Runtime only link libc/libstdc++/libz, which every Ubuntu has.
# Still, run a real OCR pass so a stripped-down system fails here with a clear message.
info "Checking OCR (RapidOCR)"
if ! (cd "$BACKEND_DIR" && "$VENV_DIR/bin/python" - <<'PY'
import pymupdf
from app.ingestion.ocr import ocr_page

doc = pymupdf.open()
page = doc.new_page()
page.insert_textbox(pymupdf.Rect(50, 50, 550, 200), "Scanned invoice total 4500", fontsize=20)
scan = pymupdf.open()
scan.new_page().insert_image(scan[0].rect, stream=page.get_pixmap(dpi=150).tobytes("png"))
text = ocr_page(scan[0], dpi=150)
assert "invoice" in text.lower(), f"unexpected OCR output: {text!r}"
PY
); then
  fail "OCR self-check failed. On minimal systems install: sudo apt-get install -y libstdc++6 zlib1g"
fi
ok "OCR working"

if [[ $WITH_DB -eq 1 ]]; then
  info "Running tests"
  (cd "$BACKEND_DIR" && "$VENV_DIR/bin/python" -m pytest -q)
fi

# ---------------------------------------------------------------- frontend
if [[ $WITH_FRONTEND -eq 1 ]]; then
  info "Setting up the Next.js frontend"
  command -v node >/dev/null 2>&1 || fail "Node.js not found. Install Node $NODE_MAJOR_MIN+ (e.g. via nvm) or rerun with --no-frontend."
  NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]')"
  [[ "$NODE_MAJOR" -ge $NODE_MAJOR_MIN ]] || fail "Node $NODE_MAJOR found; Node $NODE_MAJOR_MIN+ is required."
  (cd "$FRONTEND_DIR" && npm ci --no-audit --no-fund)
  [[ -f "$FRONTEND_DIR/.env.local" ]] || cp "$FRONTEND_DIR/.env.example" "$FRONTEND_DIR/.env.local"
  info "Type-checking and building the frontend"
  (cd "$FRONTEND_DIR" && npx next typegen >/dev/null && npx tsc --noEmit && npx next build >/dev/null)
  ok "Frontend ready (Node $(node --version))"
fi

echo
ok "Setup complete!"
cat <<EOF

Next steps:
  ./run.sh                     # API on port 8001 + web app on port 3000

  App:   http://localhost:3000
  API:   http://127.0.0.1:8001/docs
EOF
