"""Benchmark invoice field extraction on local hardware: OCR + regex baseline vs local LLMs via Ollama.

    python -m evaluation.invoices                                   # once: generate the test invoices
    python -m evaluation.extraction_benchmark                       # regex baseline only (no LLM needed)
    python -m evaluation.extraction_benchmark --models qwen2.5:1.5b qwen2.5:3b

For each model it reports per-field accuracy and seconds per invoice for two strategies:
  llm    - the model alone reads the text and returns JSON
  hybrid - regex values that pass validation win; the model fills the rest (and the vendor/buyer names)
The regex baseline is written for the generator's layouts, so it flatters itself on this data: treat its
numbers as an upper bound for regex on real invoices. Results are also written to evaluation/results/.
"""

import argparse
import json
import re
import time
from datetime import UTC, date, datetime
from pathlib import Path

from app.core.config import get_settings
from app.extraction.extractor import llm_extract, merge
from app.extraction.invoice import extract_invoice
from app.extraction.schema import INVOICE
from app.extraction.values import parse_amount, parse_date
from app.ingestion.extractors import extract
from app.llm.base import LLMError
from app.llm.ollama_provider import OllamaProvider

HERE = Path(__file__).parent
FIELDS = [spec.key for spec in INVOICE.fields]
AMOUNT_FIELDS = {spec.key for spec in INVOICE.fields if spec.type == "amount"}
AMOUNT_TOLERANCE = 0.02  # the generator splits tax into two rounded halves (CGST + SGST)


# ---------------------------------------------------------------- text acquisition
def read_text(path: Path) -> tuple[str, bool, float]:
    """The same text the app extracts from a PDF (embedded text, OCR for scans). Returns (text, used_ocr, seconds)."""
    start = time.perf_counter()
    pages = extract(path.read_bytes(), "application/pdf")
    return "\n".join(p.text for p in pages), any(p.ocr for p in pages), time.perf_counter() - start


# ---------------------------------------------------------------- scoring
def matches(field: str, got, want) -> bool:
    if got in (None, ""):
        return False
    if field in AMOUNT_FIELDS:
        amount = parse_amount(got)
        return amount is not None and abs(amount - float(want)) <= AMOUNT_TOLERANCE
    if field == "invoice_date":
        return parse_date(got) == (want if isinstance(want, str) else date.isoformat(want))
    return re.sub(r"[^a-z0-9]", "", str(got).casefold()) == re.sub(r"[^a-z0-9]", "", str(want).casefold())


def score(rows: list[dict], truths: list[dict], key: str) -> dict[str, float]:
    return {
        field: sum(matches(field, (row[key] or {}).get(field), truth[field]) for row, truth in zip(rows, truths,
                                                                                                   strict=True))
        / len(rows)
        for field in FIELDS
    }


# ---------------------------------------------------------------- reporting
def print_table(title: str, accuracy: dict[str, float], seconds: float) -> None:
    overall = sum(accuracy.values()) / len(accuracy)
    cells = "  ".join(f"{field.replace('invoice_', 'inv_')[:12]:>12}" for field in FIELDS)
    print(f"\n{title}\n  {'':>8}  {cells}  {'overall':>8}  {'s/doc':>6}")
    values = "  ".join(f"{accuracy[f]:>12.0%}" for f in FIELDS)
    print(f"  {'accuracy':>8}  {values}  {overall:>8.0%}  {seconds:>6.1f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--models", nargs="*", default=[], help="Ollama model tags, e.g. qwen2.5:3b")
    parser.add_argument("--data", type=Path, default=HERE / "invoices_data")
    parser.add_argument("--limit", type=int, help="only the first N invoices")
    parser.add_argument("--base-url", default=get_settings().ollama_base_url)
    args = parser.parse_args()

    truths = json.loads((args.data / "truth.json").read_text())[: args.limit]
    settings = get_settings()
    print(f"{len(truths)} invoices ({sum(t['scanned'] for t in truths)} scanned, need OCR)")

    texts, ocr_seconds = [], 0.0
    for truth in truths:
        text, used_ocr, seconds = read_text(args.data / truth["file"])
        texts.append(text)
        ocr_seconds += seconds if used_ocr else 0
    print(f"text/OCR: {sum(t['scanned'] for t in truths)} scans took {ocr_seconds:.1f}s total")

    rows = [{"regex": extract_invoice(text)} for text in texts]
    report = {"invoices": len(truths), "results": {}}
    regex_accuracy = score(rows, truths, "regex")
    print_table("regex baseline (no LLM)", regex_accuracy, 0.0)
    report["results"]["regex"] = {"accuracy": regex_accuracy}

    if args.models:
        provider = OllamaProvider(args.base_url, timeout=settings.ollama_timeout_seconds)
        try:
            available = set(provider.list_models())
        except LLMError as exc:
            raise SystemExit(f"{exc}. Start Ollama (`ollama serve`) or pass --base-url.") from exc
        for model in args.models:
            if model not in available:
                print(f"\n{model}: not pulled (run `ollama pull {model}`), skipping")
                continue
            llm_seconds, parse_failures = 0.0, 0
            for i, text in enumerate(texts, 1):
                try:
                    started = time.perf_counter()
                    data = llm_extract(provider, model, INVOICE, text)
                    seconds = time.perf_counter() - started
                except LLMError as exc:
                    print(f"  {model} invoice {i}: {exc}")
                    data, seconds = None, 0.0
                llm_seconds += seconds
                parse_failures += data is None
                rows[i - 1]["llm"] = data
                rows[i - 1]["hybrid"] = merge(INVOICE, rows[i - 1]["regex"], data)
                print(f"  {model}: {i}/{len(texts)}", end="\r", flush=True)
            per_doc = llm_seconds / len(texts)
            for strategy in ("llm", "hybrid"):
                accuracy = score(rows, truths, strategy)
                print_table(f"{model} - {strategy} (unparseable replies: {parse_failures})", accuracy, per_doc)
                report["results"][f"{model}:{strategy}"] = {
                    "accuracy": accuracy, "seconds_per_doc": per_doc, "unparseable": parse_failures}

    out = HERE / "results"
    out.mkdir(exist_ok=True)
    path = out / f"extraction_{datetime.now(UTC):%Y%m%d_%H%M%S}.json"
    path.write_text(json.dumps(report, indent=2))
    print(f"\nsaved {path}")


if __name__ == "__main__":
    main()
