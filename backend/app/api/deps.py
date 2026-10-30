"""Authentication and tenant isolation.

Every route resolves its resources through these dependencies, so the access rule lives in one place:
a resource is visible only through an organization the current user belongs to. Anything else is a
404 (not 403), so one tenant cannot even confirm that another tenant's IDs exist.
"""

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.rate_limit import client_ip
from app.core.security import ACCESS, TokenError, decode_token
from app.database.session import get_db
from app.models import (
    MANAGER_ROLES,
    Conversation,
    Document,
    Membership,
    Message,
    Organization,
    ProviderCredential,
    User,
    Workspace,
)

DbSession = Annotated[Session, Depends(get_db)]


def get_client_ip(request: Request) -> str:
    return client_ip(request)


ClientIP = Annotated[str, Depends(get_client_ip)]

_bearer = HTTPBearer(auto_error=False, description="Access token from /api/v1/auth/login")


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"})


def get_current_user(
    db: DbSession, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]
) -> User:
    if credentials is None:
        raise _unauthorized("Not authenticated")
    try:
        claims = decode_token(credentials.credentials, ACCESS)
    except TokenError as exc:
        raise _unauthorized(str(exc)) from exc
    user = db.get(User, claims.user_id)
    if user is None or not user.is_active:
        raise _unauthorized("Account not found or disabled")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def _not_found(what: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"{what} not found")


def membership_for(db: Session, user: User, organization_id: uuid.UUID) -> Membership | None:
    return db.scalar(
        select(Membership).where(Membership.user_id == user.id, Membership.organization_id == organization_id)
    )


def require_manager(membership: Membership) -> None:
    if membership.role not in MANAGER_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Requires the owner or admin role")


# ---------------------------------------------------------------- organizations


class OrgAccess:
    def __init__(self, organization: Organization, membership: Membership):
        self.organization, self.membership = organization, membership


def get_org_access(organization_id: uuid.UUID, db: DbSession, user: CurrentUser) -> OrgAccess:
    membership = membership_for(db, user, organization_id)
    if membership is None:
        raise _not_found("Organization")
    return OrgAccess(db.get(Organization, organization_id), membership)


def get_org_manager_access(access: Annotated[OrgAccess, Depends(get_org_access)]) -> OrgAccess:
    require_manager(access.membership)
    return access


OrgDep = Annotated[OrgAccess, Depends(get_org_access)]
OrgManagerDep = Annotated[OrgAccess, Depends(get_org_manager_access)]


# ---------------------------------------------------------------- workspaces


class WorkspaceAccess:
    def __init__(self, workspace: Workspace, membership: Membership):
        self.workspace, self.membership = workspace, membership


def _workspace_access(db: Session, user: User, workspace_id: uuid.UUID) -> WorkspaceAccess:
    workspace = db.get(Workspace, workspace_id)
    membership = membership_for(db, user, workspace.organization_id) if workspace else None
    if membership is None:
        raise _not_found("Workspace")
    return WorkspaceAccess(workspace, membership)


def get_workspace_access(workspace_id: uuid.UUID, db: DbSession, user: CurrentUser) -> WorkspaceAccess:
    return _workspace_access(db, user, workspace_id)


WorkspaceDep = Annotated[WorkspaceAccess, Depends(get_workspace_access)]


# ---------------------------------------------------------------- documents


def get_document(document_id: uuid.UUID, db: DbSession, user: CurrentUser) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise _not_found("Document")
    try:
        _workspace_access(db, user, document.workspace_id)
    except HTTPException:
        raise _not_found("Document") from None
    return document


DocumentDep = Annotated[Document, Depends(get_document)]


# ---------------------------------------------------------------- provider keys


class ProviderAccess:
    def __init__(self, credential: ProviderCredential, membership: Membership):
        self.credential, self.membership = credential, membership


def get_provider_access(provider_id: uuid.UUID, db: DbSession, user: CurrentUser) -> ProviderAccess:
    credential = db.get(ProviderCredential, provider_id)
    membership = membership_for(db, user, credential.organization_id) if credential else None
    if membership is None:
        raise _not_found("Provider")
    return ProviderAccess(credential, membership)


def get_provider_manager_access(access: Annotated[ProviderAccess, Depends(get_provider_access)]) -> ProviderAccess:
    require_manager(access.membership)
    return access


ProviderDep = Annotated[ProviderAccess, Depends(get_provider_access)]
ProviderManagerDep = Annotated[ProviderAccess, Depends(get_provider_manager_access)]


# ---------------------------------------------------------------- conversations (private to their creator)


def get_conversation(conversation_id: uuid.UUID, db: DbSession, user: CurrentUser) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != user.id:
        raise _not_found("Conversation")
    # Removed from the organization = no access to old conversations either.
    try:
        _workspace_access(db, user, conversation.workspace_id)
    except HTTPException:
        raise _not_found("Conversation") from None
    return conversation


def get_message(message_id: uuid.UUID, db: DbSession, user: CurrentUser) -> Message:
    message = db.get(Message, message_id)
    if message is None:
        raise _not_found("Message")
    try:
        get_conversation(message.conversation_id, db, user)
    except HTTPException:
        raise _not_found("Message") from None
    return message


ConversationDep = Annotated[Conversation, Depends(get_conversation)]
MessageDep = Annotated[Message, Depends(get_message)]
