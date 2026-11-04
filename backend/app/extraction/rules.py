"""Configurable validation: predefined rules a workspace can switch on/off and tune, plus custom rules built
from dropdowns ("if <field> <condition> <value>, flag <severity> <message>").

Custom rules are data, never code: they are checked by the fixed operators below, so nothing a user saves can
execute on the server. The defaults reproduce the built-in behaviour exactly, so an unconfigured workspace
validates the same way as before rules were configurable.
"""

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.extraction.values import gstin_is_valid, normalize, parse_amount, parse_date

Severity = Literal["error", "warning"]
AMOUNT_TOLERANCE = 0.02  # tax shown as two rounded halves (CGST + SGST) can differ from the total by a paisa


# ---------------------------------------------------------------- saved configuration (validated input)


class BuiltinSetting(BaseModel):
    enabled: bool
    severity: Severity
    params: dict[str, float | str | None] = Field(default_factory=dict)


Operator = Literal[
    "is_empty", "is_not_empty", "equals", "not_equals", "contains", "not_contains",
    "greater_than", "less_than", "before", "after",
]  # fmt: skip

OPERATORS_BY_TYPE: dict[str, list[str]] = {
    "text": ["is_empty", "is_not_empty", "equals", "not_equals", "contains", "not_contains"],
    "gstin": ["is_empty", "is_not_empty", "equals", "not_equals", "contains", "not_contains"],
    "amount": ["is_empty", "is_not_empty", "equals", "not_equals", "greater_than", "less_than"],
    "date": ["is_empty", "is_not_empty", "equals", "not_equals", "before", "after"],
}
_NO_VALUE = {"is_empty", "is_not_empty"}


class CustomRule(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12], pattern=r"^[a-zA-Z0-9_-]{1,40}$")
    enabled: bool = True
    field: str = Field(max_length=60)
    operator: Operator
    value: str | None = Field(default=None, max_length=200)
    severity: Severity = "warning"
    message: str = Field(min_length=1, max_length=200)

    @field_validator("message")
    @classmethod
    def _strip(cls, message: str) -> str:
        if not message.strip():
            raise ValueError("message must not be blank")
        return message.strip()


class RuleConfig(BaseModel):
    builtin: dict[str, BuiltinSetting] = Field(default_factory=dict)
    custom: list[CustomRule] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def _unique_ids(self):
        ids = [rule.id for rule in self.custom]
        if len(ids) != len(set(ids)):
            raise ValueError("custom rule ids must be unique")
        return self


# ---------------------------------------------------------------- predefined rules


@dataclass(frozen=True)
class Param:
    key: str
    label: str
    type: Literal["number", "gstin", "date", "text"]
    default: float | str | None = None
    required: bool = False


@dataclass(frozen=True)
class Problem:
    code: str
    message: str
    field: str | None
    severity: Severity | None = None  # None = use the rule's configured severity


@dataclass(frozen=True)
class BuiltinRule:
    key: str
    label: str
    description: str
    enabled: bool
    severity: Severity
    params: tuple[Param, ...] = ()
    # (values, params, today) -> problems. None for rules evaluated elsewhere (field formats, duplicates).
    check: Callable[[dict, dict, date], list[Problem]] | None = None


def _total_matches(values: dict, params: dict, _today: date) -> list[Problem]:
    subtotal, tax, total = (parse_amount(values.get(k)) for k in ("subtotal", "tax_total", "total"))
    if None in (subtotal, tax, total):
        return []
    difference = round(total - (subtotal + tax), 2)
    if abs(difference) <= AMOUNT_TOLERANCE:
        return []
    round_off = float(params.get("max_round_off") or 0)
    if abs(difference) <= round_off and total == round(total):
        # Rounded to the rupee: fine to approve, but say so, because the round-off is posted to its own ledger.
        return [
            Problem(
                "round_off",
                f"Total includes a round-off of {difference:+.2f} (subtotal + tax = {subtotal + tax:.2f})",
                "total",
                "warning",
            )
        ]
    return [
        Problem(
            "total_mismatch",
            f"Subtotal {subtotal:.2f} + tax {tax:.2f} is {subtotal + tax:.2f}, but the total says {total:.2f}",
            "total",
        )
    ]


