# KnowledgeHub AI – web app

Next.js 16 (App Router, Cache Components) + TypeScript + Tailwind CSS 4 + TanStack Query.

```bash
npm ci
cp .env.example .env.local   # BACKEND_URL=http://127.0.0.1:8001
npm run dev                  # http://localhost:3000  (or ./run.sh web from the repo root)
```

## How it talks to the API

The browser never calls FastAPI directly and never sees a token:

- `src/app/api/auth/*` – login / register / logout. Tokens from FastAPI are stored in **httpOnly,
  SameSite=Lax cookies** (unreadable by page JavaScript, so XSS can't steal a session).
- `src/app/api/backend/[...path]` – forwards `/api/backend/<path>` to `BACKEND_URL/api/v1/<path>`, attaching
  the access token. It refreshes the token *before* forwarding when it's about to expire, streams request
  bodies (uploads up to 25 MB are never buffered), and rejects cross-site state-changing requests.
- The `(app)` route group checks the session cookie server-side and redirects to `/login` without it.

Next.js' `proxy` (formerly middleware) is deliberately not used: it buffers request bodies and silently
truncates them at 10 MB.

## Pages

| Route | Purpose |
| --- | --- |
| `/login`, `/register` | Sign in / create account + organization |
| `/w/[id]` | Workspace overview |
| `/w/[id]/documents` | Upload (drag & drop), live ingestion status, open, reprocess, delete |
| `/w/[id]/research` | Conversations · chat with citation chips · sources panel (opens the PDF at the cited page) |
| `/org/[id]/settings` | AI provider keys (BYOK), members & roles, workspaces |
