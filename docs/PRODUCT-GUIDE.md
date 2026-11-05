# KnowledgeHub AI: complete product guide

_Last updated: 4 Nov 2026. One place for **what is built, how to run it, how to use it, and how to demo it**._

Related documents:
[CA-gap-analysis.md](CA-gap-analysis.md) (market and competitors) ·
[CA-pain-discovery.md](CA-pain-discovery.md) (finding the real pain) ·
[architecture.md](architecture.md) (technical design and security model) ·
[evaluation.md](evaluation.md) (search quality measurements) ·
Demo files: [`demo/`](../demo) (deck, playbook, sample files, screenshots)

---

## 1. What it is (in one minute)

KnowledgeHub AI turns a CA firm's incoming documents into **checked, approved data**, without anyone leaving the
platform:

```
Upload (PDF / WhatsApp photo / merge / split)  ->  Read the invoice (OCR + rules)  ->  Check it (validation rules)
   ->  Human review & correction (audited)  ->  Approve  ->  Export to Excel
```

Plus: **ask questions across all documents** and get answers with the exact page as the source.

Built for: CA firms and accountants (initial market: Surat). Each **workspace = one client**, each **organization =
one firm**.

---

## 2. Feature inventory: what is built

### 2.1 Documents & intake
| Feature | What it does |
| --- | --- |
| Upload | PDF, DOCX, TXT, Markdown, **JPG/PNG photos** (up to 25 MB each, drag-and-drop, many at once) |
| Photo → PDF | Phone/WhatsApp photos become upright one-page PDFs (camera rotation applied), then OCR'd |
| OCR | Scanned PDFs and photos are read automatically (RapidOCR, runs locally) |
| File safety | File type checked by content (a renamed `.exe` is refused); originals stored privately |
| Status | Live status per document: Queued → Processing → Ready / Failed (with the reason) |

