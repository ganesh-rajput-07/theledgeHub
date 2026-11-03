"""Rule-based reading of Indian GST invoices: fast, free and exact when the layout is conventional.
Anything it cannot find is returned as None for the LLM (or the reviewer) to fill in."""

import re

from app.extraction.values import GSTIN_PATTERN, parse_amount

_GSTIN = re.compile(rf"\b{GSTIN_PATTERN}\b")
_AMOUNT = r"([\d,]+\.\d{2})"


def extract_invoice(text: str) -> dict:
    def first(pattern: str) -> str | None:
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1).strip() if match else None

    gstins = _GSTIN.findall(text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    buyer = next((lines[i + 1] for i, line in enumerate(lines[:-1]) if line.lower().startswith("bill to")), None)
    tax = [parse_amount(v) for v in re.findall(rf"(?:CGST|SGST|IGST)\s*:\s*{_AMOUNT}", text)]
    return {
        "vendor_name": lines[0] if lines else None,
        "vendor_gstin": gstins[0] if gstins else None,
        "buyer_name": buyer,
        "buyer_gstin": gstins[1] if len(gstins) > 1 else None,
        "invoice_number": first(r"(?:Invoice\s*No|Inv\.?\s*No\.?|Bill\s*#)\s*:\s*(\S+)"),
        "invoice_date": first(r"(?:Invoice Date|Dated|Date)\s*:\s*([0-9A-Za-z/.\-]+)"),
        "subtotal": first(rf"Sub\s*Total\s*:\s*{_AMOUNT}"),
        "tax_total": round(sum(tax), 2) if tax else None,
        "total": first(rf"Grand\s*Total\s*:\s*(?:Rs\.?\s*)?{_AMOUNT}"),
    }
