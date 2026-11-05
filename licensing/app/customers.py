"""Customer-side rules: registration, sign-in, team, computers, 'I have paid' claims and the desktop-app login."""

import re
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import lease, money, services
from app.config import get_settings
from app.models import AuditEvent, Computer, CustomerUser, Firm, PaymentClaim, Plan
from app.security import MIN_PASSWORD_LENGTH, hash_password, verify_password
from app.services import RuleError, audit, now

ROLES = {"owner": "Owner", "admin": "Admin", "member": "Member"}


# ------------------------------------------------------------------ simple per-IP limiter (one process)


class Limiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        cutoff = time.monotonic() - window_seconds
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] < cutoff:
                hits.popleft()
            if len(hits) >= limit:
                return False
            hits.append(time.monotonic())
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = Limiter()


# ------------------------------------------------------------------ accounts


def _check_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise RuleError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")


def _email_taken(db: Session, email: str) -> bool:
    return bool(db.scalar(select(CustomerUser.id).where(func.lower(CustomerUser.email) == email.lower())))


def register(db: Session, data: dict, password: str, plan_code: str, ip: str | None) -> CustomerUser:
    if not data.get("name", "").strip():
        raise RuleError("Your name is required.")
    _check_password(password)
    plan = db.scalar(select(Plan).where(Plan.code == plan_code, Plan.is_active, Plan.is_public))
    if plan is None:
        raise RuleError("Choose a plan.")
    firm_data = services.clean_firm(
        {
            "name": data.get("firm_name", ""),
            "contact_name": data["name"],
            "email": data.get("email", ""),
            "mobile": data.get("mobile", ""),
            "city": data.get("city", ""),
            "gstin": data.get("gstin", ""),
            "notes": "",
        }
    )
    if not firm_data["mobile"]:
        raise RuleError("Mobile number is required, so we can confirm your payment.")
    if _email_taken(db, firm_data["email"]):
        raise RuleError("An account with this email already exists. Log in instead.")
    firm = services.create_firm(db, None, firm_data, ip)
    firm.requested_plan_id = plan.id
    user = CustomerUser(
        firm_id=firm.id,
        email=firm.email,
        name=data["name"].strip(),
        role="owner",
        password_hash=hash_password(password),
    )
    db.add(user)
    audit(db, None, "customer.register", f"{firm.name} registered on the website ({plan.name})", firm=firm, ip=ip)
    db.commit()
    return user


def authenticate(db: Session, email: str, password: str, ip: str | None, *, channel: str) -> CustomerUser | None:
    """Shared by the website and the desktop app: 5 wrong passwords lock the account for a while."""
    settings = get_settings()
    user = db.scalar(select(CustomerUser).where(func.lower(CustomerUser.email) == email.strip().lower()))
    if user and user.locked_until and user.locked_until > now():
        verify_password(password, None)
        return None
    if not verify_password(password, user.password_hash if user and user.is_active else None):
        if user:
            user.failed_logins += 1
            if user.failed_logins >= settings.login_max_failures:
                user.failed_logins = 0
                user.locked_until = now() + timedelta(minutes=settings.login_lock_minutes)
                audit(
                    db,
                    None,
                    "customer.locked",
                    f"{user.email} locked after repeated wrong passwords ({channel})",
                    firm=user.firm,
                    ip=ip,
                )
            db.commit()
        return None
    user.failed_logins, user.locked_until, user.last_login_at = 0, None, now()
    db.commit()
    return user


def is_locked(db: Session, email: str) -> bool:
    user = db.scalar(select(CustomerUser).where(func.lower(CustomerUser.email) == email.strip().lower()))
    return bool(user and user.locked_until and user.locked_until > now())


def change_password(db: Session, user: CustomerUser, current: str, new: str, confirm: str, ip: str | None) -> None:
    if not verify_password(current, user.password_hash):
        raise RuleError("Current password is wrong.")
    _check_password(new)
    if new != confirm:
        raise RuleError("The two new passwords don't match.")
    user.password_hash = hash_password(new)
    audit(db, None, "customer.password", f"{user.email} changed their password", firm=user.firm, ip=ip)
    db.commit()


# ------------------------------------------------------------------ team


def can_manage(user: CustomerUser) -> bool:
    return user.role in ("owner", "admin")


def team(db: Session, firm: Firm) -> list[CustomerUser]:
    return list(
        db.scalars(
            select(CustomerUser).where(CustomerUser.firm_id == firm.id).order_by(CustomerUser.created_at)
        ).unique()
    )


