# KnowledgeHub AI – architecture

A **modular monolith**: one FastAPI service with clearly separated modules, one Next.js web app,
PostgreSQL + pgvector. Customers bring their own LLM keys (BYOK); embeddings run locally.

```
Browser ──► Next.js (port 3000) ──► FastAPI (port 8001) ──► PostgreSQL + pgvector (5433 dev / db in Docker)
            · httpOnly session       · auth, tenancy, RAG     · tenants, documents, chunks + vectors,
              cookies                · ingestion + OCR          chats, citations, audit log
            · streams uploads        · embeddings (local)
                                     └──► customer's LLM: OpenAI · Anthropic · Gemini · Ollama
```

## Backend modules (`backend/app`)

| Module | Responsibility |
| --- | --- |
| `api/` | Versioned REST routes. `deps.py` is the **single place** that authenticates and resolves every resource through the caller's organization memberships. |
| `core/` | Settings, JWT + Argon2, Fernet encryption of provider keys, rate limiting, client-IP resolution. |
| `models/` + `database/migrations` | SQLAlchemy models and Alembic migrations (every schema change is a migration; CI fails on drift). |
| `ingestion/` | Validate → extract (PyMuPDF / python-docx / UTF-8, RapidOCR for scanned pages) → clean → sentence-aware chunking (≤250 tokens, never across pages). |
| `rag/` | Local embeddings, workspace-scoped vector retrieval (HNSW, cosine), follow-up query rewriting, prompt building, citation validation. |
| `llm/` | Provider-independent interface; one adapter per vendor. No vendor SDK is imported outside this folder. |
| `services/` | Business operations (auth, organizations, documents, providers, chat, audit). |

## Request flow: asking a question

1. `POST /conversations/{id}/messages` → `deps.get_conversation` checks the caller owns the conversation
   **and** is still a member of its organization (else 404).
2. Follow-up? The customer's model rewrites it into a standalone search query (fallback: previous
   question + new one; provider overloaded/auth/rate-limit errors fail fast instead).
3. Retrieval: embed the query locally, top-8 chunks **from that workspace only**, drop scores below
   `RAG_MIN_SCORE` (0.30). Nothing left → "not found" without calling (or billing) the LLM.
4. Prompt: numbered, HTML-escaped `<source>` blocks marked as untrusted data + the question + history.
5. Answer: only `[n]` markers that point at a retrieved chunk survive; citations are saved with the
   chunk, page, quote and score. A model that answers `NOT_FOUND` becomes a clear "not found" message.

## Security model

| Concern | Implementation |
| --- | --- |
| Authentication | Argon2id passwords; 30-min JWT access tokens; 7-day refresh tokens stored as revocable sessions and **rotated on every refresh**. |
| Browser sessions | Tokens only in httpOnly, SameSite=Lax cookies set by Next.js; JS never sees them. Cross-site state-changing requests rejected (Origin check). |
| Tenant isolation | Every lookup goes through `api/deps.py`; other tenants get 404. Search requires a `workspace_id`; client-supplied document IDs are checked against the workspace. Covered by a 25-route cross-tenant test. |
| Authorization | Roles owner / admin / member; managers handle keys, members, workspaces. Last owner can't be removed; admins can't create owners. |
| Provider keys | Validated before saving, Fernet-encrypted at rest, never returned or logged (`SecretStr`), only a `…abcd` hint shown; audit log records rotations without values. |
| Brute force | Per-account lockout after 5 failed logins and per-IP limits on login/register (15-min window). `X-Forwarded-For` trusted only from `TRUSTED_PROXIES`. |
| Uploads | Extension allow-list + file-signature check, 25 MB limit, UUID storage names, macro formats rejected; downloads served with `nosniff`, text as `text/plain` attachments. |
| Prompt injection | Document text escaped and fenced; system prompt treats sources as untrusted; model-invented citations stripped; Markdown rendered without raw HTML. |
| Audit | Logins (incl. failures), uploads, deletions, provider/member/workspace changes, with actor and IP. `GET /organizations/{id}/audit-logs` for owners/admins. |
| Supply chain | Pinned dependencies; `pip-audit`, `npm audit` and ruff's bandit rules run in CI. |

## Scaling notes (known limits of the MVP)

- **Run one API worker per container.** Login rate limits and the ingestion queue (FastAPI
  `BackgroundTasks`) are in-process. To scale out: move rate-limit counters to Redis and ingestion to a
  job queue (e.g. Celery/RQ/arq) with the same `run_ingestion` function.
- Isolation is enforced in application code and tests; PostgreSQL Row-Level Security would add a
  second, database-level layer.
- Ollama `base_url` is chosen by organization admins and called from the server; in a hosted multi-tenant
  deployment restrict it to an allow-list to avoid server-side request forgery.
- Retrieval is vector-only. The evaluation shows where keyword-heavy questions rank the right page lower;
  hybrid search (pgvector + PostgreSQL full-text, rank fusion) is the next quality step.
