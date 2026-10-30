import io

import pytest

from app.core.config import get_settings
from app.services.document_service import UploadError, validate_upload
from tests.factories import make_docx, make_pdf


def test_accepts_valid_pdf_and_strips_path_from_filename():
    file = validate_upload("../../etc/report.pdf", io.BytesIO(make_pdf(["Hello."])))
    assert file.filename == "report.pdf"
    assert file.mime_type == "application/pdf"


def test_accepts_docx_and_markdown():
    assert validate_upload("a.docx", io.BytesIO(make_docx(["x"]))).extension == ".docx"
    assert validate_upload("notes.MD", io.BytesIO(b"# Title")).mime_type == "text/markdown"


@pytest.mark.parametrize(
    ("filename", "data", "status"),
    [
        ("virus.exe", b"MZ...", 415),
        ("macro.docm", b"PK\x03\x04word/", 415),
        ("fake.pdf", b"just text", 415),
        ("binary.txt", b"\xff\xfe\x00\x00", 415),
        ("empty.txt", b"", 400),
    ],
)
def test_rejects_bad_files(filename, data, status):
    with pytest.raises(UploadError) as exc:
        validate_upload(filename, io.BytesIO(data))
    assert exc.value.status_code == status


def test_rejects_oversized_file(monkeypatch):
    monkeypatch.setattr(get_settings(), "max_upload_mb", 1)
    with pytest.raises(UploadError) as exc:
        validate_upload("big.txt", io.BytesIO(b"a" * (1024 * 1024 + 1)))
    assert exc.value.status_code == 413
