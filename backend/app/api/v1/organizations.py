import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import ClientIP, CurrentUser, DbSession, OrgDep, OrgManagerDep
from app.api.errors import llm_http_error
from app.llm.base import LLMError
from app.models import AuditLog, Membership, Organization, ProviderCredential, User, Workspace
from app.schemas.organization import (
    AuditLogRead,
    MemberAdd,
    MemberRead,
    OrganizationCreate,
    OrganizationRead,
    WorkspaceCreate,
    WorkspaceRead,
)
from app.schemas.provider import ProviderCreate, ProviderRead
from app.services import audit_service
from app.services.organization_service import MemberError, add_member, create_organization, remove_member
from app.services.provider_service import ProviderConfigError, create_credential

router = APIRouter(prefix="/organizations", tags=["organizations"])


def _org(organization: Organization, role: str) -> OrganizationRead:
    return OrganizationRead(
        id=organization.id,
        name=organization.name,
        slug=organization.slug,
        role=role,
        created_at=organization.created_at,
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=OrganizationRead)
def create_org(data: OrganizationCreate, user: CurrentUser, db: DbSession, ip: ClientIP):
    organization = create_organization(db, user, data.name)
    audit_service.record(db, "organization.create", user=user, organization_id=organization.id, ip=ip)
    return _org(organization, "owner")


@router.get("", response_model=list[OrganizationRead])
def list_my_orgs(user: CurrentUser, db: DbSession):
    rows = db.execute(
        select(Organization, Membership.role)
        .join(Membership, Membership.organization_id == Organization.id)
        .where(Membership.user_id == user.id)
        .order_by(Organization.created_at)
    ).all()
    return [_org(org, role) for org, role in rows]


@router.get("/{organization_id}", response_model=OrganizationRead)
def get_org(access: OrgDep):
    return _org(access.organization, access.membership.role)


# ---------------------------------------------------------------- members


@router.get("/{organization_id}/members", response_model=list[MemberRead])
def list_members(access: OrgDep, db: DbSession):
    rows = db.execute(
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.organization_id == access.organization.id)
        .order_by(Membership.created_at)
    ).all()
    return [
        MemberRead(user_id=u.id, email=u.email, full_name=u.full_name, role=m.role, created_at=m.created_at)
        for m, u in rows
    ]


@router.post("/{organization_id}/members", status_code=status.HTTP_201_CREATED, response_model=MemberRead)
def add_org_member(data: MemberAdd, access: OrgManagerDep, user: CurrentUser, db: DbSession, ip: ClientIP):
    try:
        membership = add_member(db, access.organization, data.email, data.role, access.membership.role)
    except MemberError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    audit_service.record(
        db,
        "member.add",
        user=user,
        organization_id=access.organization.id,
        target_type="user",
        target_id=membership.user_id,
        ip=ip,
        role=membership.role,
    )
    user = membership.user
    return MemberRead(
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=membership.role,
        created_at=membership.created_at,
    )


@router.delete("/{organization_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_org_member(user_id: uuid.UUID, access: OrgManagerDep, user: CurrentUser, db: DbSession, ip: ClientIP):
    try:
        remove_member(db, access.organization, user_id, access.membership.role)
    except MemberError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    audit_service.record(
        db,
        "member.remove",
        user=user,
        organization_id=access.organization.id,
        target_type="user",
        target_id=user_id,
        ip=ip,
    )


# ---------------------------------------------------------------- workspaces


@router.get("/{organization_id}/workspaces", response_model=list[WorkspaceRead])
def list_workspaces(access: OrgDep, db: DbSession):
    return db.scalars(
        select(Workspace).where(Workspace.organization_id == access.organization.id).order_by(Workspace.created_at)
    ).all()


@router.post("/{organization_id}/workspaces", status_code=status.HTTP_201_CREATED, response_model=WorkspaceRead)
def create_workspace(data: WorkspaceCreate, access: OrgManagerDep, user: CurrentUser, db: DbSession, ip: ClientIP):
    workspace = Workspace(organization_id=access.organization.id, name=data.name, description=data.description)
    db.add(workspace)
    db.commit()
    audit_service.record(
        db,
        "workspace.create",
        user=user,
        organization_id=access.organization.id,
        target_type="workspace",
        target_id=workspace.id,
        ip=ip,
        name=workspace.name,
    )
    return workspace


# ---------------------------------------------------------------- provider keys (BYOK, shared by the org)


@router.get("/{organization_id}/providers", response_model=list[ProviderRead])
def list_providers(access: OrgDep, db: DbSession):
    return db.scalars(
        select(ProviderCredential)
        .where(ProviderCredential.organization_id == access.organization.id)
        .order_by(ProviderCredential.created_at)
    ).all()


@router.post("/{organization_id}/providers", status_code=status.HTTP_201_CREATED, response_model=ProviderRead)
def add_provider(data: ProviderCreate, access: OrgManagerDep, user: CurrentUser, db: DbSession, ip: ClientIP):
    """Validates the key with the provider before storing it encrypted. Owners/admins only."""
    try:
        credential = create_credential(db, access.organization.id, data)
    except ProviderConfigError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except LLMError as exc:
        raise llm_http_error(exc) from exc
    audit_service.record(
        db,
        "provider.create",
        user=user,
        organization_id=access.organization.id,
        target_type="provider",
        target_id=credential.id,
        ip=ip,
        provider=credential.provider,
        label=credential.label,
    )
    return credential


# ---------------------------------------------------------------- audit trail


@router.get("/{organization_id}/audit-logs", response_model=list[AuditLogRead])
def list_audit_logs(
    access: OrgManagerDep,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    action: Annotated[str | None, Query(max_length=60, description="e.g. document.delete")] = None,
):
    """Most recent first. Owners/admins only."""
    query = select(AuditLog).where(AuditLog.organization_id == access.organization.id)
    if action:
        query = query.where(AuditLog.action == action)
    return db.scalars(query.order_by(AuditLog.created_at.desc()).limit(limit)).all()
