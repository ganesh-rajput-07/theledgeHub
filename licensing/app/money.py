"""Rupee formatting/parsing and calendar helpers."""

import calendar
import re
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def today() -> date:
    """Business day in India (the server may run in UTC)."""
    return datetime.now(IST).date()


def rupees(paise: int | None, symbol: bool = True) -> str:
    """Indian digit grouping: 123456789 paise -> ₹12,34,567.89; whole rupees drop the .00."""
    if paise is None:
        return "-"
    sign = "-" if paise < 0 else ""
    whole, frac = divmod(abs(paise), 100)
    digits = str(whole)
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        head = ",".join(re.findall(r"\d{1,2}", head[::-1]))[::-1]
        digits = f"{head},{tail}"
    text = digits if frac == 0 else f"{digits}.{frac:02d}"
    return f"{sign}{'₹' if symbol else ''}{text}"


def parse_rupees(text: str) -> int:
    """'1,499' / '1499.50' / '₹ 1,499' -> paise. Raises ValueError on anything else or negatives."""
    cleaned = (text or "").replace("₹", "").replace(",", "").strip()
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        raise ValueError("Enter an amount in rupees, e.g. 1499 or 1,499.50") from None
    if not value.is_finite() or value < 0 or value > Decimal("10000000"):
        raise ValueError("Enter an amount between ₹0 and ₹1,00,00,000")
    return int((value * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def add_months(start: date, months: int) -> date:
    """Same day-of-month N months later, clamped to the month's last day (31 Jan + 1 month = 28/29 Feb)."""
    month_index = start.month - 1 + months
    year, month = start.year + month_index // 12, month_index % 12 + 1
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


def period_end(start: date, months: int) -> date:
    """Last day (inclusive) of a period of `months` starting on `start`: 5 Nov + 1 month -> 4 Dec."""
    return add_months(start, months) - timedelta(days=1)


def gst_on(paise: int, percent: Decimal) -> int:
    return int((Decimal(paise) * percent / 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
