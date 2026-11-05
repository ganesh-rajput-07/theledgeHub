# Next builds: thinking and plan

_5 Nov 2026. Draft for discussion. Follows [CA-gap-analysis.md](CA-gap-analysis.md),
[CA-pricing-research.md](CA-pricing-research.md) and [licensing-plan.md](licensing-plan.md)._

**Goal:** turn "a good checker that outputs Excel" into "the checked step before Tally, plus what's missing for
GST", delivered as an app a CA can install.

| # | Build | Why | Rough effort |
| --- | --- | --- | --- |
| A | Licence check inside the app | Without it, the licence server protects nothing | ~1 week |
| B | Windows installer | Without it, no CA can use the app on their own | 2–3 weeks |
| C | **Tally export** | Without it, the CA re-types our output and the time saving disappears. #1 reason to lose a deal | 1.5–2 weeks |
| D | **GSTR-2B reconciliation + chasing lists** | Monthly, deadline-driven, money at stake; competitors match numbers but don't run the chasing | ~2 weeks |

Estimates are for focused work and will move. **A key finding:** our current extraction (vendor GSTIN, invoice
number, date, subtotal, tax total) is already enough to start C and D. The CGST/SGST/IGST split comes from the
GSTIN state codes (first two digits): same state → CGST + SGST (half each), different states → IGST. Line items
and per-rate checks can come later.

---

## A. Licence check inside the app

**Status: built (5 Nov 2026).** `backend/app/licensing/`, desktop sign-in in `/auth/login`, enforcement
middleware, licence banner and 402 handling in the frontend. Tested end to end against the real licence server.

**What changes in the product app (`backend/`, `frontend/`):**

