import uuid
from dataclasses import asdict

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, WorkspaceDep, require_manager
from app.core.config import get_settings
from app.models import Conversation, Document, ProviderCredential
from app.rag.embeddings import get_embedding_provider
from app.rag.retriever import retrieve
from app.schemas.chat import ConversationCreate, ConversationRead
from app.schemas.document import DocumentRead, DocumentUploadResponse
from app.schemas.organization import WorkspaceRead
from app.schemas.search import SearchRequest, SearchResponse, SearchResult
from app.services.document_service import UploadError, create_document, validate_upload
from app.services.organization_service import delete_workspace
from app.tasks.ingestion_tasks import ingest_document_task

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


def ensure_documents_in_workspace(db, workspace_id: uuid.UUID, document_ids: list[uuid.UUID]) -> None:
    """Never trust client-supplied IDs: every requested document must belong to this workspace."""
    if not document_ids:
        return
    found = set(
        db.scalars(select(Document.id).where(Document.workspace_id == workspace_id, Document.id.in_(document_ids)))
    )
    if missing := [str(d) for d in document_ids if d not in found]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Documents not found in this workspace: {missing}")


@router.get("/{workspace_id}", response_model=WorkspaceRead)
def get_workspace(access: WorkspaceDep):
    return access.workspace


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_workspace(access: WorkspaceDep, db: DbSession):
    """Deletes the workspace with all its documents, chunks, conversations and stored files."""
    require_manager(access.membership)
    delete_workspace(db, access.workspace)


# ---------------------------------------------------------------- documents


@router.post("/{workspace_id}/documents", status_code=status.HTTP_202_ACCEPTED, response_model=DocumentUploadResponse)
def upload_document(
    access: WorkspaceDep, user: CurrentUser, file: UploadFile, background_tasks: BackgroundTasks, db: DbSession
):
    try:
        validated = validate_upload(file.filename, file.file)
    except UploadError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc

    document = create_document(db, validated, access.workspace.id, user.id)
    background_tasks.add_task(ingest_document_task, document.id)
    return DocumentUploadResponse(
        document_id=document.id,
        filename=document.filename,
        status=document.status,
        message="Document uploaded successfully",
    )


@router.get("/{workspace_id}/documents", response_model=list[DocumentRead])
def list_documents(access: WorkspaceDep, db: DbSession):
    return db.scalars(
        select(Document).where(Document.workspace_id == access.workspace.id).order_by(Document.created_at.desc())
    ).all()


# ---------------------------------------------------------------- search


@router.post("/{workspace_id}/search", response_model=SearchResponse)
def semantic_search(access: WorkspaceDep, request: SearchRequest, db: DbSession):
    ensure_documents_in_workspace(db, access.workspace.id, request.document_ids)
    query = request.query.strip()
    results = retrieve(
        db,
        get_embedding_provider(),
        query,
        top_k=request.top_k or get_settings().retrieval_top_k,
        workspace_id=access.workspace.id,
        document_ids=request.document_ids or None,
        min_score=request.min_score,
    )
    return SearchResponse(query=query, results=[SearchResult(**asdict(r)) for r in results])


# ---------------------------------------------------------------- conversations


@router.post("/{workspace_id}/conversations", status_code=status.HTTP_201_CREATED, response_model=ConversationRead)
def create_conversation(access: WorkspaceDep, user: CurrentUser, data: ConversationCreate, db: DbSession):
    credential = db.get(ProviderCredential, data.provider_id)
    # Provider keys are per organization: a workspace can only use its own organization's keys.
    if credential is None or credential.organization_id != access.workspace.organization_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Provider not found")
    ensure_documents_in_workspace(db, access.workspace.id, data.document_ids)
    conversation = Conversation(
        workspace_id=access.workspace.id,
        user_id=user.id,
        title=data.title,
        provider_credential_id=credential.id,
        model=data.model or credential.default_model,
        document_ids=data.document_ids,
    )
    db.add(conversation)
    db.commit()
    return conversation


@router.get("/{workspace_id}/conversations", response_model=list[ConversationRead])
def list_conversations(access: WorkspaceDep, user: CurrentUser, db: DbSession):
    """Your own conversations in this workspace (chat history is private)."""
    return db.scalars(
        select(Conversation)
        .where(Conversation.workspace_id == access.workspace.id, Conversation.user_id == user.id)
        .order_by(Conversation.created_at.desc())
    ).all()
