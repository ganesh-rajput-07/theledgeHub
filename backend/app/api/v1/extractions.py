import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Response, status
from sqlalchemy import select

from app.api.deps import ClientIP, CurrentUser, DbSession, DocumentDep, WorkspaceDep, require_manager
from app.extraction.export import to_xlsx
from app.extraction.rules import CATALOG, OPERATORS_BY_TYPE, RuleConfig, RuleConfigError
from app.models import Document, Extraction, ExtractionStatus, ProviderCredential
from app.schemas.extraction import (
    ExtractionRead,
    ExtractionRequest,
    ExtractionUpdate,
    PredefinedRuleRead,
    RuleEditorRead,
    RuleFieldRead,
    RuleParamRead,
    SchemaRead,
)
from app.services import audit_service
from app.services import extraction_service as service
from app.tasks.extraction_tasks import run_extraction_task

router = APIRouter(tags=["extraction"])

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _read(extraction: Extraction) -> ExtractionRead:
    return ExtractionRead.model_validate(extraction)


def _existing(db: DbSession, document: Document) -> Extraction:
    extraction = db.scalar(select(Extraction).where(Extraction.document_id == document.id))
    if extraction is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No extraction for this document yet")
    return extraction


@router.get("/extraction-schemas", response_model=list[SchemaRead])
def list_schemas(_user: CurrentUser):
    return [
        SchemaRead(key=s.key, name=s.name, fields=[{**f.__dict__} for f in s.fields]) for s in service.SCHEMAS.values()
    ]


@router.post("/documents/{document_id}/extraction", status_code=status.HTTP_202_ACCEPTED, response_model=ExtractionRead)
def start_extraction(
    document: DocumentDep, request: ExtractionRequest, background_tasks: BackgroundTasks, db: DbSession
):
    if service.get_schema(request.schema_key) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Unknown document type '{request.schema_key}'")
    if request.provider_id is not None:
        credential = db.get(ProviderCredential, request.provider_id)
        if (
            credential is None
            or credential.organization_id != service.organization_id(db, document)
            or not credential.is_active
        ):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Provider not found")
    try:
        extraction = service.start(db, document, request.schema_key)
    except service.ExtractionBusyError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    background_tasks.add_task(run_extraction_task, extraction.id, request.provider_id, request.model)
    return _read(extraction)


@router.get("/documents/{document_id}/extraction", response_model=ExtractionRead)
def get_extraction(document: DocumentDep, db: DbSession):
    return _read(_existing(db, document))


@router.patch("/documents/{document_id}/extraction", response_model=ExtractionRead)
def correct_extraction(document: DocumentDep, update: ExtractionUpdate, user: CurrentUser, db: DbSession, ip: ClientIP):
    extraction = _existing(db, document)
    before = dict(extraction.values)
    try:
        service.update_values(db, extraction, document, update.values)
    except service.ExtractionStateError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    # Who changed which figure is the part of the trail accountants and auditors care most about.
    changes = {
        key: {"from": before.get(key), "to": value}
        for key, value in extraction.values.items()
        if before.get(key) != value
    }
    if changes:
        audit_service.record(
            db,
            "extraction.update",
            user=user,
            organization_id=service.organization_id(db, document),
            target_type="document",
            target_id=document.id,
            ip=ip,
            filename=document.filename,
            changes=changes,
        )
    return _read(extraction)


@router.post("/documents/{document_id}/extraction/approve", response_model=ExtractionRead)
def approve_extraction(document: DocumentDep, user: CurrentUser, db: DbSession, ip: ClientIP):
    extraction = _existing(db, document)
    try:
        service.approve(db, extraction, user)
    except service.ExtractionStateError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    audit_service.record(
        db,
        "extraction.approve",
        user=user,
        organization_id=service.organization_id(db, document),
        target_type="document",
        target_id=document.id,
        ip=ip,
        filename=document.filename,
    )
    return _read(extraction)


