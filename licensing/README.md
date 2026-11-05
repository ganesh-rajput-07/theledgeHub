# KnowledgeHub licence server

The online side of licensing: **admin panel** today (plans and prices, firms, payments, trials, computers, settings,
activity log). The customer website and the desktop-app login API come next. See
[`docs/licensing-plan.md`](../docs/licensing-plan.md).

## Run it locally

```bash
cd licensing
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements-dev.txt
cp .env.example .env                       # uses the dev Postgres on :5433, database "licensing"
docker exec knowledgehub-db psql -U knowledgehub -c "CREATE DATABASE licensing"   # once
.venv/bin/alembic upgrade head
.venv/bin/python -m app.cli create-admin you@example.com "Your Name"            # asks for a password
.venv/bin/uvicorn app.main:app --port 8002
```

Open http://localhost:8002 and sign in. The same `create-admin` command resets a forgotten password.

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

## Tests

```bash
.venv/bin/python -m pytest      # uses a separate licensing_test database
.venv/bin/ruff check .
```

## Production notes

- Serve behind HTTPS (e.g. Caddy) and keep `COOKIE_SECURE=true`. Run uvicorn with `--proxy-headers
  --forwarded-allow-ips=127.0.0.1` so the same-origin check sees `https`.
- Use a strong, unique admin password; 5 wrong attempts lock the account for 15 minutes.
- Back up the database daily: it is your record of who paid.
