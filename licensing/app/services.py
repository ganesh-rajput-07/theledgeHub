"""Business rules for plans, firms, subscriptions and payments. Every change is written to the audit log."""

import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import money
from app.models import AdminUser, AuditEvent, Computer, Firm, Payment, Plan, Setting, Subscription


class RuleError(ValueError):
    """A request that breaks a business rule; the message is shown to the admin as-is."""


# ------------------------------------------------------------------ settings

SETTING_DEFAULTS: dict[str, str] = {
    "business_name": "KnowledgeHub AI",
    "business_gstin": "",
    "upi_id": "",
    "bank_account_name": "",
    "bank_account_number": "",
    "bank_ifsc": "",
    "bank_name": "",
    "support_email": "",
    "support_phone": "",
    "gst_percent": "18",
    "grace_days": "0",
    "trial_days": "14",
    "computer_changes_per_month": "2",
    "lease_hours": "24",
    "download_url": "",
    "latest_version": "",
    "min_app_version": "",
}
INT_SETTINGS = {
    "grace_days": (0, 30),
    "trial_days": (1, 90),
    "computer_changes_per_month": (0, 20),
    "lease_hours": (1, 168),
}


def settings(db: Session) -> dict[str, str]:
    values = dict(SETTING_DEFAULTS)
    values.update({row.key: row.value for row in db.scalars(select(Setting))})
    return values


def save_settings(db: Session, admin: AdminUser, form: dict[str, str], ip: str | None) -> None:
    current = settings(db)
    changes = {}
    for key in SETTING_DEFAULTS:
        if key not in form:
            continue
        value = form[key].strip()
        if key in INT_SETTINGS:
            low, high = INT_SETTINGS[key]
            if not value.isdigit() or not low <= int(value) <= high:
                raise RuleError(f"{key.replace('_', ' ').capitalize()} must be a whole number from {low} to {high}.")
        if key == "gst_percent":
            try:
                if not 0 <= Decimal(value) <= 28:
                    raise ValueError
            except (ArithmeticError, ValueError):
                raise RuleError("GST % must be a number from 0 to 28.") from None
        if key == "download_url" and value and not re.match(r"^https://[^\s]+$", value):
            raise RuleError("Download link must start with https://")
        if key in ("latest_version", "min_app_version") and value and not re.fullmatch(r"\d+(\.\d+){0,2}", value):
            raise RuleError("Versions look like 1.0 or 1.2.3.")
        if key == "business_gstin" and value and not GSTIN_RE.match(value.upper()):
            raise RuleError("Your GSTIN doesn't look valid (15 characters, e.g. 24ABCDE1234F1Z5).")
        if value != current[key]:
            changes[key] = {"from": current[key], "to": value}
            row = db.get(Setting, key) or Setting(key=key)
            row.value = value
            db.add(row)
    if changes:
        audit(db, admin, "settings.update", f"Changed settings: {', '.join(changes)}", details=changes, ip=ip)
    db.commit()


def gst_percent(db: Session) -> Decimal:
    return Decimal(settings(db)["gst_percent"])


# ------------------------------------------------------------------ audit


def audit(
    db: Session,
    admin: AdminUser | None,
    action: str,
    summary: str,
    *,
    firm: Firm | None = None,
    details: dict | None = None,
    ip: str | None = None,
) -> None:
    db.add(
        AuditEvent(
            admin_id=admin.id if admin else None,
            action=action,
            firm_id=firm.id if firm else None,
            summary=summary,
            details=details or {},
            ip=ip,
        )
    )


# ------------------------------------------------------------------ status


@dataclass(frozen=True)
class Status:
    code: str  # blocked | pending | trial | active | grace | expired
    label: str
    days_left: int | None = None  # days of access left including today (active/trial/grace)

    @property
    def can_use(self) -> bool:
        return self.code in ("trial", "active", "grace")


def firm_status(firm: Firm, grace_days: int, today: date | None = None) -> Status:
    today = today or money.today()
    sub = firm.subscription
    if firm.blocked:
        return Status("blocked", "Blocked")
    if sub is None:
        return Status("pending", "Pending payment")
    left = (sub.ends_on - today).days + 1
    if left > 0:
        return Status("trial", "Trial", left) if sub.is_trial else Status("active", "Active", left)
    if grace_days and not sub.is_trial and -left < grace_days:
        return Status("grace", "Grace period", grace_days + left)
    return Status("expired", "Trial ended" if sub.is_trial else "Expired")


# ------------------------------------------------------------------ plans

CODE_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,38}$")
PLAN_FIELDS = (
    "name",
    "code",
    "description",
    "price_paise",
    "billing_months",
    "computers_included",
    "extra_computer_paise",
    "max_users",
    "invoice_limit",
    "is_active",
    "is_public",
    "sort_order",
)