### 2.2 PDF page tools (no need for other PDF software)
| Tool | Use for |
| --- | --- |
| **Merge** | Combine several PDFs in a chosen order (e.g. a vendor's monthly bills) |
| **One document per page** | Split a vendor's multi-invoice PDF into separate invoices |
| **Keep selected pages** | New PDF with chosen pages in click order (also how you "delete" cover/blank pages) |
| **Rotate** | Fix sideways scans (selected pages, or all) |
| Page thumbnails | See the pages before choosing |
| Origin labels | Every new document says where it came from ("Merged from 2 documents", "Split from…") |

Originals are **never changed**: every tool creates a new document, which is processed automatically.

### 2.3 Invoice extraction & review
| Feature | What it does |
| --- | --- |
| Extraction | Reads vendor, vendor GSTIN, buyer, buyer GSTIN, invoice no., date, subtotal, tax, total |
| Reader | Fast rule-based reader for Indian GST invoices; optional AI model for names and unusual layouts |
| Review screen | PDF on the left, extracted fields on the right, problems shown next to the field |
| Corrections | Edit any field; **every change is recorded** (who, when, old → new value) |
| Approval | Approve only when there are no errors; editing an approved invoice sends it back to review |
| Excel export | Approved invoices only, real numbers and dates (sum/sort in Excel), safe against formula injection |

### 2.4 Validation rules (per client)
Predefined rules, each with on/off, **Error (blocks approval) / Warning (flag only)** and its own setting:

| Rule | Default | Setting |
| --- | --- | --- |
| GSTIN is valid (format + check digit) | On · Error | - |
| Total = subtotal + tax | On · Error | Round-off allowed (₹1) |
| Tax rate is plausible | On · Warning | Maximum tax % (28) |
| Duplicate invoice (vendor GSTIN + invoice no.) | On · Error | - |
| Invoice date not in the future | Off | - |
| Invoice date within a period | Off | Maximum age in days |
| **Billed to this client** | Off | Client's GSTIN |
| Large amount | Off | Amount above ₹ |

**Custom rules** without code: *If [field] [condition] [value] → [Error/Warning]: [message]*. Conditions depend on the
field type (amounts: greater/less than; dates: before/after; text: contains/equals; any: is empty).
Changing rules re-checks every invoice awaiting review. Only owners/admins can change rules.

### 2.5 Research (Q&A over documents)
- Ask questions in plain language; answers come **only from the client's documents**.
- Every answer shows **citations**: document, page, quoted text, with "Open page N".
- Says "not found" instead of guessing; follow-up questions understand context.
- Search: meaning-based + keyword search, re-ranked by a second model (measured: right page first 93% of the time).
- AI provider: **bring your own key** (OpenAI, Anthropic Claude, Google Gemini) or local Ollama. Keys are encrypted
  and never shown again.

### 2.6 Firm management & security
| Feature | Details |
| --- | --- |
| Organizations, workspaces | Firm → clients; every workspace fully separated |
| Roles | Owner, Admin (manage keys, members, rules, workspaces), Member (upload, review, chat) |
| Accounts | Sign-up/login, sessions in secure cookies, lock after 5 wrong passwords |
| Audit trail | Settings → Activity: logins, uploads, deletions, corrections, approvals, exports, rule and key changes |
| Isolation | Another firm's data always answers "not found"; covered by automated tests on every route |

---

## 3. Running it

### 3.1 First-time setup
```bash
./setup.sh               # Python 3.12 venv, dependencies, backend/.env with secrets, Postgres+pgvector (Docker),
                         # migrations, AI models, OCR check, frontend build, tests
```
Options: `--no-db`, `--no-model`, `--no-frontend`.

### 3.2 Daily use (development)
```bash
./run.sh                 # API on http://127.0.0.1:8001 + web app on http://localhost:3000
./run.sh api             # API only (docs at http://127.0.0.1:8001/docs)
./run.sh web             # web app only
```

### 3.3 Full stack in Docker
```bash
./run.sh docker          # Postgres + API (:8001) + web (:3000), migrations run automatically
```

### 3.4 After pulling new code
```bash
cd backend && .venv/bin/alembic upgrade head   # apply database changes (Docker does this by itself)
```

### 3.5 Important settings (`backend/.env`)
| Setting | Default | Meaning |
| --- | --- | --- |
| `API_PORT` | 8001 | API port |
| `MAX_UPLOAD_MB` | 25 | Upload limit per file |
| `RETRIEVAL_MODE` / `RERANK_ENABLED` | hybrid / true | Search quality settings (see evaluation.md) |
| `RAG_MIN_SCORE` | 0.30 | Below this, the answer is "not found" |
| `INGESTION_MODE` | inline | `queue` = separate workers (`python -m app.worker`) for more load |
| `LOGIN_MAX_FAILURES` | 5 | Account lock threshold |
| `OLLAMA_BASE_URL` | http://localhost:11434 | Local AI models |

### 3.6 Quality checks
```bash
cd backend && .venv/bin/python -m pytest          # 237 tests incl. tenant isolation and quality guards
.venv/bin/python -m evaluation                    # search quality report
```

---

## 4. How to use it (step by step)

1. **Sign up** (`/register`): your name, email, password, firm name. A "General" workspace is created.
2. **Settings → Workspaces:** create one workspace per client (e.g. "Shree Textiles").
3. **Settings → AI providers** (optional): connect an API key, or use rules only (no AI needed for invoices).
4. **Settings → Members:** add staff (they must register first) as Member or Admin.
5. **Documents:** drag in invoices (PDFs or photos). Wait for **Ready**.
   - Multi-invoice PDF? Click **Pages** (📄 icon) → **One document per page**.
   - Sideways scan? **Pages** → **Rotate**. Unwanted pages? Select the pages to keep → **Keep selected pages**.
   - Several PDFs belong together? Tick them → **Merge selected**.
6. **Rules** (once per client): switch on "Billed to this client" with the client's GSTIN; add custom rules.
7. **Review:** click **Extract N new**. For each invoice: compare with the PDF, fix red fields, **Approve**.
8. **Excel:** export approved invoices.
9. **Research:** ask questions across the client's documents; click citations to open the page.
10. **Settings → Activity:** see who did what.

---

## 5. Demo kit (`demo/`)

| File | Purpose |
| --- | --- |
| `demo/KnowledgeHub-AI-Demo.pdf` / `.pptx` | 16-slide deck (present from the PDF; speaker notes are in the PPTX) |
| `demo/KnowledgeHub-AI-Overview.pdf` / `.docx` | Client leave-behind: overview, checks, data security, pilot proposal |
| `demo/KnowledgeHub-AI-Demo-Playbook.pdf` / `.docx` | Private script: setup, steps, what to say, what not to claim, objections, questions |
| `demo/screenshots/focused/` | Close-up, highlighted screenshots used in the deck |
| `demo/KnowledgeHub-Runbook-v2.pdf` / `.docx` | Internal runbook v2: whole system, running it, customer journey, admin tasks, pricing, licence rules, go-live checklist |
| `demo/KnowledgeHub-Runbook-v2-Slides.pdf` / `.pptx` | The same runbook as 15 slides |
| `demo/screenshots/runbook/` | Website and admin panel screenshots used in the runbook |
| `demo/sample-files/` | 6 invoices + a WhatsApp photo + an annual report (see below) |
| `demo/screenshots/` | Current screenshots of every screen |

Sample files (`truth.json` has the correct values):

| File | What it shows in the demo |
| --- | --- |
| `invoice_01.pdf` | Clean digital invoice |
| `invoice_02.pdf` | Clean invoice; **its WhatsApp photo is a duplicate** |
| `invoice_03.pdf` | Scanned invoice (OCR), large amount |
| `invoice_04.pdf` | **Wrong GST amount: NOT caught yet** (needs line-item checks, see §7) |
| `invoice_05.pdf` | **Wrong total**: caught ("total says … but subtotal + tax is …") |
| `invoice_06.pdf` | Scanned **duplicate of invoice_01**: caught |
| `whatsapp-photo-invoice.png` | Phone photo → PDF → OCR → caught as duplicate of invoice_02 |
| `shree-textiles-annual-report.pdf` | 3 pages for page tools and Q&A ("Which invoices need director approval?") |

The full demo script is in the playbook (DOCX). Short version: **upload → photo → review the wrong total →
duplicate photo → rules ("billed to this client" + custom rule) → approve → Excel → Q&A → activity log**.

---

## 6. Limits today (be honest about these)

- **Extraction accuracy is measured on generated invoices only.** Real invoices (crumpled photos, stamps, handwriting,
  Gujarati) will score lower. Measure on real client invoices before promising numbers.
- **Totals only**: no line items, HSN or CGST/SGST/IGST split yet, so a wrong GST *rate* is not detected
  (`invoice_04.pdf`).
- **Output is Excel**, not Tally entries; no GSTR-2B reconciliation yet.
- Page tools work on PDFs and photos only (not DOCX/TXT); iPhone HEIC photos are not accepted (WhatsApp sends JPEG).
- Q&A needs an AI provider key for real answers (the offline demo model only quotes the source).
- One API worker per container by default (uploads and extractions run inside the API process).

---

## 7. Roadmap (from the gap analysis)

1. **Tax breakdown**: line items, HSN, CGST/SGST/IGST, rate checks, intra/inter-state check from GSTIN state codes.
2. **Tally export**: Tally-importable XML with per-client ledger mapping.
3. **GSTR-2B reconciliation**: matched / amount differs / missing in 2B (credit at risk) / missing in books, plus
   vendor and client reminders.
4. E-invoice QR reading · bank statements · WhatsApp/email intake · per-client monthly checklist.

Order to be decided by real CA conversations ([CA-pain-discovery.md](CA-pain-discovery.md)).
