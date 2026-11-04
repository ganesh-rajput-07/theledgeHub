"""Page tools so users never have to leave the platform: merge, extract pages, split, rotate, thumbnails.
Every tool writes a new document (originals are never changed) and starts processing it like an upload."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Response, status

from app.api.deps import ClientIP, CurrentUser, DbSession, DocumentDep, WorkspaceDep
from app.documents import pdf_tools
from app.documents.pdf_tools import PdfToolError
from app.models import Document, Workspace
from app.schemas.document import (
    DocumentUploadResponse,
    ExtractPagesRequest,
    MergeRequest,
    PageInfo,
    RotateRequest,
    SplitRequest,
)
from app.services import document_tools_service as tools
from app.services.document_tools_service import ToolError

router = APIRouter(tags=["document tools"])


def _created(document: Document, message: str) -> DocumentUploadResponse:
    return DocumentUploadResponse(
        document_id=document.id, filename=document.filename, status=document.status, message=message
    )


def _run(action):
    try:
        return action()
    except ToolError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    except PdfToolError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc


@router.get("/documents/{document_id}/pages", response_model=PageInfo)
def page_info(document: DocumentDep):
    return PageInfo(document_id=document.id, page_count=_run(lambda: pdf_tools.page_count(tools.pdf_bytes(document))))


@router.get("/documents/{document_id}/pages/{page}/thumbnail", response_class=Response)
def page_thumbnail(document: DocumentDep, page: int, width: Annotated[int, Query(ge=60, le=600)] = 240):
    png = _run(lambda: pdf_tools.thumbnail(tools.pdf_bytes(document), page, width))
    return Response(png, media_type="image/png", headers={"Cache-Control": "private, max-age=300"})


@router.post(
    "/workspaces/{workspace_id}/documents/merge",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=DocumentUploadResponse,
)
def merge_documents(
    request: MergeRequest,
    access: WorkspaceDep,
    user: CurrentUser,
    background_tasks: BackgroundTasks,
    db: DbSession,
    ip: ClientIP,
):
    document = _run(
        lambda: tools.merge(db, background_tasks, access.workspace, user, ip, request.document_ids, request.filename)
    )
    return _created(document, f"Merged {len(request.document_ids)} documents")


@router.post(
    "/documents/{document_id}/extract-pages",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=DocumentUploadResponse,
)
def extract_pages(
    request: ExtractPagesRequest,
    document: DocumentDep,
    user: CurrentUser,
    background_tasks: BackgroundTasks,
    db: DbSession,
    ip: ClientIP,
):
    workspace = db.get(Workspace, document.workspace_id)
    created = _run(
        lambda: tools.extract_pages(
            db, background_tasks, workspace, user, ip, document, request.pages, request.filename
        )
    )
    return _created(created, f"Pages {request.pages} saved as a new document")


@router.post(
    "/documents/{document_id}/split", status_code=status.HTTP_202_ACCEPTED, response_model=list[DocumentUploadResponse]
)
def split_document(
    request: SplitRequest,
    document: DocumentDep,
    user: CurrentUser,
    background_tasks: BackgroundTasks,
    db: DbSession,
    ip: ClientIP,
):
    workspace = db.get(Workspace, document.workspace_id)
    parts = _run(lambda: tools.split(db, background_tasks, workspace, user, ip, document, request.ranges))
    return [_created(part, f"Part {i} of {len(parts)}") for i, part in enumerate(parts, start=1)]


@router.post(
    "/documents/{document_id}/rotate", status_code=status.HTTP_202_ACCEPTED, response_model=DocumentUploadResponse
)
def rotate_document(
    request: RotateRequest,
    document: DocumentDep,
    user: CurrentUser,
    background_tasks: BackgroundTasks,
    db: DbSession,
    ip: ClientIP,
):
    workspace = db.get(Workspace, document.workspace_id)
    created = _run(
        lambda: tools.rotate(db, background_tasks, workspace, user, ip, document, request.pages, request.degrees)
    )
    return _created(created, f"Rotated copy saved ({request.degrees}°)")