def save_plan(db: Session, admin: AdminUser, plan: Plan | None, data: dict, ip: str | None) -> Plan:
    if not CODE_RE.match(data["code"]):
        raise RuleError("Code: 2 to 39 lowercase letters, digits or dashes, e.g. 'starter' or 'pro-yearly'.")
    if not data["name"].strip():
        raise RuleError("Give the plan a name.")
    if data["billing_months"] not in (1, 3, 6, 12):
        raise RuleError("Billing period must be 1, 3, 6 or 12 months.")
    if not 1 <= data["computers_included"] <= 500:
        raise RuleError("Computers included must be from 1 to 500.")
    for key in ("max_users", "invoice_limit"):
        if data[key] is not None and data[key] < 1:
            raise RuleError("Limits must be at least 1, or empty for unlimited.")

    creating = plan is None
    plan = plan or Plan()
    changes = {
        k: {"from": getattr(plan, k, None), "to": v} for k, v in data.items() if creating or getattr(plan, k) != v
    }
    for key, value in data.items():
        setattr(plan, key, value)
    db.add(plan)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise RuleError(f"Another plan already uses the code '{data['code']}'.") from None
    if creating:
        audit(
            db,
            admin,
            "plan.create",
            f"Created plan {plan.name} at {money.rupees(plan.price_paise)}",
            details={"plan": plan.code},
            ip=ip,
        )
    elif changes:
        summary = f"Updated plan {plan.name}"
        if "price_paise" in changes:
            summary += (
                f": price {money.rupees(changes['price_paise']['from'])} → "
                f"{money.rupees(changes['price_paise']['to'])} (existing subscriptions keep their price)"
            )
        audit(db, admin, "plan.update", summary, details={"plan": plan.code, "changes": changes}, ip=ip)
    db.commit()
    return plan


def plans(db: Session, *, sellable_only: bool = False) -> list[Plan]:
    query = select(Plan).order_by(Plan.sort_order, Plan.price_paise)
    if sellable_only:
        query = query.where(Plan.is_active)
    return list(db.scalars(query))


def subscriber_counts(db: Session) -> dict[uuid.UUID, int]:
    rows = db.execute(select(Subscription.plan_id, func.count()).group_by(Subscription.plan_id))
    return {plan_id: count for plan_id, count in rows}


@dataclass(frozen=True)
class Quote:
    base: int
    extra_computers: int
    extra: int
    subtotal: int
    gst: int
    total: int


def quote(plan: Plan, computers: int, periods: int, gst: Decimal) -> Quote:
    extra_computers = max(0, computers - plan.computers_included)
    per_period = plan.price_paise + extra_computers * plan.extra_computer_paise
    subtotal = per_period * periods
    tax = money.gst_on(subtotal, gst)
    return Quote(
        plan.price_paise * periods,
        extra_computers,
        extra_computers * plan.extra_computer_paise * periods,
        subtotal,
        tax,
        subtotal + tax,
    )


# ------------------------------------------------------------------ firms

GSTIN_RE = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
MOBILE_RE = re.compile(r"^(\+91[ -]?)?[6-9]\d{9}$")
_email = TypeAdapter(EmailStr)


def clean_firm(data: dict) -> dict:
    data = {k: (v or "").strip() for k, v in data.items()}
    if not data["name"]:
        raise RuleError("Firm name is required.")
    try:
        data["email"] = _email.validate_python(data["email"]).lower()
    except ValidationError:
        raise RuleError("Enter a valid email address.") from None
    if data["mobile"] and not MOBILE_RE.match(data["mobile"].replace(" ", "")):
        raise RuleError("Mobile should be a 10-digit Indian number, e.g. 98250 12345.")
    data["gstin"] = data["gstin"].upper()
    if data["gstin"] and not GSTIN_RE.match(data["gstin"]):
        raise RuleError("GSTIN doesn't look valid (15 characters, e.g. 24ABCDE1234F1Z5).")
    return data


def create_firm(db: Session, admin: AdminUser | None, data: dict, ip: str | None) -> Firm:
    data = clean_firm(data)
    for _ in range(10):
        firm = Firm(reference=f"KH-{secrets.randbelow(90000) + 10000}", **data)
        db.add(firm)
        try:
            db.flush()
            break
        except IntegrityError as error:
            db.rollback()
            if "email" in str(error.orig):
                raise RuleError("A firm with this email already exists.") from None
    else:  # pragma: no cover - 10 reference collisions in a row
        raise RuleError("Couldn't create a payment reference; try again.")
    audit(db, admin, "firm.create", f"Created firm {firm.name} ({firm.reference})", firm=firm, ip=ip)
    db.commit()
    return firm


