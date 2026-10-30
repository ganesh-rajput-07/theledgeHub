from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class RateLimitEvent(Base):
    """One row per counted attempt. Lives in PostgreSQL so every API worker and container shares the
    same counters. Rows older than the window are pruned as new ones arrive."""

    __tablename__ = "rate_limit_events"
    __table_args__ = (Index("ix_rate_limit_events_key_created", "key", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(320), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
