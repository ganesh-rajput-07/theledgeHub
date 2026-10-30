"""Measurement code shared by the CLI (`python -m evaluation`) and the pytest regression test."""

import json
import statistics
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.ingestion.pipeline import run_ingestion
from app.llm.base import LLMProvider
from app.models import Document, DocumentStatus, Organization, Workspace
from app.rag.embeddings import get_embedding_provider
from app.rag.pipeline import answer_question
from app.rag.retriever import retrieve
from evaluation.corpus import build_pdfs

DATASET = Path(__file__).with_name("dataset.json")


def load_dataset() -> list[dict]:
    return json.loads(DATASET.read_text())


@contextmanager
def settings_override(**values):
    settings = get_settings()
    previous = {k: getattr(settings, k) for k in values}
    for k, v in values.items():
        setattr(settings, k, v)
    try:
        yield
    finally:
        for k, v in previous.items():
            setattr(settings, k, v)


def create_workspace(db: Session, name: str) -> Workspace:
    org = Organization(name=f"Eval {name}", slug=f"eval-{uuid.uuid4().hex[:10]}")
    db.add(org)
    db.flush()
    workspace = Workspace(organization_id=org.id, name=name)
    db.add(workspace)
    db.commit()
    return workspace


def ingest_corpus(db: Session, workspace_id: uuid.UUID, pdf_dir: Path, chunk_size: int, chunk_overlap: int) -> dict:
    """Ingests the corpus with the given chunking and returns ingestion stats."""
    started = time.perf_counter()
    documents = []
    with settings_override(chunk_size=chunk_size, chunk_overlap=chunk_overlap):
        for filename, path in build_pdfs(pdf_dir).items():
            document = Document(
                workspace_id=workspace_id,
                filename=filename,
                storage_path=str(path),
                mime_type="application/pdf",
                file_size=path.stat().st_size,
            )
            db.add(document)
            db.commit()
            run_ingestion(db, document.id)
            db.refresh(document)
            if document.status != DocumentStatus.COMPLETED:
                raise RuntimeError(f"Ingestion failed for {filename}")
            documents.append(document)
    chunks = sum(len(d.chunks) for d in documents)
    return {"documents": len(documents), "chunks": chunks, "seconds": round(time.perf_counter() - started, 1)}


def _relevant(result, expected: set[tuple[str, int]]) -> bool:
    return (result.filename, result.page_number) in expected


@dataclass
class RetrievalReport:
    k_values: list[int]
    recall: dict[int, float]
    precision: dict[int, float]
    hit_rate: dict[int, float]
    mrr: float
    by_kind: dict[str, dict[str, float]]
    thresholds: list[dict]
    latency_ms_p50: float
    latency_ms_p95: float
    misses: list[dict] = field(default_factory=list)