def update_firm(db: Session, admin: AdminUser, firm: Firm, data: dict, ip: str | None) -> None:
    data = clean_firm(data)
    changes = {k: {"from": getattr(firm, k), "to": v} for k, v in data.items() if getattr(firm, k) != v}
    for key, value in data.items():
        setattr(firm, key, value)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise RuleError("A firm with this email already exists.") from None
    if changes:
        audit(db, admin, "firm.update", f"Edited {firm.name}: {', '.join(changes)}", firm=firm, details=changes, ip=ip)
    db.commit()


def set_blocked(db: Session, admin: AdminUser, firm: Firm, blocked: bool, reason: str, ip: str | None) -> None:
    if blocked and not reason.strip():
        raise RuleError("Give a reason for blocking (it's shown in the activity log).")
    firm.blocked, firm.blocked_reason = blocked, reason.strip() if blocked else ""
    audit(
        db,
        admin,
        "firm.block" if blocked else "firm.unblock",
        f"{'Blocked' if blocked else 'Unblocked'} {firm.name}" + (f": {reason.strip()}" if blocked else ""),
        firm=firm,
        ip=ip,
    )
    db.commit()


# ------------------------------------------------------------------ subscriptions & payments

METHODS = {"upi": "UPI", "bank": "Bank transfer", "cash": "Cash", "cheque": "Cheque", "other": "Other"}


def record_payment(
    db: Session,
    admin: AdminUser,
    firm: Firm,
    *,
    plan: Plan,
    computers: int,
    periods: int,
    amount_paise: int,
    method: str,
    utr: str,
    paid_on: date,
    note: str,
    ip: str | None,
) -> Payment:
    """Activate or extend the firm's subscription. A renewal before expiry continues from the current end date
    (no days lost); after expiry, or after a trial, the new period starts today."""
    if not plan.is_active:
        raise RuleError("This plan is no longer sold. Pick an active plan.")
    if method not in METHODS:
        raise RuleError("Choose how the payment was made.")
    if not 1 <= periods <= 24:
        raise RuleError("Number of periods must be from 1 to 24.")
    if not plan.computers_included <= computers <= 500:
        raise RuleError(f"Computers must be at least {plan.computers_included} (included in {plan.name}).")
    if amount_paise <= 0:
        raise RuleError("Enter the amount received.")
    today = money.today()
    if paid_on > today:
        raise RuleError("Payment date can't be in the future.")

    sub = firm.subscription
    starts = sub.ends_on + timedelta(days=1) if sub and not sub.is_trial and sub.ends_on >= today else today
    ends = money.period_end(starts, plan.billing_months * periods)
    price = quote(plan, computers, 1, Decimal(0)).subtotal
    gst = gst_percent(db)
    expected = quote(plan, computers, periods, gst)
    # GST included in what was received, split back out for the records.
    gst_paise = amount_paise - int(Decimal(amount_paise) * 100 / (100 + gst)) if gst else 0

    if sub is None:
        sub = Subscription(firm_id=firm.id)
        db.add(sub)
    sub.plan_id, sub.price_paise, sub.billing_months = plan.id, price, plan.billing_months
    sub.computers_allowed, sub.ends_on, sub.is_trial = computers, ends, False

    payment = Payment(
        firm_id=firm.id,
        plan_id=plan.id,
        amount_paise=amount_paise,
        gst_paise=gst_paise,
        method=method,
        utr=utr.strip(),
        paid_on=paid_on,
        periods=periods,
        covers_from=starts,
        covers_to=ends,
        note=note.strip(),
        recorded_by=admin.id,
    )
    db.add(payment)
    summary = (
        f"Payment {money.rupees(amount_paise)} ({METHODS[method]}) from {firm.name}: {plan.name}, "
        f"{computers} computer(s), access until {ends:%d %b %Y}"
    )
    if amount_paise != expected.total:
        summary += f". Note: price list total is {money.rupees(expected.total)}"
    audit(
        db,
        admin,
        "payment.record",
        summary,
        firm=firm,
        details={
            "amount": amount_paise,
            "expected": expected.total,
            "utr": utr.strip(),
            "from": starts.isoformat(),
            "to": ends.isoformat(),
        },
        ip=ip,
    )
    db.commit()
    db.refresh(firm)
    return payment


