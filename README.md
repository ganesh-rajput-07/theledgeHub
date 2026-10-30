# KnowledgeHub AI

Multi-tenant, BYOK AI knowledge platform: upload documents, ask questions, get answers with page-level citations.
Project blueprint: [`docs/`](docs/).

## Setup

```bash
./setup.sh              # venv (Python 3.12), deps, .env, Postgres+pgvector (Docker, port 5433), migrations, model, tests
./setup.sh --no-db      # skip Docker/Postgres
./setup.sh --no-model   # skip embedding model download
```

Run the API:

```bash
./run.sh                          # http://127.0.0.1:8001/docs  (port = API_PORT in backend/.env)

cd backend && source .venv/bin/activate
pytest                            # needs the Docker database running
```

## Progress

- [x] Milestone 1 – Project foundation (FastAPI, Postgres + pgvector, config, health check)
- [x] Milestone 2 – Document ingestion (upload, validation, page-wise extraction, chunking, storage)
- [x] Milestone 3 – Embeddings and retrieval (local embeddings, pgvector HNSW, semantic search, OCR)
- [x] Milestone 4 – AI integration (BYOK providers, prompts, validated citations, not-found handling)
- [ ] Milestone 5 – Business features (auth, organizations, workspaces)
- [ ] Milestone 6 – Frontend
- [ ] Milestone 7 – Quality and release

## Document API (`/api/v1`)

| Method | Endpoint                     | Purpose                                   |
| ------ | ---------------------------- | ----------------------------------------- |
| POST   | `/documents`                 | Upload PDF / DOCX / TXT / MD (202, async) |
| GET    | `/documents`                 | List documents                            |
| GET    | `/documents/{id}`            | Document details + chunk count            |
| GET    | `/documents/{id}/status`     | Ingestion status / error                  |
| GET    | `/documents/{id}/chunks`     | Inspect chunks (`limit`, `offset`)        |
| POST   | `/documents/{id}/reprocess`  | Re-run ingestion                          |
| DELETE | `/documents/{id}`            | Delete file, chunks and jobs              |
| POST   | `/search`                    | Semantic search over completed documents  |

Documents move under `/workspaces/{id}/documents` once workspaces and auth land (Milestone 5).

```bash
curl -F "file=@report.pdf" http://127.0.0.1:8001/api/v1/documents
curl http://127.0.0.1:8001/api/v1/documents/<id>/chunks
curl -X POST http://127.0.0.1:8001/api/v1/search -H 'Content-Type: application/json' \
     -d '{"query": "How many leave days do employees get?", "top_k": 5}'
```

Search body: `query` (required), `top_k` (1–50, default 8), `document_ids` (optional filter),
`min_score` (optional cosine-similarity cutoff). Results come back best-first with filename, page number and score.

## BYOK providers & chat (`/api/v1`)

| Method | Endpoint                           | Purpose                                              |
| ------ | ---------------------------------- | ---------------------------------------------------- |
| POST   | `/providers`                       | Connect a provider (key validated, stored encrypted) |
| GET    | `/providers`                       | List connections (key hint only, never the key)      |
| PATCH  | `/providers/{id}`                  | Rename / rotate key / change model / disable         |
| POST   | `/providers/{id}/validate`         | Re-check key, list available models                  |
| DELETE | `/providers/{id}`                  | Delete the stored key                                |
| POST   | `/conversations`                   | Start a conversation (provider, model, documents)    |
| GET    | `/conversations`                   | List conversations                                   |
| POST   | `/conversations/{id}/messages`     | Ask a question → answer + citations                  |
| GET    | `/conversations/{id}/messages`     | Chat history with citations                          |
| GET    | `/messages/{id}/citations`         | Citation details                                     |

Supported providers: `openai`, `anthropic`, `gemini` (customer API key), `ollama` (local, optional `base_url`),
`mock` (offline, deterministic – disabled when `APP_ENV=production`).

```bash
curl -X POST http://127.0.0.1:8001/api/v1/providers -H 'Content-Type: application/json' \
     -d '{"provider": "anthropic", "label": "My key", "api_key": "sk-ant-...", "default_model": "claude-opus-5-5"}'
curl -X POST http://127.0.0.1:8001/api/v1/conversations -H 'Content-Type: application/json' \
     -d '{"provider_id": "<provider id>", "document_ids": []}'
curl -X POST http://127.0.0.1:8001/api/v1/conversations/<id>/messages -H 'Content-Type: application/json' \
     -d '{"question": "How many leave days do employees get?"}'
```

How an answer is produced: `retrieve (top 8, score ≥ RAG_MIN_SCORE) → nothing relevant? answer "not found"
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
