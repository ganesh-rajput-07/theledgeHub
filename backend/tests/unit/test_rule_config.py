from datetime import date

import pytest

from app.extraction.rules import CustomRule, RuleConfig, RuleConfigError, check_config, defaults, resolve
from app.extraction.schema import INVOICE, validate

TODAY = date(2026, 9, 1)
GOOD = {
    "vendor_name": "Shree Ganesh Textiles",
    "vendor_gstin": "27AAPFU0939F1ZV",
    "buyer_name": "Tapi Fabrics",
    "buyer_gstin": "27AAPFU0939F1ZV",
    "invoice_number": "INV/26-27/0042",
    "invoice_date": "20-Aug-2026",
    "subtotal": "1,00,000.00",
    "tax_total": "18,000.00",
    "total": "1,18,000.00",
}


def run(config: RuleConfig, **values) -> set[tuple[str, str]]:
    return {(i.code, i.severity) for i in validate(INVOICE, {**GOOD, **values}, check_config(INVOICE, config), TODAY)}


def configured(**builtin) -> RuleConfig:
    config = defaults("invoice")
    for key, changes in builtin.items():
        setting = config.builtin[key]
        config.builtin[key] = setting.model_copy(
            update={**changes, "params": {**setting.params, **changes.get("params", {})}}
        )
    return config


def test_defaults_match_the_previous_behaviour():
    assert run(defaults("invoice")) == set()
    assert ("total_mismatch", "error") in run(defaults("invoice"), total="1,19,000.00")


def test_disabling_a_rule_silences_it():
    config = configured(total_matches={"enabled": False})
    assert run(config, total="1,19,000.00") == set()


def test_severity_can_be_changed():
    config = configured(total_matches={"severity": "warning"})
    assert ("total_mismatch", "warning") in run(config, total="1,19,000.00")


def test_round_off_allowance_is_configurable():
    strict = configured(total_matches={"params": {"max_round_off": 0}})
    # 99,999.60 + 18,000.00 = 1,17,999.60, rounded to 1,18,000.00 on the invoice
    assert ("total_mismatch", "error") in run(strict, subtotal="99,999.60")
    assert ("round_off", "warning") in run(defaults("invoice"), subtotal="99,999.60")


def test_tax_limit_is_configurable():
    assert ("tax_implausible", "warning") in run(configured(tax_plausible={"params": {"max_tax_percent": 12}}))
    assert run(defaults("invoice")) == set()  # 18% is fine under the default 28%


def test_gstin_check_can_be_relaxed_or_switched_off():
    bad = {"vendor_gstin": "27AAPFU0939F1ZX"}
    assert ("invalid_gstin", "error") in run(defaults("invoice"), **bad)
    assert ("invalid_gstin", "warning") in run(configured(gstin_checksum={"severity": "warning"}), **bad)
    assert not any(code == "invalid_gstin" for code, _ in run(configured(gstin_checksum={"enabled": False}), **bad))


def test_date_rules():
    future = configured(date_not_future={"enabled": True})
    assert ("date_in_future", "error") in run(future, invoice_date="2026-12-25")
    assert run(future) == set()
    recent = configured(date_recent={"enabled": True, "params": {"max_age_days": 10}})
    assert ("date_too_old", "warning") in run(recent)  # 20 Aug is 12 days before 1 Sep


def test_billed_to_this_client():
    rule = configured(buyer_is_client={"enabled": True, "params": {"client_gstin": "27AAPFU0939F1ZV"}})
    assert run(rule) == set()
    assert ("wrong_buyer", "error") in run(rule, buyer_gstin="24AAACS1234A1Z1")
    assert ("wrong_buyer", "error") in run(rule, buyer_gstin=None)


def test_large_amount_threshold():
    rule = configured(large_amount={"enabled": True, "params": {"amount": 1_00_000}})
    assert ("large_amount", "warning") in run(rule)


@pytest.mark.parametrize(
    ("field", "operator", "value", "values", "flagged"),
    [
        ("total", "greater_than", "50000", {}, True),
        ("total", "less_than", "50000", {}, False),
        ("total", "equals", "1,18,000", {}, True),
        ("invoice_date", "before", "2026-09-01", {}, True),
        ("invoice_date", "after", "01/09/2026", {}, False),
        ("vendor_name", "contains", "ganesh", {}, True),
        ("vendor_name", "equals", "shree  ganesh textiles.", {}, True),
        ("vendor_name", "not_contains", "ganesh", {}, False),
        ("buyer_gstin", "is_empty", None, {"buyer_gstin": None}, True),
        ("invoice_number", "is_not_empty", None, {}, True),
        ("total", "greater_than", "50000", {"total": None}, False),  # missing values never match a comparison
    ],
)
def test_custom_rules(field, operator, value, values, flagged):
    config = defaults("invoice")
    config.custom = [CustomRule(field=field, operator=operator, value=value, severity="error", message="Check this")]
    codes = run(config, **values)
    assert any(code.startswith("custom:") for code, _ in codes) is flagged


def test_disabled_custom_rule_is_ignored():
    config = defaults("invoice")
    config.custom = [CustomRule(field="total", operator="greater_than", value="1", message="x", enabled=False)]
    assert run(config) == set()


@pytest.mark.parametrize(
    ("rule", "error"),
    [
        ({"field": "nope", "operator": "equals", "value": "1"}, "Unknown field"),
        ({"field": "vendor_name", "operator": "greater_than", "value": "1"}, "can't be used"),
        ({"field": "total", "operator": "greater_than", "value": "lots"}, "not a number"),
        ({"field": "invoice_date", "operator": "before", "value": "soon"}, "not a date"),
        ({"field": "total", "operator": "greater_than", "value": " "}, "needs a value"),
    ],
)
def test_invalid_custom_rules_are_rejected(rule, error):
    config = defaults("invoice")
    config.custom = [CustomRule(**rule, message="m")]
    with pytest.raises(RuleConfigError, match=error):
        check_config(INVOICE, config)


def test_client_gstin_must_be_valid_and_present_when_enabled():
    with pytest.raises(RuleConfigError, match="needs a value"):
        check_config(INVOICE, configured(buyer_is_client={"enabled": True}))
    with pytest.raises(RuleConfigError, match="not a valid GSTIN"):
        check_config(INVOICE, configured(buyer_is_client={"enabled": True, "params": {"client_gstin": "27ABC"}}))


def test_saved_config_survives_catalog_changes():
    saved = {
        "builtin": {
            "total_matches": {"enabled": False, "severity": "error", "params": {}},
            "retired": {"enabled": True, "severity": "error"},
        },
        "custom": [],
    }
    config = resolve("invoice", saved)
    assert config.builtin["total_matches"].enabled is False
    assert config.builtin["total_matches"].params["max_round_off"] == 1.0  # new params get their default
    assert "retired" not in config.builtin and "large_amount" in config.builtin
