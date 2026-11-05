# Offline desktop app + licence management: plan

_5 Nov 2026._ **Status:** admin panel built (`licensing/`, see its README). Next: customer website, app login API
(leases), then the licence check inside the desktop app. Pricing research: [CA-pricing-research.md](CA-pricing-research.md).

**Decisions taken:**

| Topic | Decision |
| --- | --- |
| Internet check | Online login **every time the app starts**; the login is valid for at most **24 hours**, even if the app stays open |
| Payment | **Manual** for now: the customer pays by UPI or bank transfer, and you mark them paid in an admin panel. Razorpay later |
| Licence | **Monthly subscription per firm**, covering a set number of computers |
| Rule | **Nothing works without an active paid subscription.** No free tier, no trial unless you grant one by hand |

---

## 1. The big picture

```
 ┌───────────────────────── YOUR SIDE (online) ─────────────────────────┐
 │  Website: register · pay instructions · download · my computers      │
 │  Admin panel: mark paid · extend · block · upload new versions       │
 │  Licence server (API + its own database)                             │
 │     holds: firms, users, subscriptions, payments, computers          │
 │     signs short-lived "permission slips" (licence leases)            │
 └──────────────────────────────▲───────────────────────────────────────┘
                                │ HTTPS, only at login (a few KB)
 ┌──────────────────────────────┴── CA'S COMPUTER (Windows) ────────────┐
 │  KnowledgeHub desktop app (one installer, no Docker, no terminal)    │
 │    window (Electron) → local web app → local API → local database    │
 │    OCR, AI models, documents and the database all stay here          │
 │    without a valid lease, the app shows only the login screen        │
 └──────────────────────────────────────────────────────────────────────┘
```

Client documents **never leave the CA's computer**. Only the login (email, password, computer ID, app version)
goes to your server. This is a strong selling point: *"your clients' data stays in your office."*

---

## 2. Customer journey (non-technical user)

1. **Website → Register:** name, firm name, email, mobile, password.
2. **Choose a plan** (e.g. monthly, up to 3 computers). The account is **Pending payment**. The dashboard shows UPI
   and bank details with a payment reference (e.g. `KH-1042`).
3. **Pays** by UPI or bank transfer and enters the UTR number (optional).
4. **You** see the payment in the admin panel → **Mark paid** → the subscription is active until the same date next
   month. The customer gets an email.
5. **Download:** the button appears only for active accounts. It's a normal Windows installer (Next → Next →
   Finish), with a desktop icon.
6. **Opens the app → login screen** (same email and password as the website). The app checks online → opens.
7. **Every next start:** login again (internet needed for a few seconds). After that, it works without internet
   for up to 24 hours.
8. **Renewal:** reminders 7, 3 and 1 days before expiry, by email and inside the app. If not renewed, the next login
   is refused with *"Your subscription ended on … Renew at …"*.

---

## 3. How the licence check works

### 3.1 The lease ("permission slip")
On login, the local app sends `email, password, computer_id, app_version` to the licence server. If the firm's
subscription is active and the computer is allowed, the server returns a **lease**:

```
{ firm_id, user_id, computer_id, plan, valid_for: 24h, subscription_ends, issued_at }
signed with the server's Ed25519 private key
```

- Only **your server** holds the private key, so nobody can create a lease. The app contains only the **public key**
  and checks the signature.
- The lease is kept **in memory only**, never written to disk. Closing the app throws it away, so **every start
  needs an online login**.
- Its validity is measured with the computer's **uptime clock**, not the date and time, so changing the Windows
  date doesn't extend it.
- The lease ends at 24 hours **or** at subscription expiry, whichever comes first.
- **Every request** to the local API (upload, review, export, chat…) checks the lease. Without a valid one, the
  answer is `402 Licence required` and the app returns to the login screen.
- One hour before expiry, a banner says *"Log in again to continue"*. Re-login happens without closing the app, so no
  work is lost.

### 3.2 Computer limits (stops sharing one subscription)
- `computer_id` = a hash of the Windows machine ID + a random ID created at installation.
- Each subscription allows **N computers** (set per plan or per firm). The first login on a new computer registers
  it, if a seat is free.
- If all seats are taken: *"This subscription is already used on 3 computers. Remove one on the website."*
- **Removing a computer** on the website is self-service, but limited (e.g. 2 changes per month) so a login can't be
  passed around. You can override this in the admin panel.
- **Block a computer or a firm** in the admin panel: it takes effect at their next login, at most 24 hours later.

### 3.3 Users
- The **licence server is the only place accounts live** in the desktop version. The firm owner adds staff
  (email + role) on the website, with no separate local sign-up.
- On the first login on a computer, the local app automatically creates the matching local user and firm, so the
  existing roles (owner / admin / member), workspaces and audit log keep working unchanged.
- Passwords are checked online at every start, so no password is stored on the computer.

### 3.4 Honest limits of protection
Software running on the customer's computer **can always be cracked by a determined expert**. The goal is to make
cheating harder than paying:

| Protection | Stops |
| --- | --- |
| Signed, in-memory, 24-hour leases | Fake licences, copying a licence file, changing the clock |
| Computer limit + limited device changes | Sharing one subscription across an office or between firms |
| Backend compiled to machine code (Nuitka), no readable Python | Casual editing to remove the check |
| Licence check at every API request, not just at start-up | Skipping the login screen |
| Server-side blocking, rate limits, login alerts | Leaked passwords, abuse |

