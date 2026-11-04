# CA market: gap analysis & differentiators

_Last updated: 4 Nov 2026. Update the **Status** columns as features ship._

> **Source caveat:** most public material on competitors is vendor marketing (Suvit, AI Accountant, Vyapar TaxOne…),
> apart from ICAI's AI use-case pages. No independent market-share data or verified 2026 pricing was found.
> Treat competitor claims as unverified until checked with real CA firms.

## 1. What Indian CA firms do every month

| # | Work | Where it happens today |
| --- | --- | --- |
| 1 | Post client purchase & sales invoices into books | **Tally** (near-universal in Indian CA practice) |
| 2 | **GSTR-2B reconciliation**: client's purchase register vs GSTR-2B from the GST portal, per client, monthly | Mostly **manual in Excel** at 5–50 staff firms (ICAI) |
| 3 | Bank statement entries & reconciliation | Tally + manual / add-ons |
| 4 | GSTR-1 / GSTR-3B filing, TDS, ITR, audits | Filing utilities (not our scope) |

## 2. Competitors

| Product | Known for |
| --- | --- |
| **Suvit** | Invoices / bank statements / Excel → review → **bulk post to Tally**; bank reconciliation; CA client management |
| **AI Accountant** | Direct posting to Tally & Zoho Books, **GSTR-2B reconciliation**, multi-client support for CA firms |
| **Vyapar TaxOne** | PDF / image / Excel invoice extraction → **bulk Tally purchase vouchers**, GSTR-2B comparison |
| **ClearTax, KDK, DeltaBooks** | GST reconciliation (books vs portal); KDK has CA practice software with Tally sync |
| **FinXtract** | Bank statement & invoice extraction with Tally integration (listing only) |

**Pattern:** nobody stops at Excel. Everyone ends in **Tally**, and most add **GSTR-2B matching**.

## 3. Gaps: what we haven't built (priority order)

| # | Gap | Why it matters | Status |
| --- | --- | --- | --- |
| 1 | **Tax breakdown**: CGST / SGST / IGST, rate, HSN, line items; intra/inter-state check from GSTIN state codes | Needed by both the Tally export and 2B reconciliation; the state check catches wrongly charged tax | ☐ Not started |
| 2 | **Tally export** (Tally-importable XML) + **ledger mapping** (vendor → ledger, remembered per client) | Without it our output is re-typed by hand and the time saving disappears. #1 reason to lose a deal | ☐ Not started |
| 3 | **GSTR-2B reconciliation**: upload 2B, match against approved invoices → matched / amount differs / missing in 2B (ITC at risk) / missing in books | Monthly, recurring, painful, so a reason for a monthly subscription. Our validated data is ready for it | ☐ Not started |
| 4 | **E-invoice QR code reading** (GSTIN, invoice no., date, value from the signed QR) | Exact data with no OCR guesswork. Quick win | ☐ Not started |
| 5 | **Bank statements**: PDF → transactions → ledger suggestions → Tally | Second-biggest data-entry chore; competitors sell it | ☐ Not started |
| 6 | **CA practice features**: client master (GSTIN, PAN, FY), monthly per-client checklist (books / 2B / GSTR-1 / 3B), deadline reminders, document collection via **WhatsApp / email** | Clients send bills on WhatsApp; firms track dozens of clients' deadlines | ☐ Not started |
| 7 | **More document types**: sales invoices (GSTR-1), credit / debit notes, expense bills, handwritten bills | Completes the books, not just purchases | ☐ Not started |

## 4. What we already have (our differentiators)

| Differentiator | Notes |
| --- | --- |
| Invoice extraction (rules + optional LLM) with **human review and approval** | Nothing exported without approval |
| **Configurable validation rules per client/workspace** | Predefined toggles (GSTIN checksum, total = subtotal + tax with round-off, tax plausibility, duplicates, date checks, **billed-to-this-client**, large amount) + **custom no-code rules** |
| **Every correction audited** (before → after values), approvals and exports logged | Audit trail matters to CA firms |
| **PDF tools in-app**: merge, split per page, keep pages, rotate, **photo (JPG/PNG) → PDF** | Users never leave the platform; originals never changed |
| **Q&A over documents** with page-level citations | Research / search across a client's documents |
| **Strict client (tenant) separation**, roles, Excel export protected against formula injection | Security story for client data |

**Honest position:** these advantages only win deals once gaps 1–3 exist. Feature by feature today, a CA would
say: *"Theirs puts entries into Tally and does my 2B; yours gives me Excel."*

## 5. Discovery questions for CA meetings

The full guide (pain signals, hypotheses H1–H5, interview questions, discovery log) is in
[CA-pain-discovery.md](CA-pain-discovery.md). Short version: ask these in every demo; record the answers below.

1. How do you get purchase invoices into Tally today, and how long does it take per client per month?
2. How do you do GSTR-2B reconciliation, and what's the most painful part?
3. Do clients send bills on WhatsApp? Photos or PDFs?
4. Which tools have you tried (Suvit, others), and why did you stop or stay?

| Date | Firm | Answers / notes | Gap it supports |
| --- | --- | --- | --- |
| | | | |

## 6. Plan

1. **Demo:** show what works; use the meeting for discovery (section 5). Build nothing new the night before.
2. **Next:** gap 1 (tax breakdown) → gap 2 (Tally export + ledger mapping) → gap 3 (GSTR-2B reconciliation),
   re-ordered by what the first CA firms actually say.

## Sources

- [ICAI AI use case: AI-powered GST invoice processing & reconciliation agent](https://ai.icai.org/usecases_details.php?id=250)
- [ICAI AI use case: GST reconciliation that remembers](https://ai.icai.org/usecases_details.php?id=217)
- [ICAI AI use case: Streamlining GST ITC reconciliation](https://ai.icai.org/usecases_details.php?id=84)
- [Suvit: why CA firms need accounting automation](https://www.suvit.io/post/why-ca-firm-needs-accounting-automation)
- [Suvit: AI GST reconciliation & Tally automation](https://www.suvit.io/post/ai-gst-reconciliation-tally-automation)
- [Suvit on ICAI CMP](https://betacmp.icai.org/suvit-2)
- [Suvit – Krowdbase listing](https://www.krowdbase.com/software/suvit)
- [AI Accountant: best Tally automation tools for CAs](https://www.aiaccountant.com/blog/best-tally-automation-tools-for-cas)
- [AI Accountant: GSTR-2B reconciliation tools guide](https://www.aiaccountant.com/blog/gstr-2b-reconciliation-tools-guide)
- [AI Accountant: Tally add-on software 2026](https://www.aiaccountant.com/blog/tally-add-on-software-2026)
- [Vyapar TaxOne: automate purchase entry in Tally](https://taxone.vyapar.com/post/automate-purchase-entry-in-tally)
- [Vyapar TaxOne: Tally automation solutions comparison](https://taxone.vyapar.com/post/tally-automation-solutions-comparison)
- [KDK Software: GSTR-2A/2B reconciliation](https://www.kdksoftware.com/blog/gstr-2a-2b-reconciliation/)
- [ClearTax: AI invoice reconciliation](https://cleartax.in/s/ai-invoice-reconciliation)
- [Tally Solutions: TallyPrime AI invoice processing for SMEs](https://tallysolutions.com/tally/tallyprime-ai-invoice-processing-indian-smes/)
- [Hisab Kitab: best accounting software for CA firms](https://hisabkitab.co/best-accounting-software-for-ca-firms-in-2025)
- [CAMonk: best AI tools for CA practice in India (2026)](https://blog.camonk.com/?p=16503)
- [FinXtract listing](https://www.hunted.space/product/finxtract)
