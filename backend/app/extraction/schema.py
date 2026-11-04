"""Document types as data: a schema lists the fields to extract and the rules the values must satisfy.

Adding a document type (purchase order, delivery note, claim form...) means adding a DocumentSchema, not
new pipeline code. Validation reports problems for a human reviewer; it never silently corrects values.
"""

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import date
from typing import TYPE_CHECKING, Literal

from app.extraction.invoice import extract_invoice
from app.extraction.values import gstin_is_valid, normalize, parse_amount, parse_date

if TYPE_CHECKING:
    from app.extraction.rules import RuleConfig

FieldType = Literal["text", "date", "amount", "gstin"]


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    type: FieldType = "text"
    required: bool = True
    hint: str = ""  # extra wording for the LLM prompt


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    field: str | None = None
    severity: Literal["error", "warning"] = "error"


@dataclass(frozen=True)
class DocumentSchema:
    key: str
    name: str
    fields: tuple[Field, ...]
    # Values that identify "the same document": equal key means probable duplicate.
    duplicate_key_fields: tuple[str, ...] = field(default=())
    # Optional rule-based reader tried before the LLM: text -> {field key: raw value or None}.
    heuristic: Callable[[str], dict] | None = None

    def duplicate_key(self, values: dict) -> str | None:
        parts = [normalize(values.get(key) or "") for key in self.duplicate_key_fields]
        return "|".join(parts) if self.duplicate_key_fields and all(parts) else None


def clean_values(schema: DocumentSchema, raw: dict) -> dict:
    """One canonical form per type (ISO dates, numeric amounts, upper-case GSTIN); unreadable values are kept
    as typed so the reviewer sees them. Keys outside the schema are dropped."""
    out: dict = {}
    for spec in schema.fields:
        value = raw.get(spec.key)
        if value is None or str(value).strip() == "":
            out[spec.key] = None
        elif spec.type == "amount":
            out[spec.key] = parse_amount(value) if parse_amount(value) is not None else str(value).strip()
        elif spec.type == "date":
            out[spec.key] = parse_date(value) or str(value).strip()
        elif spec.type == "gstin":
            out[spec.key] = str(value).strip().upper()
        else:
            out[spec.key] = str(value).strip()
    return out


def _check_field(spec: Field, value) -> Issue | None:
    if value in (None, ""):
        if spec.required:
            return Issue("missing", f"{spec.label} not found", spec.key)
        return None
    if spec.type == "amount" and parse_amount(value) is None:
        return Issue("invalid_amount", f"{spec.label} is not a number: {value!r}", spec.key)
    if spec.type == "date" and parse_date(value) is None:
        return Issue("invalid_date", f"{spec.label} is not a readable date: {value!r}", spec.key)
    if spec.type == "gstin" and not gstin_is_valid(value):
        return Issue("invalid_gstin", f"{spec.label} fails the GSTIN format/check digit: {value!r}", spec.key)
    return None


def validate(
    schema: DocumentSchema, values: dict, config: "RuleConfig | None" = None, today: date | None = None
) -> list[Issue]:
    """Field checks first, then the enabled predefined rules and custom rules of `config` (the workspace's
    rules; defaults when None). Rules skip fields whose value is already broken."""
    from app.extraction.rules import CATALOG, custom_problems, resolve

    config = config or resolve(schema.key, None)
    today = today or date.today()
    gstin_setting = config.builtin.get("gstin_checksum")
    issues = []
    for spec in schema.fields:
        issue = _check_field(spec, values.get(spec.key))
        if issue is not None and issue.code == "invalid_gstin" and gstin_setting is not None:
            if not gstin_setting.enabled:
                continue
            issue = replace(issue, severity=gstin_setting.severity)
        if issue is not None:
            issues.append(issue)

    broken = {i.field for i in issues}
    usable = {k: v for k, v in values.items() if k not in broken}
    for rule in CATALOG.get(schema.key, ()):
        setting = config.builtin.get(rule.key)
        if rule.check is None or setting is None or not setting.enabled:
            continue
        issues.extend(
            Issue(p.code, p.message, p.field, p.severity or setting.severity)
            for p in rule.check(usable, setting.params, today)
        )
    issues.extend(Issue(p.code, p.message, p.field, p.severity) for p in custom_problems(schema, config, usable))
    return issues


INVOICE = DocumentSchema(
    key="invoice",
    name="Purchase invoice",
    fields=(
        Field("vendor_name", "Vendor name", hint="the company issuing the invoice"),
        Field("vendor_gstin", "Vendor GSTIN", "gstin"),
        Field("buyer_name", "Buyer name", hint="the company being billed"),
        Field("buyer_gstin", "Buyer GSTIN", "gstin", required=False),
        Field("invoice_number", "Invoice number"),
        Field("invoice_date", "Invoice date", "date"),
        Field("subtotal", "Subtotal", "amount"),
        Field("tax_total", "Tax total", "amount", hint="all GST combined (CGST+SGST or IGST)"),
        Field("total", "Total", "amount", hint="the grand total payable"),
    ),
    duplicate_key_fields=("vendor_gstin", "invoice_number"),
    heuristic=extract_invoice,
)

SCHEMAS: dict[str, DocumentSchema] = {INVOICE.key: INVOICE}
