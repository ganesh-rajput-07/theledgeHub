import uuid
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import Document, DocumentChunk, DocumentStatus
from app.rag.embeddings import EmbeddingProvider


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    page_number: int | None
    chunk_index: int
    content: str
    score: float  # cosine similarity, 1.0 = identical direction


def retrieve(
    db: Session,
    provider: EmbeddingProvider,
    query: str,
    top_k: int,
    *,
    workspace_id: uuid.UUID,
    document_ids: list[uuid.UUID] | None = None,
    min_score: float | None = None,
) -> list[RetrievedChunk]:
    """Semantic search over a workspace's completed documents, closest chunks first.
    workspace_id is required: there is deliberately no way to search across tenants."""
    query_vector = provider.embed_query(query)
    distance = DocumentChunk.embedding.cosine_distance(query_vector)

    stmt = (
        select(DocumentChunk, Document.filename, distance.label("distance"))
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            Document.workspace_id == workspace_id,
            Document.status == DocumentStatus.COMPLETED,
            DocumentChunk.embedding.is_not(None),
        )
        .order_by(distance)
        .limit(top_k)
    )
    if document_ids:
        stmt = stmt.where(DocumentChunk.document_id.in_(document_ids))

    # With filters, a plain HNSW scan can return fewer than top_k rows; iterative scan keeps searching.
    db.execute(text("SET LOCAL hnsw.iterative_scan = strict_order"))
    rows = db.execute(stmt).all()
    db.rollback()  # ends the transaction that SET LOCAL applied to

    results = [
        RetrievedChunk(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            filename=filename,
            page_number=chunk.page_number,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            score=round(1 - dist, 4),
        )
        for chunk, filename, dist in rows
    ]
    if min_score is not None:
        results = [r for r in results if r.score >= min_score]
    return results