def _workspace_extractions(db: DbSession, workspace_id: uuid.UUID, status_filter: str | None, schema_key: str | None):
    query = (
        select(Extraction)
        .join(Document, Document.id == Extraction.document_id)
        .where(Document.workspace_id == workspace_id)
        .order_by(Extraction.updated_at.desc())
    )
    if status_filter:
        query = query.where(Extraction.status == status_filter)
    if schema_key:
        query = query.where(Extraction.schema_key == schema_key)
    return db.scalars(query).all()


@router.get("/workspaces/{workspace_id}/extractions", response_model=list[ExtractionRead])
def list_extractions(
    access: WorkspaceDep,
    db: DbSession,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    schema_key: str | None = None,
):
    return [_read(e) for e in _workspace_extractions(db, access.workspace.id, status_filter, schema_key)]


@router.get("/workspaces/{workspace_id}/extractions/export")
def export_extractions(
    access: WorkspaceDep, user: CurrentUser, db: DbSession, ip: ClientIP, schema_key: str = "invoice"
):
    """Approved records only, as an Excel file."""
    schema = service.get_schema(schema_key)
    if schema is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Unknown document type '{schema_key}'")
    rows = _workspace_extractions(db, access.workspace.id, ExtractionStatus.APPROVED, schema_key)
    data = to_xlsx(
        schema,
        [(e.document.filename, e.values, e.reviewed_at.date() if e.reviewed_at else None) for e in reversed(rows)],
    )
    audit_service.record(
        db,
        "extraction.export",
        user=user,
        organization_id=access.workspace.organization_id,
        target_type="workspace",
        target_id=access.workspace.id,
        ip=ip,
        schema_key=schema_key,
        rows=len(rows),
    )
    name = f"{schema_key}-{datetime.now(UTC):%Y%m%d}.xlsx"
    return Response(
        data,
        media_type=XLSX,
        headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "private, no-store"},
    )


# ---------------------------------------------------------------- validation rules (per workspace)


def _schema_or_422(schema_key: str):
    schema = service.get_schema(schema_key)
    if schema is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Unknown document type '{schema_key}'")
    return schema


def _rule_editor(schema, config: RuleConfig, rechecked: int | None = None) -> RuleEditorRead:
    return RuleEditorRead(
        schema_key=schema.key,
        fields=[RuleFieldRead(key=f.key, label=f.label, type=f.type) for f in schema.fields],
        operators=OPERATORS_BY_TYPE,
        predefined=[
            PredefinedRuleRead(
                key=rule.key,
                label=rule.label,
                description=rule.description,
                params=[RuleParamRead(key=p.key, label=p.label, type=p.type, required=p.required) for p in rule.params],
                default_enabled=rule.enabled,
                default_severity=rule.severity,
            )
            for rule in CATALOG.get(schema.key, ())
        ],
        config=config,
        rechecked=rechecked,
    )


@router.get("/workspaces/{workspace_id}/extraction-rules", response_model=RuleEditorRead)
def get_rules(access: WorkspaceDep, db: DbSession, schema_key: str = "invoice"):
    schema = _schema_or_422(schema_key)
    return _rule_editor(schema, service.rule_config(db, access.workspace.id, schema.key))


@router.put("/workspaces/{workspace_id}/extraction-rules", response_model=RuleEditorRead)
def save_rules(
    config: RuleConfig,
    access: WorkspaceDep,
    user: CurrentUser,
    db: DbSession,
    ip: ClientIP,
    schema_key: str = "invoice",
):
    """Owners/admins only: rules decide what blocks approval. Re-checks invoices still awaiting review."""
    require_manager(access.membership)
    schema = _schema_or_422(schema_key)
    try:
        rechecked = service.save_rule_config(db, access.workspace, schema, config, user)
    except RuleConfigError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    saved = service.rule_config(db, access.workspace.id, schema.key)
    audit_service.record(
        db,
        "extraction_rules.update",
        user=user,
        organization_id=access.workspace.organization_id,
        target_type="workspace",
        target_id=access.workspace.id,
        ip=ip,
        workspace=access.workspace.name,
        schema_key=schema.key,
        enabled=sorted(key for key, setting in saved.builtin.items() if setting.enabled),
        custom_rules=len(saved.custom),
        rechecked=rechecked,
    )
    return _rule_editor(schema, saved, rechecked)