---

## 4. What to build

### 4.1 Licence server + website (new, online), `licensing/`
Same stack you already know: FastAPI + Postgres for the API, Next.js for the website, hosted on a small VPS
(about ₹500–1,500/month) with HTTPS on your domain.

**Data model**

| Table | Main fields |
| --- | --- |
| `firms` | name, GSTIN (optional), mobile, status (pending / active / expired / blocked) |
| `users` | firm, email, password hash, role, active |
| `plans` | name, monthly price, computers included |
| `subscriptions` | firm, plan, starts, ends, computers allowed, status |
| `payments` | firm, amount, method (UPI / bank), reference, UTR, recorded by, period covered |
| `computers` | firm, computer_id, name, first seen, last login, app version, blocked |
| `releases` | version, installer file, SHA-256, notes, minimum supported version |
| `events` | audit of logins (success / failure + reason), payments, blocks, device changes |

**Website pages:** home + pricing · register · login · dashboard (status, expiry, pay instructions, payment history)
· my computers (rename / remove) · team (add staff) · download.

**Admin panel (you only):** firms list with filters (pending payment, expiring this week, expired) · record payment
→ activate or extend · change computer limit · block firm, user or computer · upload release · login history.

**App API:** `POST /app/login` → lease · `GET /app/public-key` · `GET /app/latest-version`.

**Emails:** welcome, payment received, expiring soon (7/3/1 days), expired, new computer added.

### 4.2 Licence client inside the existing app
- New setting `LICENCE_MODE=desktop` (the current web/Docker version keeps working as it is for development).
- `app/licensing/`: login proxy to the licence server, lease verification (Ed25519 public key built in), uptime-based
  expiry, a middleware that blocks every route without a lease, automatic local user and firm creation.
- Frontend: desktop login screen (replaces register/login), expiry banner, "subscription ended" screen with the
  renewal link.
- Tests: forged lease, expired lease, wrong computer, clock change, blocked firm, seat limit, server unreachable.

### 4.3 Windows desktop package
| Part | Approach |
| --- | --- |
| Window + installer | **Electron**: a real app window, desktop icon, NSIS installer, automatic updates |
| Web app | Existing Next.js standalone build, run by Electron's built-in Node |
| API | Existing FastAPI app compiled to an `.exe` with **Nuitka** (faster, and harder to read or edit) |
| Database | **Portable PostgreSQL 17 + pgvector**, started by the app on a private local port; data in `C:\ProgramData\KnowledgeHub` |
| AI models | Embeddings and reranker converted to **ONNX** (the app already uses onnxruntime for OCR), which removes PyTorch: about 1.5 GB smaller |
| Start-up | One click: the app starts the database → API → window, shows "Starting…", and shuts everything down cleanly on exit |
| Updates | Checks the licence server for a new version at login; downloads and installs with one click |

**Backups (essential for an offline product):** with everything on one computer, a dead hard disk would lose every
client's data. Built-in **automatic daily backup** to a chosen folder (a USB drive or a OneDrive / Google Drive
folder) plus **Restore backup** in settings.

---

## 5. Phases

| Phase | Work | Estimate | Result |
| --- | --- | --- | --- |
| **1** | Licence server, website, admin panel, manual payments, emails | 1–1.5 weeks | Customers can register and pay; you can activate them |
| **2** | Licence client in the app (leases, middleware, login screen, local user sync) | 1 week | The app refuses to work without an active paid subscription |
| **3** | Windows package: ONNX models, Nuitka API, portable Postgres, Electron, installer, updates, backups | 2–3 weeks | A non-technical user installs and runs it |
| **4** | Code-signing certificate, Razorpay (UPI auto-activation), GST invoices, monitoring | 1 week | Professional, self-running sales |

Estimates are for focused work and will change. **Phase 3 is the riskiest**: it must be built and tested on
Windows (a Windows PC or GitHub Actions Windows runners; we develop on Linux).

---

## 6. Things you need to arrange

| Item | Why | Rough cost |
| --- | --- | --- |
| Domain name + VPS | Website and licence server must be online all the time | ₹1,000–2,000/month |
| Email sending (e.g. Amazon SES / Brevo) | Payment and renewal emails | Free to low |
| **Code-signing certificate** (OV, for Windows) | Without it Windows shows *"Unknown publisher, Windows protected your PC"*, which scares non-technical users | about ₹15,000–30,000/year |
| A Windows test PC | Phase 3 testing | — |
| Later: Razorpay account (PAN, bank, KYC) | Automatic payments | 2% per payment |

---

## 7. Open questions for you

1. **Price and computers per firm:** e.g. ₹X/month for up to 3 computers, ₹Y per extra computer?
2. **Data after a subscription ends:** the data belongs to the CA's clients. Recommended: the app stays locked for all
   work, but the owner can still **export their data** (Excel and original files) for 30 days after expiry. This
   avoids disputes and data-protection (DPDP Act) problems. Or fully locked?
3. **Grace on renewal day:** lock exactly at expiry, or allow 3 days after expiry with a red banner (for CAs who
   pay late)?
4. **Trial:** none, or a time-limited trial you grant by hand from the admin panel (useful for demos and pilots)?
5. **Internet outage at start-up:** with the 24-hour rule, no internet at start means no work. Is that acceptable,
   or should the owner be able to request a one-time emergency code from you by phone?
