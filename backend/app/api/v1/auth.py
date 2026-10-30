from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models import Membership, Organization
from app.schemas.auth import (
    LoginRequest,
    MembershipSummary,
    MeResponse,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserRead,
)
from app.services import auth_service
from app.services.auth_service import AuthError, EmailTakenError

router = APIRouter(prefix="/auth", tags=["auth"])


def _unauthorized(exc: Exception) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc), headers={"WWW-Authenticate": "Bearer"})


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserRead)
def register(data: RegisterRequest, db: DbSession):
    try:
        return auth_service.register(db, data.email, data.password, data.full_name, data.organization_name)
    except EmailTakenError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: DbSession):
    try:
        user = auth_service.authenticate(db, data.email, data.password)
    except AuthError as exc:
        raise _unauthorized(exc) from exc
    return auth_service.issue_tokens(db, user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(data: RefreshRequest, db: DbSession):
    try:
        return auth_service.refresh(db, data.refresh_token)
    except AuthError as exc:
        raise _unauthorized(exc) from exc


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(data: RefreshRequest, db: DbSession):
    """Revokes the refresh token. Access tokens are short-lived and simply expire."""
    try:
        auth_service.logout(db, data.refresh_token)
    except AuthError as exc:
        raise _unauthorized(exc) from exc


@router.get("/me", response_model=MeResponse)
def me(user: CurrentUser, db: DbSession):
    rows = db.execute(
        select(Membership.role, Organization.id, Organization.name)
        .join(Organization, Organization.id == Membership.organization_id)
        .where(Membership.user_id == user.id)
        .order_by(Organization.created_at)
    ).all()
    return MeResponse(
        **UserRead.model_validate(user).model_dump(),
        organizations=[MembershipSummary(organization_id=i, organization_name=n, role=r) for r, i, n in rows],
    )