def _tax_plausible(values: dict, params: dict, _today: date) -> list[Problem]:
    subtotal, tax = parse_amount(values.get("subtotal")), parse_amount(values.get("tax_total"))
    if not subtotal or tax is None:
        return []
    limit = float(params.get("max_tax_percent") or 28) / 100
    if tax < 0 or tax > subtotal * limit + AMOUNT_TOLERANCE:
        return [
            Problem(
                "tax_implausible",
                f"Tax {tax:.2f} is {tax / subtotal:.0%} of the subtotal (allowed up to {limit:.0%})",
                "tax_total",
            )
        ]
    return []


def _date_not_future(values: dict, _params: dict, today: date) -> list[Problem]:
    invoice_date = parse_date(values.get("invoice_date") or "")
    if invoice_date and date.fromisoformat(invoice_date) > today:
        return [Problem("date_in_future", f"Invoice date {invoice_date} is in the future", "invoice_date")]
    return []


def _date_recent(values: dict, params: dict, today: date) -> list[Problem]:
    invoice_date = parse_date(values.get("invoice_date") or "")
    days = int(float(params.get("max_age_days") or 0))
    if invoice_date and days and date.fromisoformat(invoice_date) < today - timedelta(days=days):
        return [Problem("date_too_old", f"Invoice date {invoice_date} is more than {days} days old", "invoice_date")]
    return []


def _buyer_is_client(values: dict, params: dict, _today: date) -> list[Problem]:
    expected = str(params.get("client_gstin") or "").strip().upper()
    actual = str(values.get("buyer_gstin") or "").strip().upper()
    if expected and actual != expected:
        shown = actual or "missing"
        return [
            Problem("wrong_buyer", f"Billed to GSTIN {shown}, but this client's GSTIN is {expected}", "buyer_gstin")
        ]
    return []


def _large_amount(values: dict, params: dict, _today: date) -> list[Problem]:
    total, limit = parse_amount(values.get("total")), float(params.get("amount") or 0)
    if total is not None and limit and total > limit:
        return [Problem("large_amount", f"Total {total:,.2f} is above {limit:,.2f}", "total")]
    return []


INVOICE_RULES: tuple[BuiltinRule, ...] = (
    BuiltinRule(
        "gstin_checksum", "GSTIN is valid", "GSTINs must have the right format and check digit (catches OCR slips).",
        True, "error",
    ),
    BuiltinRule(
        "total_matches", "Total = subtotal + tax", "The grand total must equal subtotal plus tax.", True, "error",
        (Param("max_round_off", "Round-off allowed (₹)", "number", 1.0),), _total_matches,
    ),
    BuiltinRule(
        "tax_plausible", "Tax rate is plausible", "Tax must not exceed this share of the subtotal.", True, "warning",
        (Param("max_tax_percent", "Maximum tax %", "number", 28.0),), _tax_plausible,
    ),
    BuiltinRule(
        "duplicate", "Duplicate invoice", "Same vendor GSTIN and invoice number as another document.", True, "error",
    ),
    BuiltinRule(
        "date_not_future", "Invoice date not in the future", "Catches misread or mistyped dates.", False, "error",
        (), _date_not_future,
    ),
    BuiltinRule(
        "date_recent", "Invoice date within a period", "Flags invoices older than this many days.", False, "warning",
        (Param("max_age_days", "Maximum age (days)", "number", 365.0),), _date_recent,
    ),
    BuiltinRule(
        "buyer_is_client", "Billed to this client", "The buyer GSTIN must be this workspace's client GSTIN.",
        False, "error", (Param("client_gstin", "Client GSTIN", "gstin", None, required=True),), _buyer_is_client,
    ),
    BuiltinRule(
        "large_amount", "Large amount", "Flags invoices whose total is above this amount.", False, "warning",
        (Param("amount", "Amount above (₹)", "number", 200000.0),), _large_amount,
    ),
)  # fmt: skip

CATALOG: dict[str, tuple[BuiltinRule, ...]] = {"invoice": INVOICE_RULES}


def defaults(schema_key: str) -> RuleConfig:
    return RuleConfig(
        builtin={
            rule.key: BuiltinSetting(
                enabled=rule.enabled, severity=rule.severity, params={p.key: p.default for p in rule.params}
            )
            for rule in CATALOG.get(schema_key, ())
        }
    )


