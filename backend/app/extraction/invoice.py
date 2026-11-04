"""Rule-based reading of Indian GST invoices: fast, free and exact when the layout is conventional.
Anything it cannot find is returned as None for the LLM (or the reviewer) to fill in."""

import re

from app.extraction.values import GSTIN_PATTERN, parse_amount

_GSTIN = re.compile(rf"\b{GSTIN_PATTERN}\b")
_AMOUNT = r"([\d,]+\.\d{2})"
_CURRENCY = r"(?:Rs\.?|INR|₹)?\s*"
_SEP = r"\s*[:\-]?\s*"
_TAX_LABEL = re.compile(r"\b(CGST|SGST|UTGST|IGST)\b", re.IGNORECASE)

# Lines made only of these words are document titles ("TAX INVOICE (ORIGINAL FOR RECIPIENT)"), not the vendor.
_HEADING_WORDS = {
    "tax", "invoice", "gst", "bill", "of", "supply", "retail", "cash", "credit", "debit", "memo", "note",
    "proforma", "commercial", "original", "duplicate", "triplicate", "for", "recipient", "transporter",
    "supplier", "buyer", "copy", "export", "e", "invoice-cum-challan", "challan", "cum",
}  # fmt: skip

_SUBTOTAL = (
    rf"Sub\s*Total{_SEP}{_CURRENCY}{_AMOUNT}",
    rf"(?:Total\s*)?Taxable\s*(?:Value|Amount){_SEP}{_CURRENCY}{_AMOUNT}",
)
_TOTAL = (
    rf"Grand\s*Total{_SEP}{_CURRENCY}{_AMOUNT}",
    rf"(?:Invoice\s*Total|Total\s*Invoice\s*(?:Value|Amount)|Amount\s*Payable|Net\s*Payable|Total\s*Amount){_SEP}{_CURRENCY}{_AMOUNT}",
)


def _is_heading(line: str) -> bool:
    words = re.sub(r"[^a-z\- ]", " ", line.lower()).split()
    return bool(words) and all(word in _HEADING_WORDS for word in words)


def _vendor_name(lines: list[str]) -> str | None:
    """The first line near the top that looks like a name: not a title, label, GSTIN or date."""
    for line in lines[:8]:
        if (
            _is_heading(line)
            or ":" in line
            or _GSTIN.search(line)
            or re.search(r"\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2}", line)
        ):
            continue
        return line
    return None


def _tax_total(lines: list[str]) -> float | None:
    """Per tax type, the last amount after its label on the last line that has one (totals sit at the bottom).
    Handles 'CGST: 900.00', 'CGST @ 9%: 900.00', 'CGST 9% on 10,000.00 = 900.00' and 'CGST ... SGST ...' rows."""
    taxes: dict[str, float] = {}
    for line in lines:
        parts = _TAX_LABEL.split(line)  # [before, label, after, label, after, ...]
        for label, segment in zip(parts[1::2], parts[2::2], strict=True):
            amounts = re.findall(_AMOUNT, segment)
            if amounts:
                taxes[label.upper()] = parse_amount(amounts[-1])
    return round(sum(taxes.values()), 2) if taxes else None


def _first(text: str, patterns: tuple[str, ...] | str) -> str | None:
    for pattern in (patterns,) if isinstance(patterns, str) else patterns:
        if match := re.search(pattern, text, re.IGNORECASE):
            return match.group(1).strip()
    return None


def extract_invoice(text: str) -> dict:
    gstins = _GSTIN.findall(text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    buyer = next((lines[i + 1] for i, line in enumerate(lines[:-1]) if line.lower().startswith("bill to")), None)
    return {
        "vendor_name": _vendor_name(lines),
        "vendor_gstin": gstins[0] if gstins else None,
        "buyer_name": buyer,
        "buyer_gstin": gstins[1] if len(gstins) > 1 else None,
        "invoice_number": _first(text, r"(?:Invoice\s*No|Inv\.?\s*No\.?|Bill\s*#)\s*:\s*(\S+)"),
        "invoice_date": _first(text, r"(?:Invoice Date|Dated|Date)\s*:\s*([0-9A-Za-z/.\-]+)"),
        "subtotal": _first(text, _SUBTOTAL),
        "tax_total": _tax_total(lines),
        "total": _first(text, _TOTAL),
    }
