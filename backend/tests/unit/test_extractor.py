from app.extraction.extractor import build_prompt, extract_values, llm_extract, merge
from app.extraction.schema import INVOICE
from app.llm.base import LLMResponse

INVOICE_TEXT = """Acme Traders
Bengaluru   GSTIN: 29AABCU9603R1ZM
Invoice No: A-17
Date: 05/09/2026
Bill To:
Orbit Retail LLP
Sub Total: 1,000.00
IGST: 180.00
Grand Total: Rs. 1,180.00
"""


class FakeLLM:
    name = "fake"

    def __init__(self, reply: str):
        self.reply, self.prompts = reply, []

    def generate(self, system, messages, model, max_tokens):
        self.prompts.append((system, messages[0].content))
        return LLMResponse(self.reply, model)


def test_prompt_lists_every_field_with_its_format():
    prompt = build_prompt(INVOICE)
    assert all(spec.key in prompt for spec in INVOICE.fields)
    assert "YYYY-MM-DD" in prompt and "GSTIN" in prompt


def test_rules_alone_read_a_conventional_invoice():
    values = extract_values(INVOICE, INVOICE_TEXT)
    assert values["invoice_number"] == "A-17"
    assert values["invoice_date"] == "2026-09-05"
    assert (values["subtotal"], values["tax_total"], values["total"]) == (1000.0, 180.0, 1180.0)
    assert values["buyer_name"] == "Orbit Retail LLP"


def test_llm_json_is_extracted_from_chatty_replies():
    llm = FakeLLM('Sure! Here it is:\n{"vendor_name": "Acme Traders", "total": 1180}\nHope that helps.')
    assert llm_extract(llm, "m", INVOICE, INVOICE_TEXT) == {"vendor_name": "Acme Traders", "total": 1180}


def test_unparseable_llm_reply_is_none_not_an_error():
    assert llm_extract(FakeLLM("I cannot do that"), "m", INVOICE, INVOICE_TEXT) is None
    assert llm_extract(FakeLLM("{broken json"), "m", INVOICE, INVOICE_TEXT) is None
    assert llm_extract(FakeLLM("[1, 2]"), "m", INVOICE, INVOICE_TEXT) is None


def test_merge_prefers_valid_rules_for_typed_fields_and_the_model_for_names():
    rules = {"vendor_name": "Acme Traders", "total": "1,180.00", "vendor_gstin": "29AABCU9603R1ZM"}
    model = {"vendor_name": "Acme Traders Pvt Ltd", "total": "999.00", "vendor_gstin": "29AABCU9603R1ZX"}
    merged = merge(INVOICE, rules, model)
    assert merged["vendor_name"] == "Acme Traders Pvt Ltd"
    assert merged["total"] == "1,180.00"
    assert merged["vendor_gstin"] == "29AABCU9603R1ZM"


def test_model_fills_what_rules_missed_and_garbage_is_kept_for_the_reviewer():
    merged = merge(INVOICE, {"invoice_date": None, "total": "abc"}, {"invoice_date": "2026-01-02"})
    assert merged["invoice_date"] == "2026-01-02"
    assert merged["total"] == "abc"  # unusable everywhere, but better shown to the reviewer than blanked


def test_values_are_normalised():
    llm = FakeLLM('{"invoice_date": "5 Sep 2026", "vendor_gstin": " 29aabcu9603r1zm ", "subtotal": "Rs 1,000"}')
    values = extract_values(INVOICE, "no structure here", llm, "m")
    assert values["vendor_gstin"] == "29AABCU9603R1ZM"
    assert values["subtotal"] == 1000.0


REAL_WORLD_LAYOUT = """TAX INVOICE
(ORIGINAL FOR RECIPIENT)
Shree Krishna Textiles Pvt Ltd
Ring Road, Surat 395002
GSTIN: 24AAACS1234A1Z1
Invoice No: SKT/2026/0441
Invoice Date: 12/10/2026
Bill To
Patel Fabrics
Taxable Value: 10,169.20
CGST @ 9%: 915.20
SGST (9%) on 10,169.20 = 915.20
Round off: 0.40
Amount Payable: Rs. 12,000.00
"""


def test_rules_skip_document_titles_for_the_vendor_name():
    from app.extraction.invoice import extract_invoice

    assert extract_invoice(REAL_WORLD_LAYOUT)["vendor_name"] == "Shree Krishna Textiles Pvt Ltd"


def test_rules_read_common_tax_and_total_layouts():
    from app.extraction.invoice import extract_invoice

    values = extract_invoice(REAL_WORLD_LAYOUT)
    assert values["tax_total"] == 1830.40  # CGST @ 9%: ... and SGST (9%) on X = Y (last amount, not the base)
    assert values["subtotal"] == "10,169.20"
    assert values["total"] == "12,000.00"


def test_tax_row_with_both_labels_and_repeated_lines_takes_the_totals():
    from app.extraction.invoice import _tax_total

    lines = ["CGST 9% 450.00", "CGST 9% 450.00", "Total CGST 900.00  Total SGST 900.00"]
    assert _tax_total(lines) == 1800.00
