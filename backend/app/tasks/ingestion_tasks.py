import uuid

from app.database.session import SessionLocal
from app.ingestion.queue import claim, process


def process_job_inline(job_id: uuid.UUID) -> None:
    """INGESTION_MODE=inline: run a just-enqueued job in this API process, through the same claim/process
    path as the worker (so a worker running at the same time can never process it twice)."""
    with SessionLocal() as db:
        if (job := claim(db, job_id)) is not None:
            process(db, job)
