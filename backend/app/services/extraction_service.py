import logging
import uuid
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.extraction.extractor import extract_values
from app.extraction.schema import SCHEMAS, DocumentSchema, Issue, clean_values, validate
from app.ingestion.extractors import ExtractionError, extract
from app.llm.base import LLMError
from app.llm.factory import build_provider_for_credential
from app.models import Document, Extraction, ExtractionStatus, ProviderCredential, User, Workspace

log = logging.getLogger("knowledgehub.extraction")
STALE_AFTER = timedelta(minutes=10)  # a run "processing" longer than this lost its process and may be restarted


class ExtractionBusyError(Exception):
    pass


class ExtractionStateError(Exception):
    """The extraction is not in a state where this action makes sense (still processing, failed...)."""


def get_schema(key: str) -> DocumentSchema | None:
    return SCHEMAS.get(key)


def organization_id(db: Session, document: Document) -> uuid.UUID:
    return db.get(Workspace, document.workspace_id).organization_id


def start(db: Session, document: Document, schema_key: str) -> Extraction:
    """Create or reset the document's extraction and mark it processing."""
    extraction = db.scalar(select(Extraction).where(Extraction.document_id == document.id))
    if extraction is None:
        extraction = Extraction(document_id=document.id, schema_key=schema_key)
        db.add(extraction)
    elif extraction.status == ExtractionStatus.PROCESSING and (datetime.now(UTC) - extraction.updated_at < STALE_AFTER):
        raise ExtractionBusyError("Extraction is already running for this document")
    extraction.schema_key = schema_key
    extraction.status = ExtractionStatus.PROCESSING
    extraction.values, extraction.issues = {}, []
    extraction.duplicate_key = extraction.model = extraction.error_message = None
    extraction.reviewed_by = extraction.reviewed_at = None
    db.commit()
    return extraction


def refresh_issues(db: Session, extraction: Extraction, schema: DocumentSchema, org_id: uuid.UUID) -> None:
    """Re-run validation and the duplicate check; call after every change to `values`."""
    issues = validate(schema, extraction.values)
    extraction.duplicate_key = schema.duplicate_key(extraction.values)
    if extraction.duplicate_key:
        twin = db.scalar(
            select(Document.filename)
            .select_from(Extraction)
            .join(Document, Document.id == Extraction.document_id)
            .join(Workspace, Workspace.id == Document.workspace_id)
            .where(
                Workspace.organization_id == org_id,
                Extraction.schema_key == extraction.schema_key,
                Extraction.duplicate_key == extraction.duplicate_key,
                Extraction.id != extraction.id,
            )
            .limit(1)
        )
        if twin:
            issues.append(Issue("duplicate", f"Looks like a duplicate of {twin}", None))
    extraction.issues = [asdict(issue) for issue in issues]


def run(db: Session, extraction_id: uuid.UUID, credential_id: uuid.UUID | None, model: str | None) -> None:
    """Background job: read the document, extract, validate, and hand over for review."""
    extraction = db.get(Extraction, extraction_id)
    document = db.get(Document, extraction.document_id) if extraction else None
    schema = get_schema(extraction.schema_key) if extraction else None
    if extraction is None or document is None or schema is None:
        return
    org_id = organization_id(db, document)
    try:
        # Raw text, not the stored chunks: ingestion joins lines, but the rules rely on line structure.
        pages = extract(Path(document.storage_path).read_bytes(), document.mime_type or "")
        text = "\n".join(page.text for page in pages)
        llm, note = None, None
        credential = db.get(ProviderCredential, credential_id) if credential_id else None
        if credential is not None and credential.organization_id == org_id and model:
            llm = build_provider_for_credential(credential)
        try:
            extraction.values = extract_values(schema, text, llm, model or "")
            extraction.model = model if llm else None
        except LLMError as exc:
            note = f"The model could not be used ({exc}); only the rule-based reader ran"
            extraction.values = extract_values(schema, text)
        refresh_issues(db, extraction, schema, org_id)
        extraction.status, extraction.error_message = ExtractionStatus.NEEDS_REVIEW, note
    except (ExtractionError, OSError) as exc:
        extraction.status, extraction.error_message = ExtractionStatus.FAILED, str(exc)[:2000]
    except Exception:
        log.exception("Extraction %s crashed", extraction_id)
        db.rollback()
        extraction = db.get(Extraction, extraction_id)
        if extraction is None:
            return
        extraction.status, extraction.error_message = ExtractionStatus.FAILED, "Extraction crashed unexpectedly"
    try:
        db.commit()
    except (StaleDataError, IntegrityError):  # the document was deleted while this ran
        db.rollback()


def update_values(db: Session, extraction: Extraction, document: Document, patch: dict) -> None:
    """Reviewer corrections. An approved extraction goes back to review once edited."""
    _require_reviewable(extraction)
    schema = get_schema(extraction.schema_key)
    extraction.values = clean_values(schema, {**extraction.values, **patch})
    extraction.status = ExtractionStatus.NEEDS_REVIEW
    extraction.reviewed_by = extraction.reviewed_at = None
    refresh_issues(db, extraction, schema, organization_id(db, document))
    db.commit()


def approve(db: Session, extraction: Extraction, user: User) -> None:
    _require_reviewable(extraction)
    errors = [i for i in extraction.issues if i["severity"] == "error"]
    if errors:
        raise ExtractionStateError(f"Fix {len(errors)} problem(s) before approving: {errors[0]['message']}")
    extraction.status = ExtractionStatus.APPROVED
    extraction.reviewed_by, extraction.reviewed_at = user.id, datetime.now(UTC)
    db.commit()


def _require_reviewable(extraction: Extraction) -> None:
    if extraction.status not in (ExtractionStatus.NEEDS_REVIEW, ExtractionStatus.APPROVED):
        raise ExtractionStateError(f"Extraction is {extraction.status}; wait for it to finish or run it again")