| Piece | Design |
| --- | --- |
| Mode switch | `LICENCE_MODE=off` (today's behaviour, for development) / `desktop` (enforced) |
| Login | In desktop mode the app's login screen calls the licence server (`POST /api/app/v1/login`) through the local API, so the password never touches the browser storage |
| Lease | Verified with the built-in **public key**: signature, `aud`, `iss`, and `mid` = this computer. Kept **in memory only** |
| Expiry | Counted down on the **uptime clock** (`time.monotonic()`), not the Windows date, so changing the date doesn't help |
| Enforcement | Middleware: every API route except `/health` and the login returns `402 Licence required` without a valid lease |
| Local users | First login on a computer creates the matching local organisation and user automatically (name, email, role from the lease) |
| UX | Banner 1 hour before expiry: "Log in again to continue" (re-login without closing the app, no work lost). Clear screens for each refusal code |
| Machine ID | Windows `MachineGuid` + a random ID created at install, hashed |

**Decided (5 Nov 2026): keep strict** (online login every start, 24 hours max). Options considered: Today's rule is "online login every start, 24 hours max". No CA product we
found is this strict, and a bad internet day near the 20th could lose a customer. Options:

1. Keep strict (24 h, login each start).
2. Login online at start; if the internet is down, allow starting with the last lease for up to
   **3 days** after it was issued. Store it encrypted and tied to the machine. Still blocks unpaid use: the lease
   can't be renewed without paying.
3. Weekly login (7 days, survives restarts).

Tests: forged / expired / other-machine lease, clock change, blocked firm, seat limit, server unreachable,
grace-period rules.

## B. Windows installer

As in [licensing-plan.md](licensing-plan.md) §4.3: Electron window, Next.js standalone, FastAPI compiled with
Nuitka, portable PostgreSQL + pgvector, models converted to ONNX (removes PyTorch, about 1.5 GB smaller),
automatic daily backup, auto-update.

**Needs:** a Windows PC or GitHub Actions Windows runners for building and testing, and later a code-signing
certificate. **Risk:** highest of the four; do a spike first (Postgres + pgvector starting from a portable folder
on Windows) before committing to the full build.

## C. Tally export

**What the CA does today:** types each purchase bill into Tally as a Purchase voucher: party (vendor) ledger,
purchase ledger, CGST/SGST or IGST ledgers, round-off.

**What we'd generate:** a Tally-importable XML file of **Purchase vouchers** for approved invoices, imported in
TallyPrime via *Import → Transactions*.

| Voucher part | From our data |
| --- | --- |
| Date, supplier invoice no., supplier invoice date | Invoice date, invoice number |
| Party ledger (credit, total) | Vendor name → **mapped** to the client's Tally ledger |
| Purchase ledger (debit, subtotal) | Per client default, e.g. "Purchase @18%"; rate inferred from tax ÷ subtotal when it's one standard rate |
| Tax ledgers (debit) | Intra-state: CGST + SGST (half each); inter-state: IGST, from GSTIN state codes |
| Round-off | Difference between total and subtotal + tax (we already detect ₹1 round-off) |
| Narration | "Imported from KnowledgeHub · <file name>" |

**Ledger mapping per client (the part that saves time):**
- First export for a client: we list the vendors and ask for each Tally ledger name (pre-filled with the vendor
  name), plus the purchase/tax/round-off ledger names. Remembered per client.
- Later exports reuse the mapping; only new vendors are asked.
- Optional: also export **party ledger masters** (name, GSTIN, state) so new vendors are created in Tally.

**Checks before export:** only approved invoices, no duplicates already exported (keep an "exported to Tally on …"
mark), tax split matches GSTIN states, mapping complete.

**Needs to be verified on a real TallyPrime** (Education mode is free) with a CA's company: the exact XML tags,
how ledger names must match, and how errors are reported. Ask the first pilot firm for an anonymised company
backup or a screen-share.

**Later:** line items, HSN and per-rate purchase ledgers, which also enable "wrong GST rate" checks (the
invoice_04 gap).

## D. GSTR-2B reconciliation and chasing

**Input:** the client's GSTR-2B for a month, downloaded by the CA from the GST portal (JSON or Excel), uploaded to
the client's workspace. (Direct portal access needs GSP/API registration: not now.)

**Matching our approved invoices against 2B:**

| Step | Rule |
| --- | --- |
| Key | Vendor GSTIN + **normalised** invoice number (upper-case, strip spaces, `/`, `-`, leading zeros) |
| Fallback | Same GSTIN, date within a few days, amount within ₹1–10 → "probable match", for the CA to confirm |
| Compare | Taxable value and tax (IGST / CGST / SGST), tolerance ₹1 |

**Result lists (the product):**

| List | Meaning | Who acts |
| --- | --- | --- |
| ✅ Matched | In books and in 2B, amounts agree | Nobody |
| ⚠️ Amount differs | Same invoice, different value or tax | CA checks with the vendor or corrects the books |
| 📥 In 2B, no bill received | The vendor filed it, but the client hasn't sent the bill | **Ask the client** for the bill |
| 🚨 Bill received, not in 2B | Vendor hasn't filed → **tax credit at risk** | **Chase the vendor** |

**Chasing (where competitors stop):**
- Per vendor and per client: ready-made messages ("Please file invoice SG-07842 of 27-Apr in GSTR-1…").
- **WhatsApp click-to-chat links** (`wa.me/<number>?text=…`) open WhatsApp with the message ready. No WhatsApp
  API account needed. Email as a second option.
- Track each item: open → asked → resolved, with dates. Next month, unresolved items carry over.
- Summary per client for the CA: "₹38,420 of credit at risk across 6 invoices from 3 vendors."

**Needs to be verified** with real 2B files from a pilot firm (the JSON/Excel layout, amendments, credit notes,
reverse charge).

---

## Suggested order

| Weeks | Work | Why this order |
| --- | --- | --- |
| 1 | **A** licence check (+ offline-grace decision) | Small, and makes the licence server meaningful |
| 1–2 (parallel) | **B spike**: Postgres + pgvector + API starting on Windows | Find out early if the riskiest part works |
| 2–4 | **C** Tally export, tested on real TallyPrime with a pilot firm | Removes the #1 reason to lose a deal |
| 4–5 | **B** full installer | Needed before self-service sales |
| 5–7 | **D** GSTR-2B + chasing | The monthly, recurring reason to pay |

**Re-order C and D** if the first CA conversations say 2B and missing bills hurt more than Tally entry (hypothesis
H1 in [CA-pain-discovery.md](CA-pain-discovery.md)).

## Questions to ask pilot firms (adds to the discovery guide)

1. How are purchase bills entered in Tally today: one ledger per vendor? Rate-wise purchase ledgers? Who does it?
2. Can you share an anonymised Tally company (or screen-share) so we can test imports?
3. Can you share last month's GSTR-2B (JSON/Excel) for one client?
4. When credit is missing from 2B, how do you chase the vendor today? How long does it take?
5. How often is your office internet down when you start work?
