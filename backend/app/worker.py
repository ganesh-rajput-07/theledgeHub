"""Ingestion worker: python -m app.worker

Run as many as you like (each container or process handles one document at a time). Stops gracefully on
SIGTERM/SIGINT after finishing the current document."""

import logging
import signal
import time

from app.core.config import get_settings
from app.database.session import SessionLocal
from app.ingestion.queue import claim, process, requeue_stale

log = logging.getLogger("knowledgehub.worker")
REQUEUE_EVERY_SECONDS = 60


def run_once() -> bool:
    """Process one pending job. Returns False when the queue is empty."""
    with SessionLocal() as db:
        job = claim(db)
        if job is None:
            return False
        log.info("Processing document %s (job %s, attempt %d)", job.document_id, job.id, job.attempts)
        process(db, job)
        log.info("Finished job %s: %s", job.id, job.status)
        return True


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    stopping = False

    def stop(signum, _frame):
        nonlocal stopping
        stopping = True
        log.info("Received %s, finishing the current document then exiting", signal.Signals(signum).name)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    # Load the models once up front, so the first document doesn't pay for it.
    from app.ingestion.chunker import get_token_counter
    from app.rag.embeddings import get_embedding_provider

    get_embedding_provider()
    get_token_counter(settings.embedding_model)
    log.info("Worker ready (polling every %.1fs)", settings.worker_poll_seconds)

    last_requeue = 0.0
    while not stopping:
        if time.monotonic() - last_requeue > REQUEUE_EVERY_SECONDS:
            with SessionLocal() as db:
                requeue_stale(db, settings.job_stale_seconds, settings.job_max_attempts)
            last_requeue = time.monotonic()
        if not run_once():
            time.sleep(settings.worker_poll_seconds)
    log.info("Worker stopped")


if __name__ == "__main__":
    main()
