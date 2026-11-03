"""Parsing and checking of extracted values. Deterministic code, never an LLM judgement."""

import re
from datetime import UTC, datetime

GSTIN_PATTERN = r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]"
_GSTIN = re.compile(GSTIN_PATTERN)
_GSTIN_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%b-%Y", "%d.%m.%y", "%d-%m-%Y", "%d/%m/%y")


def parse_amount(value) -> float | None:
    """'1,38,095.05', 'Rs. 12.50' or 12.5 -> float; None when there is no number."""
    match = re.search(r"-?\d[\d,]*(?:\.\d+)?", str(value))
    return round(float(match.group().replace(",", "")), 2) if match else None


def parse_date(value) -> str | None:
    """Any common Indian date format -> ISO 'YYYY-MM-DD'; None when unreadable."""
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(str(value).strip(), fmt).replace(tzinfo=UTC).date().isoformat()
        except ValueError:
            continue
    return None


def gstin_is_valid(value) -> bool:
    """Format plus the check character, so an OCR slip (O for 0, S for 5) is caught."""
    text = str(value).strip().upper()
    if not _GSTIN.fullmatch(text):
        return False
    total = 0
    for i, char in enumerate(text[:14]):
        product = _GSTIN_CHARS.index(char) * (1 if i % 2 == 0 else 2)
        total += product // 36 + product % 36
    return text[14] == _GSTIN_CHARS[(36 - total % 36) % 36]


def normalize(value) -> str:
    """Case, spacing and punctuation-insensitive form, for duplicate keys and name comparison."""
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())
