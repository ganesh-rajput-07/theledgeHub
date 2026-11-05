# KnowledgeHub AI roadmap

_Last updated: 5 Nov 2026. **One list of everything planned**, in order, with links to the detailed plans. Tick items
off here as they ship._

Detailed plans: [next-builds-plan.md](next-builds-plan.md) (A–D in depth) ·
[licensing-plan.md](licensing-plan.md) (licence system and installer) ·
[CA-gap-analysis.md](CA-gap-analysis.md) (market gaps) · [CA-pain-discovery.md](CA-pain-discovery.md) (what to
validate with CA firms) · [CA-pricing-research.md](CA-pricing-research.md) (pricing).

---

## Where we are

| Area | Status |
| --- | --- |
| Product: invoice extraction, rules per client, review & audit trail, PDF tools, Q&A, Excel export | ✅ Built |
| Licence server: customer website, admin panel, manual payments, signed 24-hour licences | ✅ Built (`licensing/`) |
| Licence check inside the app (`LICENCE_MODE=desktop`) | ✅ Built |
| Windows installer | ☐ Next |
| Tally export, GSTR-2B reconciliation | ☐ Planned |
| First paying CA firm | ☐ Not yet |

**Decisions already taken:** monthly subscription per firm with a computer limit; manual payments first; online
sign-in at every start, 24-hour licence (strict); no free tier, trials only by hand.

---

## Now: make it installable and sellable

### B. Windows installer (2–3 weeks) · details: [licensing-plan.md §4.3](licensing-plan.md)
- ☐ **Spike first:** portable PostgreSQL + pgvector + the API starting from a folder on Windows.
- ☐ Convert the embedding and reranker models to ONNX (drops PyTorch, about 1.5 GB smaller).
- ☐ Compile the API with Nuitka (faster start, harder to read or patch).
- ☐ Electron window running the Next.js standalone build; one-click start and clean shutdown.
- ☐ NSIS installer, desktop icon, data in `C:\ProgramData\KnowledgeHub`.
- ☐ **Automatic daily backup** to a chosen folder (USB / OneDrive / Google Drive) + *Restore backup*.
- ☐ Auto-update: check the licence server for a new version at sign-in.
- ☐ Ship the real licence public key in the app; build with `LICENCE_MODE=desktop`.
- ☐ Test with a non-technical person on a real Windows PC.
- **Needs:** a Windows PC or GitHub Actions Windows runners.

### Go live (before the first real customer) · checklist in the runbook v2
- ☐ Domain + small VPS with HTTPS; licence server deployed; `PUBLIC_URL`, `COOKIE_SECURE=true`.
- ☐ `generate-keys` on the server; private key backed up offline; public key into the app.
- ☐ Admin settings: UPI, bank details, GSTIN, support contact; real plans and prices.
- ☐ Daily database backup of the licence server.
- ☐ Terms of service and privacy policy pages (the sign-up form already asks to accept them).

---

## Next: win deals

### C. Tally export (1.5–2 weeks) · details: [next-builds-plan.md §C](next-builds-plan.md)
- ☐ Tally-importable XML of Purchase vouchers for approved invoices.
- ☐ CGST + SGST or IGST split from GSTIN state codes; round-off line.
- ☐ **Ledger mapping per client** (vendor → party ledger, purchase/tax/round-off ledgers), remembered.
- ☐ Optional party-ledger masters for new vendors.
- ☐ "Exported to Tally on …" mark to prevent double posting.
- ☐ Verify on a real TallyPrime (Education mode) with a pilot firm's data.

### D. GSTR-2B reconciliation + chasing (about 2 weeks) · details: [next-builds-plan.md §D](next-builds-plan.md)
- ☐ Upload the client's GSTR-2B (JSON/Excel) per month.
- ☐ Match on vendor GSTIN + normalised invoice number; probable matches by date and amount.
- ☐ Four lists: matched · amount differs · in 2B but no bill (ask the client) · bill but not in 2B (credit at risk,
  chase the vendor).
- ☐ Ready-made messages with **WhatsApp click-to-chat links** and email; track asked → resolved; carry over.
- ☐ Per-client summary: "₹X of credit at risk across N invoices."
- ☐ Verify with real 2B files from a pilot firm.

**Order of C and D:** swap them if the first CA conversations say missing bills / blocked credit hurts more
(hypothesis H1).

---

## Then: run the business without manual work

### Phase 4: licensing and payments (about 1 week)
- ☐ Code-signing certificate for the installer (avoids "Unknown publisher").
- ☐ Razorpay: UPI/card payment on the website that activates the subscription automatically.
- ☐ GST invoices for your own sales (PDF, numbered, emailed).
- ☐ Emails: welcome, payment received, renewal reminders (7/3/1 days), expired, new computer added.
- ☐ Password reset by email (today: you set a new password in the admin panel).
- ☐ Move sign-up/app-login rate limits to Redis before running more than one worker.
- ☐ Yearly plans and multi-year discounts (prices already supported as 12-month plans).

### Licence rules to revisit with real customers
- ☐ Strict 24-hour online sign-in vs a short offline grace (decided: strict for now; competitors are more lenient).
- ☐ Data access after a subscription ends (recommended: export-only for 30 days, for DPDP reasons).
- ☐ Grace days after expiry (setting exists, currently 0).

---

## Later: broaden the product (order decided by CA feedback)

From [CA-gap-analysis.md](CA-gap-analysis.md):

| # | Item | Why |
| --- | --- | --- |
| 1 | **Line items, HSN, per-rate GST checks** | Catches a wrong GST rate (the invoice_04 gap); enables rate-wise purchase ledgers in Tally |
| 2 | **E-invoice QR reading** | Exact data from the signed QR, no OCR guesswork. Quick win |
| 3 | **Bank statements** → transactions → ledger suggestions → Tally | Second-biggest data-entry chore |
| 4 | **Practice features:** client master (GSTIN, PAN, FY), monthly checklist per client, deadline reminders | Firms track dozens of clients' deadlines |
| 5 | **Document collection** via WhatsApp / email inbox, filed into the right client automatically | Clients send bills on WhatsApp at month-end (H2) |
| 6 | **More document types:** sales invoices (GSTR-1), credit/debit notes, expense bills, handwritten bills | Completes the books |
| 7 | **GST notices:** read the notice, find the documents, draft a reply, track the deadline | Rare but high stakes (H3) |
| 8 | Gujarati/Hindi invoices; iPhone HEIC photos | Real-world inputs |

---

## Always: sell and learn

- ☐ Meet 5–10 CA firms; ask the discovery questions **before** demoing; log answers in
  [CA-pain-discovery.md](CA-pain-discovery.md).
- ☐ Sit in one firm's office between the 11th and 20th of a month.
- ☐ Pilot on 50–100 real invoices per firm; **measure real accuracy** (today it's measured only on generated
  invoices).
- ☐ Validate prices with the first 5 firms (suggested: Solo ₹999, Team ₹2,499, Firm ₹4,499 per month + GST).
- ☐ Collect testimonials; turn the first pilots into paying customers.
- ☐ Update the demo kit (deck, overview, runbook) as features ship.

## Known limits today (keep honest in demos)

- Wrong GST amount/rate is not caught (totals only).
- Output is Excel; no Tally, no GSTR-2B yet.
- Accuracy measured on generated invoices only.
- Q&A needs an AI provider key for real answers.
- The app runs from the terminal until the installer exists.
