import ipaddress
import random
from functools import lru_cache

from fastapi import Request
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.rate_limit import RateLimitEvent


class PostgresRateLimiter:
    """Sliding-window counters stored in PostgreSQL, shared by all API workers and containers.
    Login volumes are tiny, so a table with an index on (key, created_at) is plenty fast and needs no
    extra infrastructure. Two simultaneous requests can both pass the check (at most limit + workers),
    which is acceptable for brute-force protection."""

    def retry_after(self, db: Session, key: str, limit: int, window: int) -> int:
        """Seconds until `key` may try again, or 0 if it is under the limit."""
        cutoff = func.now() - func.make_interval(0, 0, 0, 0, 0, 0, window)
        count, oldest_wait = db.execute(
            select(
                func.count(),
                func.extract(
                    "epoch",
                    func.min(RateLimitEvent.created_at) + func.make_interval(0, 0, 0, 0, 0, 0, window) - func.now(),
                ),
            ).where(RateLimitEvent.key == key, RateLimitEvent.created_at > cutoff)
        ).one()
        return max(int(oldest_wait) + 1, 1) if count >= limit else 0

    def hit(self, db: Session, key: str, window: int) -> None:
        db.add(RateLimitEvent(key=key))
        db.execute(
            delete(RateLimitEvent).where(
                RateLimitEvent.key == key,
                RateLimitEvent.created_at <= func.now() - func.make_interval(0, 0, 0, 0, 0, 0, window),
            )
        )
        if random.random() < 0.01:  # noqa: S311 - occasional global cleanup, not security relevant
            db.execute(
                delete(RateLimitEvent).where(RateLimitEvent.created_at < func.now() - func.make_interval(0, 0, 0, 1))
            )
        db.commit()

    def reset(self, db: Session, key: str) -> None:
        db.execute(delete(RateLimitEvent).where(RateLimitEvent.key == key))
        db.commit()


limiter = PostgresRateLimiter()


@lru_cache
def _trusted_networks():
    return [ipaddress.ip_network(n.strip()) for n in get_settings().trusted_proxies.split(",") if n.strip()]


def client_ip(request: Request) -> str:
    """The caller's IP. X-Forwarded-For is honoured only when the direct peer is a trusted proxy,
    otherwise anyone could rotate fake IPs to dodge the limits."""
    peer = request.client.host if request.client else "unknown"
    try:
        trusted = any(ipaddress.ip_address(peer) in net for net in _trusted_networks())
    except ValueError:
        trusted = False
    forwarded = request.headers.get("x-forwarded-for")
    if trusted and forwarded:
        return forwarded.split(",")[0].strip()
    return peer
