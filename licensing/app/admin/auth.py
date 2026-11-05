"""Admin sign-in: server-side sessions in httpOnly cookies, CSRF token per session, account lock-out."""

from dataclasses import dataclass
from datetime import timedelta

from fastapi import Depends, HTTPException, Request
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import AdminSession, AdminUser
from app.security import new_token, same, token_hash, verify_password
from app.services import audit, now

COOKIE = "kh_admin"


class LoginRequired(Exception):  # control flow: handled by redirecting to /login
    pass


@dataclass
class Ctx:
    admin: AdminUser
    session: AdminSession
    ip: str | None


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def authenticate(db: Session, email: str, password: str, ip: str | None) -> AdminUser | None:
    settings = get_settings()
    admin = db.scalar(select(AdminUser).where(func.lower(AdminUser.email) == email.strip().lower()))
    if admin and admin.locked_until and admin.locked_until > now():
        verify_password(password, None)
        return None
    if not verify_password(password, admin.password_hash if admin and admin.is_active else None):
        if admin:
            admin.failed_logins += 1
            if admin.failed_logins >= settings.login_max_failures:
                admin.failed_logins = 0
                admin.locked_until = now() + timedelta(minutes=settings.login_lock_minutes)
                audit(db, admin, "admin.locked", f"{admin.email} locked after repeated wrong passwords", ip=ip)
            db.commit()
        return None
    admin.failed_logins, admin.locked_until, admin.last_login_at = 0, None, now()
    audit(db, admin, "admin.login", f"{admin.email} signed in", ip=ip)
    db.commit()
    return admin


def start_session(db: Session, admin: AdminUser, ip: str | None) -> str:
    token = new_token()
    db.execute(delete(AdminSession).where(AdminSession.expires_at < now()))
    db.add(
        AdminSession(
            admin_id=admin.id,
            token_hash=token_hash(token),
            csrf_token=new_token(),
            ip=ip,
            expires_at=now() + timedelta(hours=get_settings().session_hours),
        )
    )
    db.commit()
    return token


def end_session(db: Session, token: str | None) -> None:
    if token:
        db.execute(delete(AdminSession).where(AdminSession.token_hash == token_hash(token)))
        db.commit()


def current(request: Request, db: Session = Depends(get_db)) -> Ctx:
    token = request.cookies.get(COOKIE)
    session = db.scalar(select(AdminSession).where(AdminSession.token_hash == token_hash(token))) if token else None
    if session is None or session.expires_at < now() or not session.admin.is_active:
        raise LoginRequired
    return Ctx(session.admin, session, client_ip(request))


async def checked(request: Request, ctx: Ctx = Depends(current)) -> Ctx:
    """For POST routes: the form must carry this session's CSRF token, and any Origin must be our own."""
    origin = request.headers.get("origin")
    if origin and origin != f"{request.url.scheme}://{request.url.netloc}":
        raise HTTPException(403, "Cross-site request refused")
    form = await request.form()
    if not same(form.get("csrf"), ctx.session.csrf_token):
        raise HTTPException(403, "Your form expired. Go back, reload the page and try again.")
    return ctx