def evaluate_retrieval(
    db: Session,
    workspace_id: uuid.UUID,
    dataset: list[dict],
    k_values=(1, 3, 5, 8),
    thresholds=None,
    mode: str | None = None,
    rerank: bool | None = None,
) -> RetrievalReport:
    thresholds = thresholds or [round(0.10 + 0.05 * i, 2) for i in range(8)]  # 0.10 .. 0.45
    provider = get_embedding_provider()
    max_k = max(k_values)
    recall = {k: [] for k in k_values}
    precision = {k: [] for k in k_values}
    hits = {k: [] for k in k_values}
    reciprocal_ranks, latencies, top_scores, kinds, misses = [], [], [], {}, []

    for item in dataset:
        started = time.perf_counter()
        candidates = retrieve(
            db, provider, item["question"], top_k=max_k, workspace_id=workspace_id, mode=mode, rerank=rerank
        )
        latencies.append((time.perf_counter() - started) * 1000)
        # Mirror production: "not found" is decided by the *best* cosine score among candidates, and the
        # ranking the model sees only contains chunks at or above RAG_MIN_SCORE.
        top_scores.append((bool(item["sources"]), max((r.score for r in candidates), default=0.0)))
        results = [r for r in candidates if r.score >= get_settings().rag_min_score]
        if not item["sources"]:
            continue

        expected = {(s["document"], s["page"]) for s in item["sources"]}
        relevant_flags = [_relevant(r, expected) for r in results]
        for k in k_values:
            found = {(r.filename, r.page_number) for r in results[:k]} & expected
            recall[k].append(len(found) / len(expected))
            precision[k].append(sum(relevant_flags[:k]) / k)
            hits[k].append(1.0 if found else 0.0)
        rank = next((i + 1 for i, flag in enumerate(relevant_flags) if flag), None)
        reciprocal_ranks.append(1 / rank if rank else 0.0)
        kinds.setdefault(item["kind"], []).append(1.0 if rank == 1 else 0.0)
        if rank != 1:
            misses.append(
                {
                    "question": item["question"],
                    "expected": sorted(expected),
                    "got": [(r.filename, r.page_number, r.score) for r in results[:3]],
                    "rank": rank,
                }
            )

    sweep = []
    for t in thresholds:
        answered_ok = [s >= t for is_answerable, s in top_scores if is_answerable]
        refused_ok = [s < t for is_answerable, s in top_scores if not is_answerable]
        sweep.append(
            {
                "threshold": t,
                "answerable_attempted": statistics.mean(answered_ok),
                "unanswerable_refused": statistics.mean(refused_ok) if refused_ok else None,
                "accuracy": statistics.mean(answered_ok + refused_ok),
            }
        )

    mean = lambda values: round(statistics.mean(values), 3)  # noqa: E731
    return RetrievalReport(
        k_values=list(k_values),
        recall={k: mean(v) for k, v in recall.items()},
        precision={k: mean(v) for k, v in precision.items()},
        hit_rate={k: mean(v) for k, v in hits.items()},
        mrr=mean(reciprocal_ranks),
        by_kind={kind: {"top1": mean(v), "questions": len(v)} for kind, v in sorted(kinds.items())},
        thresholds=sweep,
        latency_ms_p50=round(statistics.median(latencies), 1),
        latency_ms_p95=round(sorted(latencies)[int(0.95 * (len(latencies) - 1))], 1),
        misses=misses,
    )


def _contains(answer: str, fact: str) -> bool:
    normalize = lambda s: s.lower().replace(",", "")  # noqa: E731
    return normalize(fact) in normalize(answer)


def evaluate_answers(db: Session, workspace_id: uuid.UUID, dataset: list[dict], llm: LLMProvider, model: str) -> dict:
    """End-to-end: the real answer pipeline (retrieve -> prompt -> model -> validated citations)."""
    rows = []
    for item in dataset:
        result = answer_question(db, llm, model, item["question"], [], workspace_id, None)
        expected = {(s["document"], s["page"]) for s in item["sources"]}
        cited = [(c.chunk.filename, c.chunk.page_number) for c in result.citations]
        rows.append(
            {
                "question": item["question"],
                "answerable": bool(item["sources"]),
                "status": result.status,
                "facts_found": all(_contains(result.answer, f) for f in item["facts"]) if item["facts"] else None,
                "citations": len(cited),
                "correct_citations": sum(1 for c in cited if c in expected),
                "latency_ms": result.latency_ms,
                "tokens": (result.input_tokens or 0) + (result.output_tokens or 0),
                "answer": result.answer,
            }
        )

    answerable = [r for r in rows if r["answerable"]]
    unanswerable = [r for r in rows if not r["answerable"]]
    cited_total = sum(r["citations"] for r in answerable)
    latencies = sorted(r["latency_ms"] for r in rows)
    return {
        "model": model,
        "answered_rate": round(statistics.mean(r["status"] == "completed" for r in answerable), 3),
        "fact_recall": round(statistics.mean(bool(r["facts_found"]) for r in answerable), 3),
        "grounded_rate": round(statistics.mean(r["citations"] > 0 for r in answerable), 3),
        "citation_precision": round(sum(r["correct_citations"] for r in answerable) / cited_total, 3)
        if cited_total
        else None,
        "unanswerable_refused": round(statistics.mean(r["status"] == "not_found" for r in unanswerable), 3)
        if unanswerable
        else None,
        "latency_ms_p50": statistics.median(latencies),
        "latency_ms_p95": latencies[int(0.95 * (len(latencies) - 1))],
        "total_tokens": sum(r["tokens"] for r in rows),
        "rows": rows,
    }
