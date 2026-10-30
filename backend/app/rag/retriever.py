import uuid
from dataclasses import dataclass

from sqlalchemy import Text, cast, func, select, text
from sqlalchemy.dialects.postgresql import TSQUERY
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Document, DocumentChunk, DocumentStatus
from app.rag.embeddings import EmbeddingProvider

# Reciprocal Rank Fusion constant (60 is the value from the original RRF paper and the common default).
RRF_K = 60


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    page_number: int | None
    chunk_index: int
    content: str
    score: float  # cosine similarity, 1.0 = identical direction (also used for RAG_MIN_SCORE)


def _keyword_query(query: str):
    """OR of the question's stemmed terms: `plainto_tsquery` alone would AND them, and a page rarely
    contains every word of a question. ts_rank_cd still rewards chunks that match more terms."""
    return cast(func.replace(cast(func.plainto_tsquery("english", query), Text), "&", "|"), TSQUERY)


def retrieve(
    db: Session,
    provider: EmbeddingProvider,
    query: str,
    top_k: int,
    *,
    workspace_id: uuid.UUID,
    document_ids: list[uuid.UUID] | None = None,
    min_score: float | None = None,
    mode: str | None = None,
    rerank: bool | None = None,
) -> list[RetrievedChunk]:
    """Search a workspace's completed documents, best chunks first.

    mode "vector": cosine similarity only. mode "hybrid" (default): vector and full-text rankings merged
    with Reciprocal Rank Fusion, which rescues keyword-heavy questions (names, numbers, years) that a
    small embedding model ranks too low. Either way, chunks below `min_score` cosine are dropped, so the
    not-found threshold means the same thing in both modes. With reranking (default on), a cross-encoder
    orders the best `rerank_candidates`; the search modes then only decide which candidates it sees.
    workspace_id is required: there is deliberately no way to search across tenants."""
    settings = get_settings()
    mode = mode or settings.retrieval_mode
    rerank = settings.rerank_enabled if rerank is None else rerank
    distance = DocumentChunk.embedding.cosine_distance(provider.embed_query(query))
    wanted = max(top_k, settings.rerank_candidates) if rerank else top_k
    pool = wanted if mode == "vector" else max(wanted * 2, 40)

    def base(*extra):
        stmt = (
            select(DocumentChunk, Document.filename, distance.label("distance"), *extra)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                Document.workspace_id == workspace_id,
                Document.status == DocumentStatus.COMPLETED,
                DocumentChunk.embedding.is_not(None),
            )
        )
        return stmt.where(DocumentChunk.document_id.in_(document_ids)) if document_ids else stmt

    # With filters, a plain HNSW scan can return fewer rows than asked for; iterative scan keeps searching.
    db.execute(text("SET LOCAL hnsw.iterative_scan = strict_order"))
    vector_rows = db.execute(base().order_by(distance).limit(pool)).all()
    keyword_rows = []
    if mode == "hybrid":
        tsquery = _keyword_query(query)
        rank = func.ts_rank_cd(DocumentChunk.search_vector, tsquery)
        keyword_rows = db.execute(
            base().where(DocumentChunk.search_vector.op("@@")(tsquery)).order_by(rank.desc()).limit(pool)
        ).all()
    db.rollback()  # ends the transaction that SET LOCAL applied to

    candidates: dict[uuid.UUID, tuple] = {}
    fused: dict[uuid.UUID, float] = {}
    keyword_weight = settings.hybrid_keyword_weight
    for ranking, weight in ((vector_rows, 1.0), (keyword_rows, keyword_weight)):
        for position, (chunk, filename, dist) in enumerate(ranking, start=1):
            candidates[chunk.id] = (chunk, filename, dist)
            fused[chunk.id] = fused.get(chunk.id, 0.0) + weight / (RRF_K + position)

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
        for chunk, filename, dist in candidates.values()
    ]
    if min_score is not None:
        results = [r for r in results if r.score >= min_score]
    results.sort(key=lambda r: fused[r.chunk_id], reverse=True)
    results = results[:wanted]
    if rerank and len(results) > 1:
        from app.rag.reranker import get_reranker

        scores = get_reranker().scores(query, [r.content for r in results])
        results = [r for _, r in sorted(zip(scores, results, strict=True), key=lambda pair: -pair[0])]
    return results[:top_k]