def grant_trial(
    db: Session, admin: AdminUser, firm: Firm, *, plan: Plan, days: int, computers: int, ip: str | None
) -> None:
    sub = firm.subscription
    if sub and not sub.is_trial and sub.ends_on >= money.today():
        raise RuleError("This firm has a paid subscription; extend it instead of starting a trial.")
    if not 1 <= days <= 90:
        raise RuleError("Trial length must be from 1 to 90 days.")
    if not 1 <= computers <= 20:
        raise RuleError("Trial computers must be from 1 to 20.")
    ends = money.today() + timedelta(days=days - 1)
    if sub is None:
        sub = Subscription(firm_id=firm.id)
        db.add(sub)
    sub.plan_id, sub.price_paise, sub.billing_months = plan.id, 0, plan.billing_months
    sub.computers_allowed, sub.ends_on, sub.is_trial = computers, ends, True
    audit(
        db,
        admin,
        "subscription.trial",
        f"Trial for {firm.name}: {plan.name}, {days} days (until {ends:%d %b %Y})",
        firm=firm,
        details={"days": days, "computers": computers},
        ip=ip,
    )
    db.commit()
    db.refresh(firm)


def adjust_subscription(
    db: Session, admin: AdminUser, firm: Firm, *, ends_on: date, computers: int, reason: str, ip: str | None
) -> None:
    """Manual correction: change the end date or computer limit (goodwill days, fixing a mistake)."""
    sub = firm.subscription
    if sub is None:
        raise RuleError("This firm has no subscription yet. Record a payment or start a trial first.")
    if not reason.strip():
        raise RuleError("Give a reason for the change (it's kept in the activity log).")
    if not 1 <= computers <= 500:
        raise RuleError("Computers must be from 1 to 500.")
    if ends_on > money.today() + timedelta(days=3 * 366):
        raise RuleError("End date can't be more than 3 years ahead.")
    changes = {}
    if sub.ends_on != ends_on:
        changes["ends_on"] = {"from": sub.ends_on.isoformat(), "to": ends_on.isoformat()}
    if sub.computers_allowed != computers:
        changes["computers"] = {"from": sub.computers_allowed, "to": computers}
    if not changes:
        raise RuleError("Nothing changed.")
    sub.ends_on, sub.computers_allowed = ends_on, computers
    parts = []
    if "ends_on" in changes:
        parts.append(f"access until {ends_on:%d %b %Y}")
    if "computers" in changes:
        parts.append(f"{computers} computer(s)")
    audit(
        db,
        admin,
        "subscription.adjust",
        f"Adjusted {firm.name}: {', '.join(parts)}. Reason: {reason.strip()}",
        firm=firm,
        details=changes | {"reason": reason.strip()},
        ip=ip,
    )
    db.commit()


def set_computer_blocked(
    db: Session, admin: AdminUser, computer: Computer, firm: Firm, blocked: bool, ip: str | None
) -> None:
    computer.blocked = blocked
    audit(
        db,
        admin,
        "computer.block" if blocked else "computer.unblock",
        f"{'Blocked' if blocked else 'Unblocked'} computer '{computer.name or computer.machine_hash[:8]}' "
        f"of {firm.name}",
        firm=firm,
        ip=ip,
    )
    db.commit()


def remove_computer(db: Session, admin: AdminUser, computer: Computer, firm: Firm, ip: str | None) -> None:
    audit(
        db,
        admin,
        "computer.remove",
        f"Removed computer '{computer.name or computer.machine_hash[:8]}' of {firm.name} (frees a seat)",
        firm=firm,
        ip=ip,
    )
    db.delete(computer)
    db.commit()


# ------------------------------------------------------------------ dashboard


def dashboard(db: Session) -> dict:
    grace = int(settings(db)["grace_days"])
    today = money.today()
    firms = list(db.scalars(select(Firm)).unique())
    counts = dict.fromkeys(("active", "trial", "grace", "pending", "expired", "blocked"), 0)
    expiring, pending, mrr = [], [], 0
    for firm in firms:
        status = firm_status(firm, grace, today)
        counts[status.code] += 1
        if status.code in ("active", "grace"):
            mrr += firm.subscription.price_paise // max(1, firm.subscription.billing_months)
        if status.code in ("active", "trial", "grace") and status.days_left is not None and status.days_left <= 7:
            expiring.append((firm, status))
        if status.code == "pending":
            pending.append(firm)
    month_start = today.replace(day=1)
    collected = (
        db.scalar(select(func.coalesce(func.sum(Payment.amount_paise), 0)).where(Payment.paid_on >= month_start)) or 0
    )
    recent = list(db.scalars(select(Payment).order_by(Payment.created_at.desc()).limit(8)).unique())
    return {
        "counts": counts,
        "mrr": mrr,
        "collected": collected,
        "expiring": sorted(expiring, key=lambda x: x[1].days_left),
        "pending": pending,
        "recent": recent,
        "total": len(firms),
        "month_start": month_start,
    }


def now() -> datetime:
    return datetime.now(UTC)
