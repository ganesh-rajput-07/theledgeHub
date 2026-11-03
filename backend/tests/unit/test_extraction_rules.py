import random

import pytest

from app.extraction.schema import INVOICE, validate
from app.extraction.values import gstin_is_valid, parse_amount, parse_date
from evaluation.invoices import gstin

GOOD = {
    "vendor_name": "Shree Ganesh Textiles", "vendor_gstin": "27AAPFU0939F1ZV", "buyer_name": "Tapi Fabrics",
    "buyer_gstin": None, "invoice_number": "INV/26-27/0042", "invoice_date": "20-Aug-2026",
    "subtotal": "1,00,000.00", "tax_total": "18,000.00", "total": "1,18,000.00",
}


def codes(values):
    return {(i.code, i.field) for i in validate(INVOICE, values)}


def test_clean_invoice_has_no_issues():
    assert validate(INVOICE, GOOD) == []


def test_generated_gstins_pass_checksum():
    rng = random.Random(1)
    assert all(gstin_is_valid(gstin("24", rng)) for _ in range(50))


def test_gstin_ocr_slip_is_caught():
    assert not gstin_is_valid("27AAPFU0939F1ZW")  # wrong check digit
    assert not gstin_is_valid("27AAPFU0939F1Z")  # too short
    assert not gstin_is_valid(None)


@pytest.mark.parametrize("text, expected", [("1,38,095.05", 138095.05), ("Rs. 12.50", 12.5), (7, 7.0), ("n/a", None)])
def test_parse_amount(text, expected):
    assert parse_amount(text) == expected


@pytest.mark.parametrize("text", ["2026-08-20", "20/08/2026", "20-Aug-2026", "20.08.26"])
def test_parse_date_formats(text):
    assert parse_date(text) == "2026-08-20"


def test_missing_and_invalid_fields():
    bad = {**GOOD, "invoice_number": "", "invoice_date": "sometime", "vendor_gstin": "27AAPFU0939F1ZW"}
    assert codes(bad) == {("missing", "invoice_number"), ("invalid_date", "invoice_date"),
                          ("invalid_gstin", "vendor_gstin")}


def test_optional_field_may_be_absent():
    assert "buyer_gstin" not in {i.field for i in validate(INVOICE, GOOD)}


def test_total_mismatch_is_flagged():
    assert ("total_mismatch", "total") in codes({**GOOD, "total": "1,19,000.00"})


def test_paisa_rounding_is_tolerated():
    assert validate(INVOICE, {**GOOD, "total": "1,18,000.01"}) == []


def test_implausible_tax_is_a_warning():
    issues = validate(INVOICE, {**GOOD, "tax_total": "30,000.00", "total": "1,30,000.00"})
    assert [(i.code, i.severity) for i in issues] == [("tax_implausible", "warning")]


def test_rules_skip_fields_that_are_already_broken():
    assert codes({**GOOD, "subtotal": "abc"}) == {("invalid_amount", "subtotal")}


def test_duplicate_key_ignores_case_and_punctuation():
    other = {**GOOD, "vendor_gstin": "27aapfu0939f1zv", "invoice_number": "inv-26-27-0042"}
    assert INVOICE.duplicate_key(GOOD) == INVOICE.duplicate_key(other)
    assert INVOICE.duplicate_key({**GOOD, "invoice_number": None}) is None
