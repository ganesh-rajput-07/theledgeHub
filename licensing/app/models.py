"""Licence server data model. Money is stored in paise (integers); dates are calendar dates in IST terms."""

import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _id() -> Mapped[uuid.UUID]:
    return mapped_column(primary_key=True, default=uuid.uuid4)


def _created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[uuid.UUID] = _id()
    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created()


class AdminSession(Base):
    __tablename__ = "admin_sessions"

    id: Mapped[uuid.UUID] = _id()
    admin_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("admin_users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)  # sha256 of the cookie value
    csrf_token: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ip: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = _created()

    admin: Mapped[AdminUser] = relationship(lazy="joined")


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = _id()
    code: Mapped[str] = mapped_column(String(40), unique=True)  # stable id, e.g. "starter"
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text, default="")
    price_paise: Mapped[int] = mapped_column(Integer)  # per billing period, excluding GST
    billing_months: Mapped[int] = mapped_column(Integer, default=1)  # 1 = monthly, 12 = yearly
    computers_included: Mapped[int] = mapped_column(Integer, default=1)
    extra_computer_paise: Mapped[int] = mapped_column(Integer, default=0)  # per extra computer per period
    max_users: Mapped[int | None] = mapped_column(Integer)  # None = unlimited
    invoice_limit: Mapped[int | None] = mapped_column(Integer)  # invoices per month; None = unlimited
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # inactive plans can't be sold
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)  # shown on the website pricing page
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Firm(Base):
    __tablename__ = "firms"

    id: Mapped[uuid.UUID] = _id()
    reference: Mapped[str] = mapped_column(String(20), unique=True)  # payment reference shown to the customer
    name: Mapped[str] = mapped_column(String(200))
    contact_name: Mapped[str] = mapped_column(String(120), default="")
    email: Mapped[str] = mapped_column(String(255), unique=True)
    mobile: Mapped[str] = mapped_column(String(20), default="")
    city: Mapped[str] = mapped_column(String(80), default="")
    gstin: Mapped[str] = mapped_column(String(15), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    blocked_reason: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = _created()

    subscription: Mapped["Subscription | None"] = relationship(back_populates="firm", uselist=False, lazy="joined")


class Subscription(Base):
    """One per firm, extended by payments. Price and limits are a snapshot: editing a plan's price
    later only affects new sales and renewals, never what a firm already paid for."""

    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = _id()
    firm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("firms.id", ondelete="CASCADE"), unique=True)
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plans.id"))
    price_paise: Mapped[int] = mapped_column(Integer)  # per period, excl. GST, incl. extra computers
    billing_months: Mapped[int] = mapped_column(Integer, default=1)
    computers_allowed: Mapped[int] = mapped_column(Integer)
    ends_on: Mapped[date] = mapped_column(Date)  # last day of access (inclusive)
    is_trial: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    firm: Mapped[Firm] = relationship(back_populates="subscription")
    plan: Mapped[Plan] = relationship(lazy="joined")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = _id()
    firm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("firms.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plans.id"))
    amount_paise: Mapped[int] = mapped_column(Integer)  # what was actually received, incl. GST
    gst_paise: Mapped[int] = mapped_column(Integer, default=0)
    method: Mapped[str] = mapped_column(String(20))  # upi | bank | cash | cheque | other
    utr: Mapped[str] = mapped_column(String(60), default="")  # bank / UPI transaction reference
    paid_on: Mapped[date] = mapped_column(Date)
    periods: Mapped[int] = mapped_column(Integer, default=1)
    covers_from: Mapped[date] = mapped_column(Date)
    covers_to: Mapped[date] = mapped_column(Date)
    note: Mapped[str] = mapped_column(Text, default="")
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = _created()

    firm: Mapped[Firm] = relationship(lazy="joined")
    plan: Mapped[Plan] = relationship(lazy="joined")


class Computer(Base):
    """A computer the desktop app was activated on (filled by the app login API)."""

    __tablename__ = "computers"
    __table_args__ = (UniqueConstraint("firm_id", "machine_hash"),)

    id: Mapped[uuid.UUID] = _id()
    firm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("firms.id", ondelete="CASCADE"), index=True)
    machine_hash: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(120), default="")
    app_version: Mapped[str] = mapped_column(String(40), default="")
    blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    first_seen: Mapped[datetime] = _created()
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = _id()
    admin_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("admin_users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(60), index=True)
    firm_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("firms.id", ondelete="SET NULL"), index=True)
    summary: Mapped[str] = mapped_column(Text)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    ip: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    admin: Mapped[AdminUser | None] = relationship(lazy="joined")
    firm: Mapped[Firm | None] = relationship(lazy="joined")
