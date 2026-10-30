from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select

from app.api.deps import ClientIP, CurrentUser, DbSession, DocumentDep, membership_for, require_manager
from app.models import Document, DocumentChunk, DocumentStatus, Workspace
from app.schemas.document import (
    ChunkPage,
    DocumentDetail,
    DocumentRead,
    DocumentStatusRead,
)
from app.services import audit_service
from app.services.document_service import delete_document
from app.tasks.ingestion_tasks import ingest_document_task

router = APIRouter(prefix="/documents", tags=["documents"])


def _chunk_count(db: DbSession, document: Document) -> int:
    return db.scalar(select(func.count()).where(DocumentChunk.document_id == document.id)) or 0


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document(document: DocumentDep, db: DbSession):
    return DocumentDetail(
        **DocumentRead.model_validate(document).model_dump(),
        chunk_count=_chunk_count(db, document),
    )


@router.get("/{document_id}/file", response_class=FileResponse)
def download_document(document: DocumentDep):
    """The original upload, for the citation viewer (PDFs open inline at #page=N)."""
    path = Path(document.storage_path)
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File is no longer stored")
    # Text and Markdown are served as plain text so a browser never renders uploaded HTML/JS.
    media_type = document.mime_type if document.mime_type in INLINE_TYPES else "text/plain; charset=utf-8"
    return FileResponse(
        path,
        media_type=media_type,
        filename=document.filename,
        content_disposition_type="inline" if document.mime_type == "application/pdf" else "attachment",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"},
    )


INLINE_TYPES = {"application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}


@router.get("/{document_id}/status", response_model=DocumentStatusRead)
def get_document_status(document: DocumentDep, db: DbSession):
    job = document.ingestion_jobs[-1] if document.ingestion_jobs else None
    return DocumentStatusRead(
        document_id=document.id,
        status=document.status,
        error_message=job.error_message if job else None,
        started_at=job.started_at if job else None,
        completed_at=job.completed_at if job else None,
        chunk_count=_chunk_count(db, document),
    )


@router.get("/{document_id}/chunks", response_model=ChunkPage)
def list_document_chunks(
    document: DocumentDep,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    items = db.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document.id)
        .order_by(DocumentChunk.chunk_index)
        .limit(limit)
        .offset(offset)
    ).all()
    return ChunkPage(total=_chunk_count(db, document), items=items)


@router.post("/{document_id}/reprocess", status_code=status.HTTP_202_ACCEPTED, response_model=DocumentStatusRead)
def reprocess_document(document: DocumentDep, background_tasks: BackgroundTasks, db: DbSession):
    if document.status == DocumentStatus.PROCESSING:
        raise HTTPException(status.HTTP_409_CONFLICT, "Document is already being processed")
    document.status = DocumentStatus.PENDING
    db.commit()
    background_tasks.add_task(ingest_document_task, document.id)
    return DocumentStatusRead(document_id=document.id, status=document.status, chunk_count=_chunk_count(db, document))


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_document(document: DocumentDep, user: CurrentUser, db: DbSession, ip: ClientIP):
    """The uploader, or an owner/admin of the organization, can delete a document."""
    workspace = db.get(Workspace, document.workspace_id)
    if document.uploaded_by != user.id:
        require_manager(membership_for(db, user, workspace.organization_id))
    document_id, filename = document.id, document.filename
    delete_document(db, document)
    audit_service.record(
        db,
        "document.delete",
        user=user,
        organization_id=workspace.organization_id,
        target_type="document",
        target_id=document_id,
        ip=ip,
        filename=filename,
    )
