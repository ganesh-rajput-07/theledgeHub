"""INGESTION_MODE=queue: uploads are queued in PostgreSQL and processed by `python -m app.worker`."""

import threading
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app import worker
from app.core.config import get_settings
from app.database.session import SessionLocal
from app.ingestion.queue import claim, requeue_stale
from app.models import DocumentStatus, IngestionJob
from tests.factories import make_pdf


@pytest.fixture
def queue_mode(monkeypatch):
    monkeypatch.setattr(get_settings(), "ingestion_mode", "queue")


def upload(api, name="queued.pdf", text="Queued document about the quarterly travel budget."):
    response = api.post(
        f"/api/v1/workspaces/{api.workspace_id}/documents",
        files={"file": (name, make_pdf([text]), "application/pdf")},
    )
    assert response.status_code == 202
    return response.json()["document_id"]


def drain_queue():
    while worker.run_once():
        pass


def test_upload_waits_for_a_worker(api, queue_mode):
    document_id = upload(api)
    assert api.get(f"/api/v1/documents/{document_id}/status").json()["status"] == "pending"

    assert worker.run_once() is True
    status = api.get(f"/api/v1/documents/{document_id}/status").json()
    assert status["status"] == "completed" and status["chunk_count"] == 1
    results = api.post(f"/api/v1/workspaces/{api.workspace_id}/search", json={"query": "travel budget"}).json()
    assert results["results"][0]["document_id"] == document_id


def test_reprocess_refused_while_queued(api, queue_mode):
    document_id = upload(api)
    assert api.post(f"/api/v1/documents/{document_id}/reprocess").status_code == 409
    drain_queue()
    assert api.post(f"/api/v1/documents/{document_id}/reprocess").status_code == 202
    drain_queue()
    assert api.get(f"/api/v1/documents/{document_id}/status").json()["status"] == "completed"


def test_concurrent_workers_never_claim_the_same_job(api, queue_mode):
    drain_queue()
    for i in range(6):
        upload(api, f"doc-{i}.pdf", f"Document number {i} about topic {i}.")

    claimed, lock = [], threading.Lock()

    def worker_thread():
        with SessionLocal() as db:
            while (job := claim(db)) is not None:
                with lock:
                    claimed.append(job.id)

    threads = [threading.Thread(target=worker_thread) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(claimed) == 6
    assert len(set(claimed)) == 6  # FOR UPDATE SKIP LOCKED: every job exactly once


def test_stale_jobs_are_requeued_then_failed(api, queue_mode):
    drain_queue()
    document_id = upload(api)
    with SessionLocal() as db:
        job = claim(db)  # a worker takes the job ... and dies
        job.started_at = datetime.now(UTC) - timedelta(hours=2)
        db.commit()

        assert requeue_stale(db, stale_seconds=1800, max_attempts=3) == 1
        db.refresh(job)
        assert job.status == DocumentStatus.PENDING

        for _ in range(2):  # two more crashed attempts
            job = claim(db)
            job.started_at = datetime.now(UTC) - timedelta(hours=2)
            db.commit()
            requeue_stale(db, stale_seconds=1800, max_attempts=3)
        db.refresh(job)
        assert job.status == DocumentStatus.FAILED and job.attempts == 3

    status = api.get(f"/api/v1/documents/{document_id}/status").json()
    assert status["status"] == "failed" and "stopped 3 times" in status["error_message"]


def test_running_jobs_are_left_alone(api, queue_mode):
    drain_queue()
    upload(api)
    with SessionLocal() as db:
        job = claim(db)  # started just now: a healthy worker is on it
        assert requeue_stale(db, stale_seconds=1800, max_attempts=3) == 0
        assert db.scalar(select(IngestionJob.status).where(IngestionJob.id == job.id)) == DocumentStatus.PROCESSING
