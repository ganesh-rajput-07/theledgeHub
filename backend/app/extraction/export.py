import io
from datetime import date

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from app.extraction.schema import DocumentSchema


def to_xlsx(schema: DocumentSchema, rows: list[tuple[str, dict, date | None]]) -> bytes:
    """One sheet of approved records: typed cells (real numbers and dates) so Excel can sum and sort them.
    `rows` are (source filename, values, approval date)."""
    book = Workbook()
    sheet = book.active
    sheet.title = schema.name[:31]
    sheet.append([spec.label for spec in schema.fields] + ["Source file", "Approved on"])
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for filename, values, approved in rows:
        record = []
        for spec in schema.fields:
            value = values.get(spec.key)
            if spec.type == "date" and isinstance(value, str):
                try:
                    value = date.fromisoformat(value)
                except ValueError:
                    pass
            record.append(value)
        sheet.append([*record, filename, approved])
    for index, spec in enumerate(schema.fields, 1):
        letter = get_column_letter(index)
        for cell in sheet[letter][1:]:
            if spec.type == "amount":
                cell.number_format = "#,##0.00"
            elif spec.type == "date":
                cell.number_format = "dd-mmm-yyyy"
        sheet.column_dimensions[letter].width = max(len(spec.label), 18)
    sheet.column_dimensions[get_column_letter(len(schema.fields) + 1)].width = 28
    sheet.freeze_panes = "A2"
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()