def add_member(
    db: Session,
    actor: CustomerUser | None,
    firm: Firm,
    *,
    name: str,
    email: str,
    role: str,
    password: str,
    ip: str | None,
    admin=None,
) -> CustomerUser:
    if actor is not None and not can_manage(actor):
        raise RuleError("Only the owner or an admin can add people.")
    allowed = {"admin", "member"} if actor is not None else {"owner", "admin", "member"}
    if role not in allowed:
        raise RuleError("Choose a role.")
    if not name.strip():
        raise RuleError("Name is required.")
    try:
        email = services._email.validate_python(email.strip()).lower()
    except ValueError:
        raise RuleError("Enter a valid email address.") from None
    _check_password(password)
    if _email_taken(db, email):
        raise RuleError("Someone already uses this email.")
    sub = firm.subscription
    if sub and sub.plan.max_users:
        active = sum(1 for u in team(db, firm) if u.is_active)
        if active >= sub.plan.max_users:
            raise RuleError(f"Your plan allows {sub.plan.max_users} people. Remove someone or upgrade your plan.")
    user = CustomerUser(
        firm_id=firm.id, email=email, name=name.strip(), role=role, password_hash=hash_password(password)
    )
    db.add(user)
    who = actor.email if actor else (admin.email if admin else "admin")
    audit(db, admin, "customer.user_add", f"{who} added {email} ({ROLES[role]}) to {firm.name}", firm=firm, ip=ip)
    db.commit()
    return user


def set_member_active(db: Session, actor: CustomerUser, member: CustomerUser, active: bool, ip: str | None) -> None:
    if not can_manage(actor):
        raise RuleError("Only the owner or an admin can change the team.")
    if member.id == actor.id or member.role == "owner":
        raise RuleError("The owner and your own account can't be switched off here.")
    member.is_active = active
    audit(
        db,
        None,
        "customer.user_" + ("enable" if active else "disable"),
        f"{actor.email} {'re-enabled' if active else 'switched off'} {member.email}",
        firm=actor.firm,
        ip=ip,
    )
    db.commit()


# ------------------------------------------------------------------ computers


def computers(db: Session, firm: Firm) -> list[Computer]:
    return list(db.scalars(select(Computer).where(Computer.firm_id == firm.id).order_by(Computer.first_seen)))


def removals_this_month(db: Session, firm: Firm) -> int:
    since = now() - timedelta(days=30)
    return (
        db.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.firm_id == firm.id,
                AuditEvent.action == "computer.remove_self",
                AuditEvent.created_at >= since,
            )
        )
        or 0
    )


def remove_own_computer(db: Session, actor: CustomerUser, computer: Computer, ip: str | None) -> None:
    if not can_manage(actor):
        raise RuleError("Only the owner or an admin can remove computers.")
    limit = int(services.settings(db)["computer_changes_per_month"])
    if removals_this_month(db, actor.firm) >= limit:
        raise RuleError(f"You can remove {limit} computer(s) per 30 days. Contact support if you need more.")
    audit(
        db,
        None,
        "computer.remove_self",
        f"{actor.email} removed computer '{computer.name or computer.machine_hash[:8]}'",
        firm=actor.firm,
        ip=ip,
    )
    db.delete(computer)
    db.commit()


# ------------------------------------------------------------------ payments


def price_for(db: Session, plan: Plan, computers_wanted: int | None = None) -> services.Quote:
    return services.quote(plan, computers_wanted or plan.computers_included, 1, services.gst_percent(db))


def claim_payment(
    db: Session, user: CustomerUser, *, amount: str, method: str, utr: str, paid_on: str, note: str, ip: str | None
) -> PaymentClaim:
    try:
        amount_paise = money.parse_rupees(amount)
    except ValueError as error:
        raise RuleError(f"Amount: {error}") from None
    if amount_paise <= 0:
        raise RuleError("Enter the amount you paid.")
    if method not in ("upi", "bank"):
        raise RuleError("Choose UPI or bank transfer.")
    if not re.fullmatch(r"[A-Za-z0-9-]{6,40}", utr.strip()):
        raise RuleError("Enter the UTR / transaction ID from your bank or UPI app (6 to 40 letters and digits).")
    try:
        day = date.fromisoformat(paid_on)
    except ValueError:
        raise RuleError("Pick the date you paid.") from None
    if day > money.today() or day < money.today() - timedelta(days=60):
        raise RuleError("Payment date must be within the last 60 days.")
    open_claims = (
        db.scalar(
            select(func.count())
            .select_from(PaymentClaim)
            .where(PaymentClaim.firm_id == user.firm_id, PaymentClaim.status == "open")
        )
        or 0
    )
    if open_claims >= 3:
        raise RuleError("We're still checking your earlier payments. We'll confirm them shortly.")
    firm = user.firm
    plan_id = firm.subscription.plan_id if firm.subscription else firm.requested_plan_id
    claim = PaymentClaim(
        firm_id=firm.id,
        plan_id=plan_id,
        amount_paise=amount_paise,
        method=method,
        utr=utr.strip().upper(),
        paid_on=day,
        note=note.strip()[:500],
    )
    db.add(claim)
    audit(
        db,
        None,
        "payment.claim",
        f"{firm.name} reports a payment of {money.rupees(amount_paise)} ({services.METHODS[method]}, UTR {claim.utr})",
        firm=firm,
        ip=ip,
    )
    db.commit()
    return claim


