"""Retrieval-quality regression guard on the evaluation corpus (see docs/evaluation.md).
Thresholds sit a little below the measured values, so a real regression fails while noise doesn't."""

import pytest

from app.core.config import get_settings
from app.database.session import SessionLocal
from evaluation.harness import create_workspace, evaluate_retrieval, ingest_corpus, load_dataset


@pytest.fixture(scope="module")
def report(tmp_path_factory):
    settings = get_settings()
    with SessionLocal() as db:
        workspace = create_workspace(db, "rag-quality")
        ingest_corpus(db, workspace.id, tmp_path_factory.mktemp("corpus"), settings.chunk_size, settings.chunk_overlap)
        return evaluate_retrieval(db, workspace.id, load_dataset())


def test_retrieval_finds_the_right_page(report):
    # Default pipeline = hybrid search + cross-encoder reranking (vector-only measured 0.86 / 0.906).
    assert report.hit_rate[1] >= 0.90  # measured 0.93
    assert report.hit_rate[5] >= 0.95  # measured 1.00
    assert report.mrr >= 0.93  # measured 0.964


def test_distractors_are_not_confused(report):
    # e.g. our revenue vs the competitor's revenue, leave policy vs remote-work policy
    assert report.by_kind["distractor"]["top1"] == 1.0


def test_reranking_beats_plain_vector_search(tmp_path_factory):
    settings = get_settings()
    with SessionLocal() as db:
        workspace = create_workspace(db, "rerank-vs-vector")
        ingest_corpus(db, workspace.id, tmp_path_factory.mktemp("c2"), settings.chunk_size, settings.chunk_overlap)
        plain = evaluate_retrieval(db, workspace.id, load_dataset(), mode="vector", rerank=False)
        reranked = evaluate_retrieval(db, workspace.id, load_dataset(), mode="hybrid", rerank=True)
    assert reranked.mrr > plain.mrr
    assert reranked.by_kind["paraphrase"]["top1"] >= plain.by_kind["paraphrase"]["top1"]  # no trade-off


def test_default_not_found_threshold_keeps_every_answerable_question(report):
    row = next(r for r in report.thresholds if abs(r["threshold"] - get_settings().rag_min_score) < 1e-9)
    assert row["answerable_attempted"] == 1.0
    assert row["unanswerable_refused"] > 0
