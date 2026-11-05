from datetime import date

import pytest

from app.money import add_months, parse_rupees, period_end, rupees


@pytest.mark.parametrize(
    ("paise", "text"),
    [(0, "₹0"), (99900, "₹999"), (149950, "₹1,499.50"), (12345678900, "₹12,34,56,789"), (-5000, "-₹50")],
)
def test_indian_grouping(paise, text):
    assert rupees(paise) == text


def test_parse_rupees():
    assert parse_rupees("₹ 1,499") == 149900
    assert parse_rupees("1499.505") == 149951
    for bad in ("", "abc", "-1", "NaN", "Infinity", "100000001"):
        with pytest.raises(ValueError):
            parse_rupees(bad)


def test_month_arithmetic_clamps_to_month_end():
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2026, 11, 5), 2) == date(2027, 1, 5)
    assert add_months(date(2026, 3, 15), -3) == date(2025, 12, 15)
    assert period_end(date(2026, 11, 5), 1) == date(2026, 12, 4)
    assert period_end(date(2026, 1, 1), 12) == date(2026, 12, 31)
