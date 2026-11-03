"""Schema-driven extraction: rule-based reader first, an optional LLM for the rest, merged field by field."""

import json
import re

from app.extraction.schema import DocumentSchema, Field, clean_values
from app.extraction.values import gstin_is_valid, parse_amount, parse_date
from app.llm.base import ChatMessage, LLMProvider

MAX_TEXT_CHARS = 6000
_TYPE_HINTS = {
    "date": "as YYYY-MM-DD",
    "amount": "a plain number, no currency symbol or thousands separators",
    "gstin": "the 15-character GSTIN, copied exactly",
}


def build_prompt(schema: DocumentSchema) -> str:
    def describe(spec: Field) -> str:
        notes = ", ".join(n for n in (spec.hint, _TYPE_HINTS.get(spec.type, "")) if n)
        return f"- {spec.key}: {spec.label}" + (f" ({notes})" if notes else "")

    return (
        f"You extract data from a {schema.name.lower()}. Reply with one JSON object and nothing else, with "
        "exactly these keys:\n"
        + "\n".join(describe(spec) for spec in schema.fields)
        + "\nUse null for anything not present. Copy values exactly as written; never invent or guess any."
    )


def llm_extract(llm: LLMProvider, model: str, schema: DocumentSchema, text: str, max_tokens: int = 400) -> dict | None:
    """The model's JSON, or None when the reply isn't a JSON object (a small model's most common failure)."""
    reply = llm.generate(build_prompt(schema), [ChatMessage("user", text[:MAX_TEXT_CHARS])], model, max_tokens)
    match = re.search(r"\{.*\}", reply.text, re.DOTALL)
    try:
        data = json.loads(match.group(0)) if match else None
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _usable(spec: Field, value) -> bool:
    if value in (None, ""):
        return False
    if spec.type == "gstin":
        return gstin_is_valid(value)
    if spec.type == "amount":
        return parse_amount(value) is not None
    if spec.type == "date":
        return parse_date(value) is not None
    return True


def merge(schema: DocumentSchema, heuristic: dict, llm: dict | None) -> dict:
    """Typed fields: the rule-based value when it validates (exact), else the model's. Free-text fields
    (names): the model first, because layouts vary too much for rules. Values are never altered."""
    llm = llm or {}
    out = {}
    for spec in schema.fields:
        order = (llm, heuristic) if spec.type == "text" else (heuristic, llm)
        out[spec.key] = next((src[spec.key] for src in order if _usable(spec, src.get(spec.key))), None)
        if out[spec.key] is None:  # keep something for the reviewer to correct rather than a blank
            out[spec.key] = next((src[spec.key] for src in order if src.get(spec.key) not in (None, "")), None)
    return out


def extract_values(schema: DocumentSchema, text: str, llm: LLMProvider | None = None, model: str = "") -> dict:
    heuristic = schema.heuristic(text) if schema.heuristic else {}
    answer = llm_extract(llm, model, schema, text) if llm is not None else None
    return clean_values(schema, merge(schema, heuristic, answer))
