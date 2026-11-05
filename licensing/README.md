# KnowledgeHub licence server

The online side of licensing, one FastAPI service:

| Part | URL | For |
| --- | --- | --- |
| Customer website | `/` | Pricing, register, pay instructions, "I have paid", download, computers, team, password |
| Admin panel | `/admin` | You: plans and prices, firms, payments, trials, computers, logins, settings, activity log |
| App login API | `/api/app/v1/...` | The desktop app: login at every start → signed 24-hour lease |

Design: [`docs/licensing-plan.md`](../docs/licensing-plan.md).

## Run it locally

```bash
cd licensing
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements-dev.txt
cp .env.example .env                       # uses the dev Postgres on :5433, database "licensing"
docker exec knowledgehub-db psql -U knowledgehub -c "CREATE DATABASE licensing"   # once
.venv/bin/alembic upgrade head
.venv/bin/python -m app.cli create-admin you@example.com "Your Name"            # asks for a password
.venv/bin/python -m app.cli generate-keys                                       # once: lease signing key
.venv/bin/uvicorn app.main:app --port 8002
```

Website: http://localhost:8002 · Admin: http://localhost:8002/admin. The same `create-admin` command resets a
forgotten admin password.

**The signing key (`keys/lease_private.pem`) is the most important secret you have.** Anyone with it can create
licences. Never commit it (it's in `.gitignore`), back it up somewhere safe, and keep the printed public key: it
goes into the desktop app. Replacing the key logs out every installed app.

## How a customer gets going

1. Registers on `/register` (chooses a plan) → firm is **Pending payment**; their account page shows the amount
   incl. GST, your UPI/bank details and their `KH-` reference.
2. Pays, then clicks **I have paid** with the UTR → it appears on your admin dashboard under *Customers say they've
   paid*.
3. You check the UTR in your bank app → **Check & activate** (form is pre-filled) → **Record payment**.
4. Their account shows **Download for Windows** (link set in Admin → Settings → Desktop app).
5. They install and log in with the same email and password; each new computer takes a seat.

## Daily use

| I want to… | Where |
| --- | --- |
| Change a price or computer limit | **Plans & prices → Edit**. Applies to new sales and renewals; firms keep the price they paid for |
| Stop selling a plan | Edit → untick **On sale** (existing firms keep it) |
| Private deal for one firm | New plan, untick **Show on the website pricing page** |
| Activate a firm after UPI / bank payment | **Firms →** firm **→ Record a payment**. The price-list total is calculated and pre-filled |
| Renew | Same form. Before expiry it continues from the end date; after expiry it starts today |
| Give a trial / goodwill days / fix a mistake | Firm page → **Start a free trial** / **Adjust end date or computers** (reason required) |
| Stop a firm that misuses the licence | Firm page → **Block firm** |
| Monthly figures for your CA | **Payments →** month **→ Download CSV** |
| UPI ID, bank details, GST %, grace days, login validity | **Settings** |
| Who changed what | **Activity log** (every sign-in, price change, payment, block, correction) |

## App login API (contract for the desktop app)

`POST /api/app/v1/login`

```json
{"email": "...", "password": "...", "machine_id": "stable id of this installation (16-200 chars)",
 "machine_name": "PARTNER-CABIN", "app_version": "1.0.0"}
```

Success `200`:

```json
{"lease": "<EdDSA JWT>", "expires_at": "2026-11-06T11:50:50+00:00", "valid_seconds": 86399,
 "user": {"name": "...", "email": "...", "role": "owner"}, "firm": {"name": "...", "reference": "KH-48072"},
 "subscription": {"plan": "Team", "ends_on": "2026-12-04", "status": "active", "days_left": 30, "trial": false},
 "latest_version": "1.0.0"}
```

Refusals return `{"code": ..., "message": ...}` with a message ready to show the user:

| HTTP | code | When |
| --- | --- | --- |
| 401 | `invalid_credentials` | Wrong email or password |
| 423 | `locked` | 5 wrong passwords: locked for 15 minutes |
| 402 | `no_subscription` / `expired` | Not paid yet / subscription (and grace) ended |
| 403 | `firm_blocked` / `computer_blocked` / `computer_limit` | Blocked by you / all computer seats used |
| 426 | `update_required` | App older than *Minimum version allowed* |
| 429 | `rate_limited` | Too many attempts from one network |
| 503 | `server_not_ready` | Signing key not created yet |

The lease claims: `sub` (user id), `mid` (sha256 of the machine id), `firm`, `user`, `plan`, `computers`,
`ends_on`, `trial`, `iat`, `exp`, `ttl`, `aud` = `knowledgehub-desktop`, `iss` = `knowledgehub-licensing`. The app
must verify the signature with the public key, check `aud`, `iss` and `mid`, keep the lease **in memory only**,
and count `ttl` down on its own uptime clock (not the wall clock). `app/lease.py: verify()` is the reference check.
`GET /api/app/v1/public-key` returns the public key.

## The desktop app side (product app)

The product app enforces the licence when started with `LICENCE_MODE=desktop` (see `backend/.env.example`):

| Setting | Value |
| --- | --- |
| `LICENCE_MODE` | `desktop` |
| `LICENCE_SERVER_URL` | this server, e.g. `https://licence.your-domain` |
| `LICENCE_PUBLIC_KEY_FILE` | the public key printed by `generate-keys` (default `backend/app/licensing/licence_public_key.pem`) |
| `APP_VERSION` | sent at login; compared with *Minimum version allowed* |
| `NEXT_PUBLIC_LICENCE_MODE=desktop`, `NEXT_PUBLIC_LICENCE_SITE_URL` | frontend build: hides sign-up, shows the licence banner |

What happens in the app: sign-in goes to `/api/app/v1/login`; the lease is verified (signature, audience, this
computer) and kept in memory; its time counts down on the uptime clock; every API call returns `402` once it has
run out, which sends the user back to sign-in; the firm and user are created locally on first sign-in; signing out
or restarting forgets the lease.

## Tests

```bash
.venv/bin/python -m pytest      # uses a separate licensing_test database
.venv/bin/ruff check .
```

## Production notes

- Serve behind HTTPS (e.g. Caddy) and keep `COOKIE_SECURE=true`. Run uvicorn with `--proxy-headers
  --forwarded-allow-ips=127.0.0.1` so the same-origin check sees `https`.
- Set `PUBLIC_URL` to your real address (used in messages such as "Renew at …").
- Use a strong, unique admin password; 5 wrong attempts lock the account for 15 minutes.
- Rate limits for sign-ups and app logins are kept in memory, so run a single worker (or move them to Redis
  before scaling out).
- Password reset by email isn't built yet: customers contact you, and you set a new password in the firm's
  *Logins* panel (this also unlocks a locked account).
- Back up the database daily: it is your record of who paid.