def open_claims(db: Session, firm: Firm | None = None) -> list[PaymentClaim]:
    query = select(PaymentClaim).where(PaymentClaim.status == "open").order_by(PaymentClaim.created_at)
    if firm is not None:
        query = query.where(PaymentClaim.firm_id == firm.id)
    return list(db.scalars(query).unique())


# ------------------------------------------------------------------ desktop app login


class AppLoginError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


@dataclass
class AppLogin:
    lease: str
    expires_at: object
    user: CustomerUser
    firm: Firm
    status: services.Status


def _version(text: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", text or "")
    return tuple(int(p) for p in parts[:3]) or (0,)


def app_login(
    db: Session, *, email: str, password: str, machine_id: str, machine_name: str, app_version: str, ip: str | None
) -> AppLogin:
    config = services.settings(db)
    renew = f"{get_settings().public_url}/account"
    min_version = config.get("min_app_version", "")
    if min_version and _version(app_version) < _version(min_version):
        raise AppLoginError(
            426, "update_required", f"Please install the latest version of KnowledgeHub (you have {app_version})."
        )

    user = authenticate(db, email, password, ip, channel="desktop app")
    if user is None:
        if is_locked(db, email):
            raise AppLoginError(423, "locked", "Too many wrong passwords. Try again in 15 minutes.")
        raise AppLoginError(401, "invalid_credentials", "Wrong email or password.")
    firm = user.firm
    grace = int(config["grace_days"])
    status = services.firm_status(firm, grace)

    def refuse(code: str, message: str, http: int = 403) -> AppLoginError:
        audit(
            db,
            None,
            "app.login_refused",
            f"Desktop login refused for {user.email}: {code}",
            firm=firm,
            ip=ip,
            details={"code": code, "machine": machine_name[:120]},
        )
        db.commit()
        return AppLoginError(http, code, message)

    if status.code == "blocked":
        raise refuse("firm_blocked", "This account is blocked. Please contact support.")
    if status.code == "pending":
        raise refuse("no_subscription", f"Your subscription isn't active yet. Complete your payment at {renew}", 402)
    if status.code == "expired":
        raise refuse(
            "expired", f"Your subscription ended on {firm.subscription.ends_on:%d %b %Y}. Renew at {renew}", 402
        )

    mhash = lease.machine_hash(machine_id)
    computer = db.scalar(select(Computer).where(Computer.firm_id == firm.id, Computer.machine_hash == mhash))
    if computer is None:
        in_use = db.scalar(select(func.count()).select_from(Computer).where(Computer.firm_id == firm.id)) or 0
        if in_use >= firm.subscription.computers_allowed:
            raise refuse(
                "computer_limit",
                f"Your plan allows {firm.subscription.computers_allowed} computer(s) and "
                f"all are in use. Remove one at {get_settings().public_url}/account/computers",
            )
        computer = Computer(firm_id=firm.id, machine_hash=mhash, name=machine_name.strip()[:120])
        db.add(computer)
        audit(db, None, "computer.add", f"New computer '{computer.name}' activated by {user.email}", firm=firm, ip=ip)
    elif computer.blocked:
        raise refuse("computer_blocked", "This computer has been blocked. Please contact support.")
    computer.last_seen, computer.app_version = now(), app_version[:40]
    if machine_name.strip():
        computer.name = machine_name.strip()[:120]

    sub = firm.subscription
    token, expires = lease.issue(
        claims={
            "sub": str(user.id),
            "mid": mhash,
            "firm": {"id": str(firm.id), "name": firm.name, "reference": firm.reference},
            "user": {"email": user.email, "name": user.name, "role": user.role},
            "plan": {"code": sub.plan.code, "name": sub.plan.name, "invoice_limit": sub.plan.invoice_limit},
            "computers": sub.computers_allowed,
            "ends_on": sub.ends_on.isoformat(),
            "trial": sub.is_trial,
        },
        hours=int(config["lease_hours"]),
        access_ends=lease.access_ends_at(sub.ends_on, 0 if sub.is_trial else grace),
    )
    audit(db, None, "app.login", f"Desktop login: {user.email} on '{computer.name}' ({app_version})", firm=firm, ip=ip)
    db.commit()
    return AppLogin(token, expires, user, firm, status)


def gst_note(db: Session) -> Decimal:
    return services.gst_percent(db)
