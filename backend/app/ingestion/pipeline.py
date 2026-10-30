import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.ingestion.chunker import chunk_pages, get_token_counter
from app.ingestion.cleaner import clean_text
from app.ingestion.extractors import ExtractedPage, ExtractionError, extract
from app.models import Document, DocumentChunk, DocumentStatus, IngestionJob
from app.rag.embeddings import get_embedding_provider


def run_ingestion(db: Session, document_id: uuid.UUID) -> IngestionJob | None:
    """Extract (+OCR) -> clean -> chunk -> embed -> store. Re-running replaces previous chunks."""
    document = db.get(Document, document_id)
    if document is None:
        return None

    job = IngestionJob(
        document_id=document.id,
        status=DocumentStatus.PROCESSING,
        started_at=datetime.now(UTC),
    )
    document.status = DocumentStatus.PROCESSING
    db.add(job)
    db.commit()

    settings = get_settings()
    try:
        raw_pages = extract(Path(document.storage_path).read_bytes(), document.mime_type or "")
        pages = [ExtractedPage(p.page_number, clean_text(p.text), p.ocr) for p in raw_pages]
        chunks = chunk_pages(
            pages,
            count_tokens=get_token_counter(settings.embedding_model),
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )
        if not chunks:
            raise ExtractionError("No extractable text found (the document is empty or OCR could not read it)")

        provider = get_embedding_provider()
        vectors = provider.embed_documents([c.content for c in chunks])

        db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
        db.add_all(
            DocumentChunk(
                document_id=document.id,
                chunk_index=c.chunk_index,
                content=c.content,
                page_number=c.page_number,
                token_count=c.token_count,
                embedding=vector,
                metadata_=c.metadata,
            )
            for c, vector in zip(chunks, vectors, strict=True)
        )
        document.embedding_model = provider.model_name
        document.page_count = sum(1 for p in raw_pages if p.page_number is not None) or None
        document.status = job.status = DocumentStatus.COMPLETED
    except Exception as exc:  # noqa: BLE001 - any failure must be recorded on the job
        db.rollback()
        document.status = job.status = DocumentStatus.FAILED
        job.error_message = str(exc)[:2000]
    job.completed_at = datetime.now(UTC)
    db.commit()
    return job
