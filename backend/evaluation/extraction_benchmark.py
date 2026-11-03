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

import pymupdf

from app.core.config import get_settings
from app.ingestion.ocr import ocr_page
from app.llm.base import ChatMessage, LLMError
from app.llm.ollama_provider import OllamaProvider

HERE = Path(__file__).parent
FIELDS = ["vendor_name", "vendor_gstin", "buyer_name", "buyer_gstin", "invoice_number", "invoice_date",
          "subtotal", "tax_total", "total"]
AMOUNT_FIELDS = {"subtotal", "tax_total", "total"}
NAME_FIELDS = {"vendor_name", "buyer_name"}
AMOUNT_TOLERANCE = 0.02  # the generator splits tax into two rounded halves (CGST + SGST)
OCR_DPI = 150
MAX_TEXT_CHARS = 6000

SYSTEM_PROMPT = (
    "You extract data from invoices. Reply with one JSON object and nothing else, with exactly these keys: "
    + ", ".join(FIELDS)
    + ". vendor = the company issuing the invoice; buyer = the company billed. invoice_date as YYYY-MM-DD. "
    "Amounts as plain numbers without currency or commas; tax_total = all GST (CGST+SGST or IGST) combined; "
    "total = the grand total. Use null for anything not present. Copy values exactly; never invent any."
)

GSTIN = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b")
AMOUNT = r"([\d,]+\.\d{2})"
DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%b-%Y", "%d.%m.%y", "%d-%m-%Y", "%d/%m/%y")


# ---------------------------------------------------------------- text acquisition
def read_text(path: Path) -> tuple[str, bool, float]:
    """Embedded text if the PDF has any, otherwise OCR. Returns (text, used_ocr, seconds)."""
    start = time.perf_counter()
    with pymupdf.open(path) as doc:
        text = "\n".join(page.get_text() for page in doc).strip()
        used_ocr = not text
        if used_ocr:
            text = "\n".join(ocr_page(page, OCR_DPI) for page in doc)
    return text, used_ocr, time.perf_counter() - start


# ---------------------------------------------------------------- regex baseline
def regex_extract(text: str) -> dict:
    def first(pattern: str) -> str | None:
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1).strip() if match else None

    gstins = GSTIN.findall(text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    buyer = next((lines[i + 1] for i, line in enumerate(lines[:-1]) if line.lower().startswith("bill to")), None)
    tax = [to_amount(v) for v in re.findall(rf"(?:CGST|SGST|IGST)\s*:\s*{AMOUNT}", text)]
    return {
        "vendor_name": lines[0] if lines else None,
        "vendor_gstin": gstins[0] if gstins else None,
        "buyer_name": buyer,
        "buyer_gstin": gstins[1] if len(gstins) > 1 else None,
        "invoice_number": first(r"(?:Invoice No|Inv\. No\.|Bill #)\s*:\s*(\S+)"),
        "invoice_date": first(r"(?:Invoice Date|Dated|Date)\s*:\s*([0-9A-Za-z/.\-]+)"),
        "subtotal": first(rf"Sub Total\s*:\s*{AMOUNT}"),
        "tax_total": round(sum(tax), 2) if tax else None,
        "total": first(rf"Grand Total\s*:\s*(?:Rs\.?\s*)?{AMOUNT}"),
    }


# ---------------------------------------------------------------- LLM extraction
def llm_extract(provider: OllamaProvider, model: str, text: str) -> tuple[dict | None, float]:
    start = time.perf_counter()
    reply = provider.generate(SYSTEM_PROMPT, [ChatMessage("user", text[:MAX_TEXT_CHARS])], model, max_tokens=400)
    seconds = time.perf_counter() - start
    match = re.search(r"\{.*\}", reply.text, re.DOTALL)
    try:
        data = json.loads(match.group(0)) if match else None
    except json.JSONDecodeError:
        data = None
    return (data if isinstance(data, dict) else None), seconds


def valid(field: str, value) -> bool:
    if value in (None, ""):
        return False
    if field.endswith("gstin"):
        return bool(GSTIN.fullmatch(str(value)))
    if field in AMOUNT_FIELDS:
        return to_amount(value) is not None
    if field == "invoice_date":
        return to_date(value) is not None
    return True


def hybrid(regex: dict, llm: dict | None) -> dict:
    llm = llm or {}
    out = {}
    for field in FIELDS:
        preferred, fallback = (llm.get(field), regex.get(field)) if field in NAME_FIELDS else (
            regex.get(field), llm.get(field))
        out[field] = preferred if valid(field, preferred) or not valid(field, fallback) else fallback
    return out


# ---------------------------------------------------------------- scoring
def to_amount(value) -> float | None:
    try:
        return round(float(re.sub(r"[^\d.\-]", "", str(value))), 2)
    except ValueError:
        return None


def to_date(value) -> str | None:
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(str(value).strip(), fmt).replace(tzinfo=UTC).date().isoformat()
        except ValueError:
            continue
    return None


def matches(field: str, got, want) -> bool:
    if got in (None, ""):
        return False
    if field in AMOUNT_FIELDS:
        amount = to_amount(got)
        return amount is not None and abs(amount - float(want)) <= AMOUNT_TOLERANCE
    if field == "invoice_date":
        return to_date(got) == (want if isinstance(want, str) else date.isoformat(want))
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

    rows = [{"regex": regex_extract(text)} for text in texts]
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
                    data, seconds = llm_extract(provider, model, text)
                except LLMError as exc:
                    print(f"  {model} invoice {i}: {exc}")
                    data, seconds = None, 0.0
                llm_seconds += seconds
                parse_failures += data is None
                rows[i - 1]["llm"] = data
                rows[i - 1]["hybrid"] = hybrid(rows[i - 1]["regex"], data)
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