def resolve(schema_key: str, saved: dict | None) -> RuleConfig:
    """Saved settings over the defaults; unknown keys are ignored, new catalog rules get their defaults."""
    config = defaults(schema_key)
    if not saved:
        return config
    stored = RuleConfig.model_validate(saved)
    for key, setting in stored.builtin.items():
        if key in config.builtin:
            merged = {**config.builtin[key].params, **setting.params}
            config.builtin[key] = BuiltinSetting(enabled=setting.enabled, severity=setting.severity, params=merged)
    config.custom = stored.custom
    return config


# ---------------------------------------------------------------- checking what users save


class RuleConfigError(ValueError):
    pass


def check_config(schema, config: RuleConfig) -> RuleConfig:
    """Reject anything the engine couldn't evaluate, with a message a person can act on."""
    catalog = {rule.key: rule for rule in CATALOG.get(schema.key, ())}
    fields = {spec.key: spec for spec in schema.fields}
    for key, setting in config.builtin.items():
        rule = catalog.get(key)
        if rule is None:
            raise RuleConfigError(f"Unknown predefined rule '{key}'")
        for param in rule.params:
            value = setting.params.get(param.key)
            if value in (None, ""):
                if setting.enabled and param.required:
                    raise RuleConfigError(f"'{rule.label}' needs a value for {param.label}")
                continue
            if param.type == "number" and (parse_amount(value) is None or parse_amount(value) < 0):
                raise RuleConfigError(f"{param.label} must be a positive number")
            if param.type == "gstin" and not gstin_is_valid(value):
                raise RuleConfigError(f"{param.label} is not a valid GSTIN: {value}")
            setting.params[param.key] = parse_amount(value) if param.type == "number" else str(value).strip().upper()
    for rule in config.custom:
        spec = fields.get(rule.field)
        if spec is None:
            raise RuleConfigError(f"Unknown field '{rule.field}'")
        if rule.operator not in OPERATORS_BY_TYPE[spec.type]:
            raise RuleConfigError(f"'{rule.operator}' can't be used with {spec.label} ({spec.type})")
        if rule.operator in _NO_VALUE:
            rule.value = None
            continue
        if not (rule.value or "").strip():
            raise RuleConfigError(f"The rule on {spec.label} needs a value")
        if spec.type == "amount" and parse_amount(rule.value) is None:
            raise RuleConfigError(f"'{rule.value}' is not a number")
        if spec.type == "date":
            if (parsed := parse_date(rule.value)) is None:
                raise RuleConfigError(f"'{rule.value}' is not a date (use YYYY-MM-DD)")
            rule.value = parsed
        rule.value = rule.value.strip()
    return config


# ---------------------------------------------------------------- custom rules


def _custom_matches(rule: CustomRule, field_type: str, value) -> bool:
    """True when the condition holds, i.e. the document should be flagged."""
    empty = value in (None, "")
    if rule.operator == "is_empty":
        return empty
    if rule.operator == "is_not_empty":
        return not empty
    if empty:
        return False  # a missing value is reported by the required-field check; conditions don't apply
    if field_type == "amount":
        actual, wanted = parse_amount(value), parse_amount(rule.value)
        if actual is None or wanted is None:
            return False
        return {
            "equals": abs(actual - wanted) <= AMOUNT_TOLERANCE,
            "not_equals": abs(actual - wanted) > AMOUNT_TOLERANCE,
            "greater_than": actual > wanted,
            "less_than": actual < wanted,
        }[rule.operator]
    if field_type == "date":
        actual = parse_date(value)
        if actual is None:
            return False
        return {
            "equals": actual == rule.value,
            "not_equals": actual != rule.value,
            "before": actual < rule.value,
            "after": actual > rule.value,
        }[rule.operator]
    actual, wanted = re.sub(r"\s+", " ", str(value)).strip().casefold(), str(rule.value).strip().casefold()
    return {
        "equals": normalize(actual) == normalize(wanted),
        "not_equals": normalize(actual) != normalize(wanted),
        "contains": wanted in actual,
        "not_contains": wanted not in actual,
    }[rule.operator]


def custom_problems(schema, config: RuleConfig, values: dict) -> list[Problem]:
    types = {spec.key: spec.type for spec in schema.fields}
    return [
        Problem(f"custom:{rule.id}", rule.message, rule.field, rule.severity)
        for rule in config.custom
        if rule.enabled and rule.field in types and _custom_matches(rule, types[rule.field], values.get(rule.field))
    ]
