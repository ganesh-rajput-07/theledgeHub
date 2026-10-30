"""A small PostgreSQL job queue on the `ingestion_jobs` table.

Workers claim jobs with SELECT ... FOR UPDATE SKIP LOCKED, so any number of worker processes (and API
replicas) can run side by side: each job is handed to exactly one of them, without extra infrastructure.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingestion.pipeline import run_ingestion
from app.models import Document, DocumentStatus, IngestionJob

log = logging.getLogger("knowledgehub.queue")

ACTIVE = (DocumentStatus.PENDING, DocumentStatus.PROCESSING)


class JobAlreadyActiveError(Exception):
    pass


def enqueue(db: Session, document: Document) -> IngestionJob:
    active = db.scalar(
        select(IngestionJob.id).where(IngestionJob.document_id == document.id, IngestionJob.status.in_(ACTIVE))
    )
    if active:
        raise JobAlreadyActiveError("Document is already queued or being processed")
    job = IngestionJob(document_id=document.id, status=DocumentStatus.PENDING)
    document.status = DocumentStatus.PENDING
    db.add(job)
    db.commit()
    return job


def claim(db: Session, job_id: uuid.UUID | None = None) -> IngestionJob | None:
    """Take the oldest pending job (or a specific one). Locked rows are skipped, never waited on."""
    stmt = (
        select(IngestionJob)
        .where(IngestionJob.status == DocumentStatus.PENDING)
        .order_by(IngestionJob.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if job_id is not None:
        stmt = stmt.where(IngestionJob.id == job_id)
    job = db.scalar(stmt)
    if job is None:
        db.rollback()
        return None
    job.status = DocumentStatus.PROCESSING
    job.started_at = datetime.now(UTC)
    job.attempts += 1
    db.commit()
    return job


def process(db: Session, job: IngestionJob) -> None:
    try:
        run_ingestion(db, job.document_id, job=job)
    except Exception:
        log.exception("Ingestion job %s crashed", job.id)
        db.rollback()
        if (stored := db.get(IngestionJob, job.id)) is not None:
            stored.status = DocumentStatus.FAILED
            stored.error_message = "Processing crashed unexpectedly"
            stored.completed_at = datetime.now(UTC)
            db.commit()


def requeue_stale(db: Session, stale_seconds: int, max_attempts: int) -> int:
    """Jobs whose worker died mid-run go back to the queue, or fail after `max_attempts` claims."""
    cutoff = datetime.now(UTC) - timedelta(seconds=stale_seconds)
    stuck = db.scalars(
        select(IngestionJob)
        .where(IngestionJob.status == DocumentStatus.PROCESSING, IngestionJob.started_at < cutoff)
        .with_for_update(skip_locked=True)
    ).all()
    for job in stuck:
        document = db.get(Document, job.document_id)
        if job.attempts >= max_attempts:
            job.status = DocumentStatus.FAILED
            job.error_message = f"Processing stopped {job.attempts} times (worker crashed or was restarted)"
            job.completed_at = datetime.now(UTC)
        else:
            job.status = DocumentStatus.PENDING
        if document is not None:
            document.status = job.status
    db.commit()
    if stuck:
        log.warning("Requeued or failed %d stale ingestion job(s)", len(stuck))
    return len(stuck)
