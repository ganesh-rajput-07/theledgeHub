from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import ClientIP, CurrentUser, DbSession
from app.core.config import get_settings
from app.core.rate_limit import limiter
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
from app.services import audit_service, auth_service
from app.services.auth_service import AuthError, EmailTakenError

router = APIRouter(prefix="/auth", tags=["auth"])


def _unauthorized(exc: Exception) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc), headers={"WWW-Authenticate": "Bearer"})


def _enforce(db: DbSession, key: str, limit: int) -> None:
    wait = limiter.retry_after(db, key, limit, get_settings().rate_limit_window_seconds)
    if wait:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Too many attempts. Try again in {wait // 60 + 1} minute(s).",
            headers={"Retry-After": str(wait)},
        )


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserRead)
def register(data: RegisterRequest, db: DbSession, ip: ClientIP):
    window = get_settings().rate_limit_window_seconds
    _enforce(db, f"register:ip:{ip}", get_settings().register_ip_max_attempts)
    limiter.hit(db, f"register:ip:{ip}", window)
    try:
        user = auth_service.register(db, data.email, data.password, data.full_name, data.organization_name)
    except EmailTakenError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    audit_service.record(db, "auth.register", user=user, ip=ip)
    return user


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: DbSession, ip: ClientIP):
    """Locks an account after LOGIN_MAX_FAILURES failed attempts and an IP after LOGIN_IP_MAX_ATTEMPTS
    attempts, both per RATE_LIMIT_WINDOW_SECONDS."""
    settings = get_settings()
    email_key, ip_key = f"login:email:{auth_service.normalize_email(data.email)}", f"login:ip:{ip}"
    window = settings.rate_limit_window_seconds
    _enforce(db, email_key, settings.login_max_failures)
    _enforce(db, ip_key, settings.login_ip_max_attempts)
    limiter.hit(db, ip_key, window)
    try:
        user = auth_service.authenticate(db, data.email, data.password)
    except AuthError as exc:
        limiter.hit(db, email_key, window)
        audit_service.record(db, "auth.login_failed", email=auth_service.normalize_email(data.email), ip=ip)
        raise _unauthorized(exc) from exc
    limiter.reset(db, email_key)
    audit_service.record(db, "auth.login", user=user, ip=ip)
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
