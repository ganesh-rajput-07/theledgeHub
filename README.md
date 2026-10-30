# KnowledgeHub AI

Multi-tenant, BYOK AI knowledge platform: upload documents, ask questions, get answers with page-level citations.
Project blueprint: [`docs/`](docs/).

## Setup

```bash
./setup.sh               # venv (Python 3.12), deps, .env, Postgres+pgvector (Docker, port 5433), migrations,
                         # embedding model, OCR check, frontend (npm ci + build), tests
./setup.sh --no-db       # skip Docker/Postgres
./setup.sh --no-model    # skip embedding model download
./setup.sh --no-frontend # skip the Next.js frontend
```

Run the API:

```bash
./run.sh                          # API on :8001 + web app on http://localhost:3000
./run.sh api                      # API only   (http://127.0.0.1:8001/docs, port = API_PORT in backend/.env)
./run.sh web                      # web only   (frontend/README.md explains how it talks to the API)
./run.sh docker                   # full stack in containers: Postgres + API (:8001) + web (:3000)

cd backend && source .venv/bin/activate
pytest                            # needs the Docker database running
```

### Docker

`./run.sh docker` builds and starts everything (`docker compose --env-file backend/.env --profile app up --build`).
Secrets come from `backend/.env`; the API image bakes in the embedding model, runs migrations on start and
runs as a non-root user. Plain `docker compose up -d db` still starts only the database for local development.
Set `COOKIE_SECURE=false` only when serving the web app over plain HTTP on a non-localhost address.

## Quality

| Check | Command | CI |
| --- | --- | --- |
| Tests (unit, integration, 25-route tenant isolation, RAG quality guard) | `cd backend && .venv/bin/python -m pytest` | ✓ |
| RAG evaluation (Recall@K, MRR, not-found sweep, citations) | `cd backend && .venv/bin/python -m evaluation` – see [docs/evaluation.md](docs/evaluation.md) | guard only |
| Lint + security rules (ruff incl. bandit `S`) | `.venv/bin/ruff check app tests evaluation` | ✓ |
| Migrations match models | `.venv/bin/alembic check` | ✓ |
| Dependency vulnerabilities | `.venv/bin/pip-audit -r requirements.txt` · `npm audit --omit=dev` | ✓ |
| Frontend types / lint / build | `npx tsc --noEmit` · `npx eslint src` · `npx next build` | ✓ |

Architecture, security model and scaling notes: [docs/architecture.md](docs/architecture.md).

## Progress

- [x] Milestone 1 – Project foundation (FastAPI, Postgres + pgvector, config, health check)
- [x] Milestone 2 – Document ingestion (upload, validation, page-wise extraction, chunking, storage)
- [x] Milestone 3 – Embeddings and retrieval (local embeddings, pgvector HNSW, semantic search, OCR)
- [x] Milestone 4 – AI integration (BYOK providers, prompts, validated citations, not-found handling)
- [x] Milestone 5 – Business features (auth, organizations, workspaces, roles, tenant isolation)
- [x] Milestone 6 – Frontend (Next.js dashboard, research chat with citations, settings)
- [x] Milestone 7 – Quality and release (RAG evaluation, rate limiting, audit log, Docker, CI)

## API (`/api/v1`)

Everything except `auth/register|login|refresh|logout` and `/health` needs `Authorization: Bearer <access token>`.
A resource from another organization always answers **404**, so tenants can't even confirm each other's IDs exist.
Full interactive reference: http://127.0.0.1:8001/docs

| Area | Endpoints |
| --- | --- |
| Auth | `POST auth/register` · `POST auth/login` · `POST auth/refresh` (rotates) · `POST auth/logout` (revokes) · `GET auth/me` |
| Organizations | `GET/POST organizations` · `GET organizations/{id}` · `GET/POST organizations/{id}/members` · `DELETE organizations/{id}/members/{user_id}` |
| Audit log | `GET organizations/{id}/audit-logs` (`limit`, `action`; owners/admins) |
| Workspaces | `GET/POST organizations/{id}/workspaces` · `GET/DELETE workspaces/{id}` |
| Documents | `GET/POST workspaces/{id}/documents` · `GET/DELETE documents/{id}` · `GET documents/{id}/status` · `GET documents/{id}/chunks` · `GET documents/{id}/file` · `POST documents/{id}/reprocess` |
| Search | `POST workspaces/{id}/search` (`query`, `top_k` 1–50, `document_ids`, `min_score`) |
| Provider keys (BYOK) | `GET/POST organizations/{id}/providers` · `GET/PATCH/DELETE providers/{id}` · `POST providers/{id}/validate` |
| Chat | `GET/POST workspaces/{id}/conversations` · `GET/DELETE conversations/{id}` · `GET/POST conversations/{id}/messages` · `GET messages/{id}/citations` |

