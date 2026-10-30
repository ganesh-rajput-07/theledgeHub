# RAG evaluation

Testing that the app *returns an answer* isn't enough; we measure whether it finds the **right evidence**
and refuses when the evidence isn't there.

## Method

- **Corpus** (`backend/evaluation/corpus.py`): 6 PDFs / 14 pages about a fictional company, with
  deliberate look-alikes – our revenue vs a competitor's, the leave policy vs the remote-work policy.
- **Questions** (`backend/evaluation/dataset.json`): 35 total – 28 answerable, each labelled with the
  document + page that contains the answer and the facts a correct answer must state; 7 unanswerable
  but plausible ("How many employees does Northwind have?"). Question types: `lookup`, `paraphrase`
  (no shared keywords with the source), `distractor` (a look-alike page exists).
- **Metrics**
  - *Recall@K / Hit rate@K* – is the labelled page among the top K chunks?
  - *Precision@K* – share of the top K that are labelled pages (with one relevant page per question,
    the maximum @K is 1/K).
  - *MRR* – 1 / rank of the first relevant chunk.
  - *Not-found sweep* – for each `RAG_MIN_SCORE`, share of answerable questions still attempted and of
    unanswerable questions refused before any LLM call.
  - *End-to-end* (with a provider) – answered, facts present, grounded (≥1 citation), citation precision
    (citations pointing at a labelled page), unanswerable refused, latency, tokens.

```bash
cd backend
.venv/bin/python -m evaluation                                    # retrieval metrics (free, local)
.venv/bin/python -m evaluation --chunk-sizes 150,250,400          # compare chunking
.venv/bin/python -m evaluation --provider mock                    # + end-to-end, offline
ANTHROPIC_API_KEY=... .venv/bin/python -m evaluation --provider anthropic --model claude-opus-5-5
.venv/bin/python -m evaluation --provider ollama --model qwen3:4b # local model
```

It runs against a separate `knowledgehub_eval` database and writes `backend/evaluation/results/latest.{md,json}`.
`tests/integration/test_rag_quality.py` re-runs the retrieval part in CI as a regression guard.

## Results (30 Oct 2026 · `all-MiniLM-L6-v2` · chunk 250 / overlap 50)

| Metric | @1 | @3 | @5 | @8 |
| --- | --- | --- | --- | --- |
| Recall / hit rate | 86% | 96% | 100% | 100% |
| Precision | 86% | 32% | 20% | 12% |

**MRR 0.906.** Top-1 by type: distractor 100% (3/3), paraphrase 90% (9/10), lookup 80% (12/15).

The right page is always in the top 5, and the 8 chunks sent to the model always include it, so the model
always *has* the evidence. Look-alike documents were never confused.

### Not-found threshold

| RAG_MIN_SCORE | answerable attempted | unanswerable refused |
| --- | --- | --- |
| 0.25 (old default) | 100% | 0% |
| **0.30 (new default)** | **100%** | **14%** |
| 0.35 | 100% | 43% |
| 0.40 | 86% | 57% |

**Decision:** the original 0.25 never fired – questions about the same company always look a little
similar (unanswerable top scores were all ≥ 0.30). We moved the default to **0.30**, which refuses some
off-topic questions before spending the customer's tokens while keeping every answerable one. 0.35 scored
better here but sits too close to real answerable questions to trust on 28 samples. Most refusals are left
to the model (system prompt rule: reply `NOT_FOUND` if the sources don't contain the answer).

### End-to-end (mock provider)

| Answered | Facts correct | Grounded | Citation precision | Unanswerable refused |
| --- | --- | --- | --- | --- |
| 100% | 54% | 100% | 86% | 14% |

The mock only quotes the start of the top source, so these rows test the *plumbing* (citations always
point at retrieved chunks; 86% point at the labelled page = top-1 accuracy). Fact accuracy and refusals
need a real model: run the command above with your provider. Not yet measured with a real LLM – no
provider key was available during development, and the local Ollama model was too slow on the dev machine.

## Known weaknesses (from the misses)

| Question | Rank of right page | Why |
| --- | --- | --- |
| What was Northwind's total revenue in fiscal year 2025? | 5 | Page 1 (CEO letter, "2025", company name) out-scores the financial page. |
| Was the company profitable in 2025? | 3 | "Profit" ↔ "operating profit" is weak for a small embedding model. |
| How many customers does Northwind have? | 2 | Product-manual intro is semantically close. |
| What revenue target did the board set for next year? | 3 | Financial-overview page competes with the outlook page. |

These are keyword-heavy lookups, which is exactly what **hybrid search** (vector + PostgreSQL full-text
with rank fusion) or a **reranker** fixes. Both are on the roadmap; this harness will show whether they help.

**Chunk size** could not be compared on this corpus: every page is under 150 tokens, so 150/250/400 all
give one chunk per page. Use `--chunk-sizes` with longer real documents to tune it.

Retrieval latency in the report (~1 s p50) was measured on a heavily loaded machine (load average > 15);
query embedding with MiniLM normally takes tens of milliseconds.
