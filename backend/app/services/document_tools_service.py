"""Create new documents from existing PDFs (merge, extract pages, split, rotate). Originals are never changed."""

import uuid
from pathlib import Path

from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.documents import pdf_tools
from app.ingestion.queue import enqueue
from app.models import Document, User, Workspace
from app.services import audit_service
from app.services.document_service import PDF_MIME, ValidatedFile, create_document
from app.tasks.ingestion_tasks import process_job_inline

MAX_SPLIT_PARTS = 100


class ToolError(Exception):
    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.message, self.status_code = message, status_code


def pdf_bytes(document: Document) -> bytes:
    if document.mime_type != PDF_MIME:
        raise ToolError(f"“{document.filename}” isn't a PDF; page tools work on PDFs and photos")
    path = Path(document.storage_path)
    if not path.is_file():
        raise ToolError(f"The file for “{document.filename}” is no longer stored", 404)
    return path.read_bytes()


def output_name(requested: str | None, fallback: str) -> str:
    """User-chosen or generated filename; path parts stripped, always ending in .pdf."""
    name = Path((requested or "").strip()).name or fallback
    stem = name[:-4] if name.lower().endswith(".pdf") else name
    return f"{stem.strip()[:240] or 'document'}.pdf"


def stem(document: Document) -> str:
    return Path(document.filename).stem


def workspace_documents(db: Session, workspace_id: uuid.UUID, ids: list[uuid.UUID]) -> list[Document]:
    """The documents in the order asked for; any id outside this workspace is a 404 (never trust client ids)."""
    found = {
        d.id: d for d in db.scalars(select(Document).where(Document.workspace_id == workspace_id, Document.id.in_(ids)))
    }
    if missing := [str(i) for i in ids if i not in found]:
        raise ToolError(f"Documents not found in this workspace: {missing}", 404)
    return [found[i] for i in ids]


def save_derived(
    db: Session,
    background_tasks: BackgroundTasks,
    workspace: Workspace,
    user: User,
    ip: str,
    data: bytes,
    filename: str,
    operation: str,
    sources: list[Document],
    **details,
) -> Document:
    """Store a tool's output as a new document, audit it, and start processing it like an upload."""
    limit = get_settings().max_upload_mb * 4 * 1024 * 1024
    if len(data) > limit:
        raise ToolError(f"The result is larger than {limit // (1024 * 1024)} MB", 413)
    origin = {
        "operation": operation,
        "sources": [{"id": str(d.id), "filename": d.filename} for d in sources],
        **details,
    }
    document = create_document(db, ValidatedFile(filename, ".pdf", PDF_MIME, data, origin), workspace.id, user.id)
    audit_service.record(
        db,
        f"document.{operation}",
        user=user,
        organization_id=workspace.organization_id,
        target_type="document",
        target_id=document.id,
        ip=ip,
        filename=document.filename,
        sources=[d.filename for d in sources],
        **details,
    )
    job = enqueue(db, document)
    if get_settings().ingestion_mode == "inline":
        background_tasks.add_task(process_job_inline, job.id)
    return document


def merge(db, background_tasks, workspace, user, ip, ids: list[uuid.UUID], filename: str | None) -> Document:
    if len(set(ids)) != len(ids):
        raise ToolError("Each document can appear only once in a merge")
    sources = workspace_documents(db, workspace.id, ids)
    data = pdf_tools.merge([pdf_bytes(d) for d in sources])
    name = output_name(filename, f"Merged - {stem(sources[0])}")
    return save_derived(db, background_tasks, workspace, user, ip, data, name, "merge", sources)


def extract_pages(db, background_tasks, workspace, user, ip, document, pages: str, filename: str | None) -> Document:
    data = pdf_bytes(document)
    chosen = pdf_tools.parse_pages(pages, pdf_tools.page_count(data))
    name = output_name(filename, f"{stem(document)} (pages {pages.replace(' ', '')})")
    return save_derived(
        db, background_tasks, workspace, user, ip, pdf_tools.select_pages(data, chosen), name, "extract_pages",
        [document], pages=pages,
    )  # fmt: skip


def split(db, background_tasks, workspace, user, ip, document, ranges: list[str] | None) -> list[Document]:
    """No ranges: one document per page. Ranges: one document per range, e.g. ["1-2", "3", "4-6"]."""
    data = pdf_bytes(document)
    total = pdf_tools.page_count(data)
    groups = [pdf_tools.parse_pages(r, total) for r in ranges] if ranges else [[p] for p in range(1, total + 1)]
    if len(groups) < 2:
        raise ToolError("Splitting needs at least two parts (a single page or range is 'Extract pages')")
    if len(groups) > MAX_SPLIT_PARTS:
        raise ToolError(f"Split into at most {MAX_SPLIT_PARTS} documents at once")
    parts = pdf_tools.split(data, groups)
    labels = ranges or [str(p) for p in range(1, total + 1)]
    created = []
    for i, (part, label) in enumerate(zip(parts, labels, strict=True), start=1):
        name = output_name(None, f"{stem(document)} - part {i} (p{label})")
        created.append(
            save_derived(db, background_tasks, workspace, user, ip, part, name, "split", [document], pages=label)
        )
    return created


def rotate(db, background_tasks, workspace, user, ip, document, pages: str, degrees: int) -> Document:
    data = pdf_bytes(document)
    chosen = pdf_tools.parse_pages(pages, pdf_tools.page_count(data))
    name = output_name(None, f"{stem(document)} (rotated)")
    return save_derived(
        db, background_tasks, workspace, user, ip, pdf_tools.rotate(data, chosen, degrees), name, "rotate",
        [document], pages=pages, degrees=degrees,
    )  # fmt: skip
