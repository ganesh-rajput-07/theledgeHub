"""Desktop login: ask the licence server, verify its lease, and mirror the firm and user locally."""

import secrets
from dataclasses import dataclass

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.licensing import lease as leases
from app.licensing.machine import machine_id, machine_name
from app.models import Membership, Organization, Role, User
from app.services.organization_service import create_organization

UNREACHABLE = "Can't reach the licence server. Check your internet connection and try again."


class LicenceError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def desktop_mode() -> bool:
    return get_settings().licence_mode == "desktop"


def request_lease(email: str, password: str) -> str:
    """POST to the licence server; returns the signed lease or raises LicenceError with a user-ready message."""
    settings = get_settings()
    payload = {
        "email": email,
        "password": password,
        "machine_id": machine_id(),
        "machine_name": machine_name(),
        "app_version": settings.app_version,
    }
    try:
        response = httpx.post(
            f"{settings.licence_server_url.rstrip('/')}/api/app/v1/login",
            json=payload,
            timeout=settings.licence_timeout_seconds,
        )
    except httpx.HTTPError:
        raise LicenceError(503, "server_unreachable", UNREACHABLE) from None
    try:
        body = response.json()
    except ValueError:
        raise LicenceError(
            502, "bad_response", "The licence server sent an unexpected reply. Try again later."
        ) from None
    if response.status_code != 200:
        status = response.status_code if 400 <= response.status_code < 600 else 502
        raise LicenceError(status, str(body.get("code", "refused")), str(body.get("message", "Login refused.")))
    if not isinstance(body.get("lease"), str):
        raise LicenceError(502, "bad_response", "The licence server sent an unexpected reply. Try again later.")
    return body["lease"]


ROLE_MAP = {"owner": Role.OWNER, "admin": Role.ADMIN, "member": Role.MEMBER}


def sync_local_account(db: Session, claims: dict) -> User:
    """The licence server is the source of truth for who belongs to which firm; mirror it locally."""
    info, firm = claims["user"], claims["firm"]
    email = str(info["email"]).strip().lower()
    role = ROLE_MAP.get(str(info.get("role")), Role.MEMBER)

    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if user is None:
        # Passwords are checked online; the local hash is random so the local password login can't be used.
        user = User(email=email, password_hash=hash_password(secrets.token_urlsafe(32)))
        db.add(user)
        db.flush()
    user.full_name, user.is_active = info.get("name") or user.full_name, True

    organization = db.scalar(select(Organization).where(Organization.licence_firm_id == str(firm["id"])))
    if organization is None:
        organization = create_organization(db, user, firm["name"], commit=False)
        organization.licence_firm_id = str(firm["id"])
    organization.name = firm["name"]
    membership = db.scalar(
        select(Membership).where(Membership.user_id == user.id, Membership.organization_id == organization.id)
    )
    if membership is None:
        db.add(Membership(user_id=user.id, organization_id=organization.id, role=role))
    else:
        membership.role = role
    db.commit()
    return user


@dataclass
class DesktopLogin:
    user: User
    lease: leases.Lease


def login(db: Session, email: str, password: str) -> DesktopLogin:
    token = request_lease(email, password)
    try:
        claims = leases.verify(token, machine_id())
    except leases.LeaseInvalid as error:
        raise LicenceError(403, "lease_invalid", f"{error}. Please contact support.") from error
    lease = leases.store(claims)
    return DesktopLogin(sync_local_account(db, claims), lease)