**Roles**: members upload, search and chat; owners/admins also manage provider keys, members and workspaces.
Documents can be deleted by their uploader or an owner/admin. Conversations are private to their creator.

Supported providers: `openai`, `anthropic`, `gemini` (customer API key), `ollama` (local, optional `base_url`),
`mock` (offline, deterministic – disabled when `APP_ENV=production`).

```bash
API=http://127.0.0.1:8001/api/v1
curl -X POST $API/auth/register -H 'Content-Type: application/json' \
     -d '{"email": "me@company.com", "password": "a-long-password", "organization_name": "Acme"}'
TOKEN=$(curl -s -X POST $API/auth/login -H 'Content-Type: application/json' \
     -d '{"email": "me@company.com", "password": "a-long-password"}' | jq -r .access_token)
curl -H "Authorization: Bearer $TOKEN" $API/organizations            # → org id
curl -H "Authorization: Bearer $TOKEN" $API/organizations/<org>/workspaces   # → workspace id
curl -H "Authorization: Bearer $TOKEN" -F "file=@report.pdf" $API/workspaces/<ws>/documents
curl -H "Authorization: Bearer $TOKEN" -X POST $API/organizations/<org>/providers -H 'Content-Type: application/json' \
     -d '{"provider": "anthropic", "label": "My key", "api_key": "sk-ant-...", "default_model": "claude-opus-5-5"}'
curl -H "Authorization: Bearer $TOKEN" -X POST $API/workspaces/<ws>/conversations -H 'Content-Type: application/json' \
     -d '{"provider_id": "<provider id>"}'
curl -H "Authorization: Bearer $TOKEN" -X POST $API/conversations/<id>/messages -H 'Content-Type: application/json' \
     -d '{"question": "How many leave days do employees get?"}'
```

How an answer is produced: `follow-up? rewrite it into a standalone search query → retrieve within the
workspace (top 8, score ≥ RAG_MIN_SCORE) → nothing relevant? answer "not found"
without calling the LLM → numbered <sources> + question → customer's model → keep only [n] markers that point at a
retrieved chunk → save answer, citations, token usage`.

- **Keys**: validated with one cheap `list models` call before saving, Fernet-encrypted (`ENCRYPTION_KEY`), never
  returned or logged (`SecretStr`); only a `…abcd` hint is shown. The chosen model must be available to the key.
- **Citations** come from the backend, not the model: a `[7]` the model invents is stripped from the answer.
- **Prompt injection**: document text is escaped and wrapped in `<source>` tags the system prompt marks as untrusted.
- **Errors**: bad key → 400, provider rate limit → 429, unknown model / refusal → 422, provider down → 502.
  A failed call stores nothing, so the user can simply retry.
- **Anthropic**: current models get `effort: medium` and server-side refusal fallbacks (`fallbacks: "default"`).
  **OpenAI** uses the Responses API with `store=false`, so customer documents aren't retained provider-side.

## Ingestion pipeline

`validate → store → extract (PyMuPDF / python-docx / UTF-8, OCR fallback) → clean → chunk → embed → save`

- **Validation**: extension allow-list, file-signature check (content must really be a PDF/DOCX/UTF-8 text),
  size limit (`MAX_UPLOAD_MB`), filename path stripping; files are stored under generated UUID names.
- **Chunking**: sentence-aware, 250 tokens with 50-token overlap, counted with the embedding model's own tokenizer.
  `all-MiniLM-L6-v2` truncates at 256 tokens, so the blueprint's 500-token default would silently lose text.
  Chunks never cross pages, so every chunk cites exactly one page.
- **OCR**: PDF pages with (almost) no text layer but with images are rendered and read with RapidOCR
  (CPU, ONNX models bundled in the pip wheel – no Tesseract/system packages). OCR'd chunks carry
  `metadata: {"ocr": true}`. Toggle with `OCR_ENABLED`, tune with `OCR_DPI` / `OCR_MIN_TEXT_CHARS`.
- **Embeddings**: `all-MiniLM-L6-v2` on CPU, normalized 384-d vectors, stored in `document_chunks.embedding`
  with an HNSW cosine index. Each document records its `embedding_model` so a future model change knows what to
  re-embed. Documents ingested before Milestone 3 have no vectors – call `POST /documents/{id}/reprocess`.
