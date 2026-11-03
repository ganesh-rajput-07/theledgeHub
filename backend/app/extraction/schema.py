"""Document types as data: a schema lists the fields to extract and the rules the values must satisfy.

Adding a document type (purchase order, delivery note, claim form...) means adding a DocumentSchema, not
new pipeline code. Validation reports problems for a human reviewer; it never silently corrects values.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from app.extraction.invoice import extract_invoice
from app.extraction.values import gstin_is_valid, normalize, parse_amount, parse_date

FieldType = Literal["text", "date", "amount", "gstin"]
AMOUNT_TOLERANCE = 0.02  # tax shown as two rounded halves (CGST + SGST) can differ from the total by a paisa


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


Rule = Callable[[dict], list[Issue]]


@dataclass(frozen=True)
class DocumentSchema:
    key: str
    name: str
    fields: tuple[Field, ...]
    rules: tuple[Rule, ...] = field(default=())
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


def validate(schema: DocumentSchema, values: dict) -> list[Issue]:
    """Field-level checks first, then the schema's cross-field rules (skipped for fields already broken)."""
    issues = [i for spec in schema.fields if (i := _check_field(spec, values.get(spec.key)))]
    broken = {i.field for i in issues}
    for rule in schema.rules:
        issues.extend(i for i in rule({k: v for k, v in values.items() if k not in broken}) if i)
    return issues


def _total_matches_parts(values: dict) -> list[Issue]:
    subtotal, tax, total = (parse_amount(values.get(k)) for k in ("subtotal", "tax_total", "total"))
    if None in (subtotal, tax, total):
        return []
    if abs(subtotal + tax - total) > AMOUNT_TOLERANCE:
        return [
            Issue(
                "total_mismatch",
                f"Subtotal {subtotal:.2f} + tax {tax:.2f} is {subtotal + tax:.2f}, but the total says {total:.2f}",
                "total",
            )
        ]
    return []


def _tax_is_plausible(values: dict) -> list[Issue]:
    """GST slabs are 0-28%; anything above is a misread number or a wrong tax line."""
    subtotal, tax = parse_amount(values.get("subtotal")), parse_amount(values.get("tax_total"))
    if not subtotal or tax is None:
        return []
    if tax < 0 or tax > subtotal * 0.28 + AMOUNT_TOLERANCE:
        return [
            Issue(
                "tax_implausible",
                f"Tax {tax:.2f} is {tax / subtotal:.0%} of the subtotal (Indian GST is at most 28%)",
                "tax_total",
                "warning",
            )
        ]
    return []


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
    rules=(_total_matches_parts, _tax_is_plausible),
    duplicate_key_fields=("vendor_gstin", "invoice_number"),
    heuristic=extract_invoice,
)

SCHEMAS: dict[str, DocumentSchema] = {INVOICE.key: INVOICE}
