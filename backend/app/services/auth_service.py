from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import (
    ACCESS,
    REFRESH,
    TokenError,
    create_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models import AuthSession, User
from app.services.organization_service import create_organization


class AuthError(Exception):
    pass


class EmailTakenError(Exception):
    pass


def normalize_email(email: str) -> str:
    return email.strip().lower()


def register(db: Session, email: str, password: str, full_name: str | None, organization_name: str | None) -> User:
    email = normalize_email(email)
    if db.scalar(select(User.id).where(func.lower(User.email) == email)):
        raise EmailTakenError("An account with this email already exists")
    user = User(email=email, password_hash=hash_password(password), full_name=full_name)
    db.add(user)
    db.flush()
    if organization_name:
        create_organization(db, user, organization_name, commit=False)
    db.commit()
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(func.lower(User.email) == normalize_email(email)))
    # Same error and same (hashing) cost whether the email exists or not.
    if not verify_password(password, user.password_hash if user else None) or not user.is_active:
        raise AuthError("Incorrect email or password")
    return user


def issue_tokens(db: Session, user: User) -> dict:
    access, access_claims = create_token(user.id, ACCESS)
    refresh, refresh_claims = create_token(user.id, REFRESH)
    db.add(AuthSession(id=refresh_claims.jti, user_id=user.id, expires_at=refresh_claims.expires_at))
    db.commit()
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "expires_in": int((access_claims.expires_at - datetime.now(UTC)).total_seconds()),
    }


def _active_session(db: Session, refresh_token: str) -> AuthSession:
    try:
        claims = decode_token(refresh_token, REFRESH)
    except TokenError as exc:
        raise AuthError(str(exc)) from exc
    session = db.get(AuthSession, claims.jti)
    if session is None or session.revoked_at is not None or session.user_id != claims.user_id:
        raise AuthError("Refresh token has been revoked")
    return session


def refresh(db: Session, refresh_token: str) -> dict:
    """Rotation: the used refresh token is revoked and a new pair is issued, so a stolen
    refresh token stops working as soon as the real user refreshes."""
    session = _active_session(db, refresh_token)
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise AuthError("Account is disabled")
    session.revoked_at = datetime.now(UTC)
    return issue_tokens(db, user)


def logout(db: Session, refresh_token: str) -> None:
    session = _active_session(db, refresh_token)
    session.revoked_at = datetime.now(UTC)
    db.commit()
