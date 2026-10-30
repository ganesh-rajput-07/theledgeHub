import uuid

from app.database.session import SessionLocal
from app.ingestion.pipeline import run_ingestion


def ingest_document_task(document_id: uuid.UUID) -> None:
    """Background entry point: uses its own session, never the request's."""
    with SessionLocal() as db:
        run_ingestion(db, document_id)
