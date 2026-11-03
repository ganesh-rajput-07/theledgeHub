import uuid

from app.database.session import SessionLocal
from app.services.extraction_service import run


def run_extraction_task(extraction_id: uuid.UUID, credential_id: uuid.UUID | None, model: str | None) -> None:
    """FastAPI background task: own database session, since the request's session is closed by then."""
    with SessionLocal() as db:
        run(db, extraction_id, credential_id, model)
