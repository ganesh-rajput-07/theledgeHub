import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.documents.pdf_tools import IMAGE_TYPES, PdfToolError, image_to_pdf
from app.models import Document

PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

ALLOWED_TYPES = {
    ".pdf": PDF_MIME,
    ".docx": DOCX_MIME,
    ".txt": "text/plain",
    ".md": "text/markdown",
}

_READ_BLOCK = 1024 * 1024


class UploadError(Exception):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class ValidatedFile:
    filename: str
    extension: str
    mime_type: str
    data: bytes
    origin: dict | None = None  # where the stored file came from, when it isn't the upload itself


def _read_limited(stream: BinaryIO, max_bytes: int) -> bytes:
    buffer = bytearray()
    while block := stream.read(_READ_BLOCK):
        buffer.extend(block)
        if len(buffer) > max_bytes:
            raise UploadError(f"File exceeds the {max_bytes // (1024 * 1024)} MB limit", 413)
    return bytes(buffer)


def _matches_signature(data: bytes, extension: str) -> bool:
    """Trust file contents, not the client's filename or Content-Type."""
    if extension == ".pdf":
        return data.startswith(b"%PDF-")
    if extension in (".jpg", ".jpeg"):
        return data.startswith(b"\xff\xd8\xff")
    if extension == ".png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if extension == ".docx":
        # DOCX is a ZIP container; macro-enabled .docm is rejected by its extension.
        return data.startswith(b"PK\x03\x04") and b"word/" in data
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return False
    return "\x00" not in text


def validate_upload(filename: str | None, stream: BinaryIO) -> ValidatedFile:
    safe_name = Path(filename or "").name.strip()[:255]
    extension = Path(safe_name).suffix.lower()
    if not safe_name or (extension not in ALLOWED_TYPES and extension not in IMAGE_TYPES):
        allowed = ", ".join(sorted({*ALLOWED_TYPES, *IMAGE_TYPES}))
        raise UploadError(f"Unsupported file type. Allowed: {allowed}", 415)

    data = _read_limited(stream, get_settings().max_upload_mb * 1024 * 1024)
    if not data:
        raise UploadError("File is empty", 400)
    if not _matches_signature(data, extension):
        raise UploadError(f"File content does not match its {extension} extension", 415)
    if extension in IMAGE_TYPES:
        # Photos of invoices (e.g. from WhatsApp) become upright one-page PDFs, so every tool and OCR applies.
        try:
            pdf = image_to_pdf(data)
        except PdfToolError as exc:
            raise UploadError(str(exc), 415) from exc
        name = f"{Path(safe_name).stem[:250]}.pdf"
        return ValidatedFile(name, ".pdf", PDF_MIME, pdf, {"operation": "photo", "converted_from": safe_name})
    return ValidatedFile(safe_name, extension, ALLOWED_TYPES[extension], data)


def create_document(
    db: Session, file: ValidatedFile, workspace_id: uuid.UUID, uploaded_by: uuid.UUID | None
) -> Document:
    document_id = uuid.uuid4()
    storage_dir = Path(get_settings().storage_dir).resolve()
    storage_dir.mkdir(parents=True, exist_ok=True)
    # Stored under a generated name, so the user-supplied filename never touches the filesystem.
    path = storage_dir / f"{document_id}{file.extension}"
    path.write_bytes(file.data)

    document = Document(
        id=document_id,
        workspace_id=workspace_id,
        uploaded_by=uploaded_by,
        filename=file.filename,
        storage_path=str(path),
        mime_type=file.mime_type,
        file_size=len(file.data),
        checksum=hashlib.sha256(file.data).hexdigest(),
        origin=file.origin,
    )
    db.add(document)
    try:
        db.commit()
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return document


def delete_document(db: Session, document: Document) -> None:
    """Deletes the row (chunks and jobs cascade in the database) and then the stored file."""
    path = Path(document.storage_path)
    db.delete(document)
    db.commit()
    path.unlink(missing_ok=True)
