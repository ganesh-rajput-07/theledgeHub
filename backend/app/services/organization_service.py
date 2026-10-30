import re
import uuid
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Document, Membership, Organization, Role, User, Workspace

DEFAULT_WORKSPACE = "General"


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60] or "org"
    return f"{slug}-{uuid.uuid4().hex[:6]}"


def create_organization(db: Session, owner: User, name: str, commit: bool = True) -> Organization:
    """Creates the organization, makes the creator its owner, and adds a default workspace."""
    organization = Organization(name=name, slug=_slugify(name))
    db.add(organization)
    db.flush()
    db.add(Membership(user_id=owner.id, organization_id=organization.id, role=Role.OWNER))
    db.add(Workspace(organization_id=organization.id, name=DEFAULT_WORKSPACE))
    if commit:
        db.commit()
    return organization


class MemberError(Exception):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.message, self.status_code = message, status_code


def add_member(db: Session, organization: Organization, email: str, role: Role, actor_role: str) -> Membership:
    """Adds an existing user. (Email invitations for people without an account come later.)"""
    if role == Role.OWNER and actor_role != Role.OWNER:
        raise MemberError("Only an owner can add another owner", 403)
    user = db.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))
    if user is None:
        raise MemberError("No account with this email - ask them to register first", 404)
    existing = db.scalar(
        select(Membership).where(Membership.organization_id == organization.id, Membership.user_id == user.id)
    )
    if existing:
        raise MemberError("User is already a member", 409)
    membership = Membership(user_id=user.id, organization_id=organization.id, role=role)
    db.add(membership)
    db.commit()
    return membership


def delete_workspace(db: Session, workspace: Workspace) -> None:
    """Rows cascade in the database (documents, chunks, conversations); files are removed here."""
    paths = db.scalars(select(Document.storage_path).where(Document.workspace_id == workspace.id)).all()
    db.delete(workspace)
    db.commit()
    for path in paths:
        Path(path).unlink(missing_ok=True)


def remove_member(db: Session, organization: Organization, user_id: uuid.UUID, actor_role: str) -> None:
    membership = db.scalar(
        select(Membership).where(Membership.organization_id == organization.id, Membership.user_id == user_id)
    )
    if membership is None:
        raise MemberError("Member not found", 404)
    if membership.role == Role.OWNER:
        if actor_role != Role.OWNER:
            raise MemberError("Only an owner can remove an owner", 403)
        owners = db.scalar(
            select(func.count()).where(Membership.organization_id == organization.id, Membership.role == Role.OWNER)
        )
        if owners <= 1:
            raise MemberError("An organization must keep at least one owner", 409)
    db.delete(membership)
    db.commit()
