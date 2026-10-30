import ipaddress
import threading
import time
from collections import defaultdict, deque
from functools import lru_cache

from fastapi import Request

from app.core.config import get_settings


class SlidingWindowLimiter:
    """In-memory sliding-window counter. Good for a single API process; with several workers or
    machines, move the counters to a shared store (Redis) so limits apply across all of them."""

    def __init__(self):
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, window: float, now: float) -> deque[float]:
        events = self._events[key]
        while events and events[0] <= now - window:
            events.popleft()
        return events

    def retry_after(self, key: str, limit: int, window: float) -> int:
        """Seconds until `key` may try again, or 0 if it is under the limit."""
        now = time.monotonic()
        with self._lock:
            events = self._prune(key, window, now)
            return int(events[0] + window - now) + 1 if len(events) >= limit else 0

    def hit(self, key: str) -> None:
        with self._lock:
            self._events[key].append(time.monotonic())

    def reset(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)


limiter = SlidingWindowLimiter()


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
