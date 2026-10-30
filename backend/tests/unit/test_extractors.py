import pytest

from app.ingestion.extractors import ExtractionError, extract
from tests.factories import make_docx, make_pdf


def test_pdf_extraction_preserves_page_numbers():
    pages = extract(make_pdf(["Page one text.", "Page two text."]), "application/pdf")
    assert [p.page_number for p in pages] == [1, 2]
    assert "Page two text." in pages[1].text


def test_docx_extraction():
    mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    pages = extract(make_docx(["Leave policy.", "Insurance policy."]), mime)
    assert pages[0].page_number is None
    assert "Insurance policy." in pages[0].text


def test_invalid_pdf_raises_extraction_error():
    with pytest.raises(ExtractionError):
        extract(b"%PDF-1.7 garbage", "application/pdf")


def test_unsupported_type():
    with pytest.raises(ExtractionError):
        extract(b"x", "application/zip")
