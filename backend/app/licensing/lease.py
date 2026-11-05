"""The current lease: verified once, then held in this process's memory only.

Expiry is measured on the computer's uptime clock, which keeps running during sleep and can't be changed by
setting the Windows date, so moving the clock back doesn't extend a lease. Restarting the app forgets the lease,
so every start needs an online login.
"""

import hashlib
import threading
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.core.config import get_settings

ISSUER = "knowledgehub-licensing"
AUDIENCE = "knowledgehub-desktop"


class LeaseInvalid(Exception):
    pass


def uptime() -> float:
    clock = getattr(time, "CLOCK_BOOTTIME", None)  # Linux: includes suspend. Windows' monotonic already does.
    return time.clock_gettime(clock) if clock is not None else time.monotonic()


def machine_hash(machine_id: str) -> str:
    """Same derivation as the licence server (licensing/app/lease.py)."""
    return hashlib.sha256(f"kh-machine:{machine_id}".encode()).hexdigest()


@lru_cache
def public_key() -> Ed25519PublicKey:
    path = Path(get_settings().licence_public_key_file)
    if not path.is_file():
        raise LeaseInvalid(f"Licence public key missing at {path}")
    key = serialization.load_pem_public_key(path.read_bytes())
    if not isinstance(key, Ed25519PublicKey):
        raise LeaseInvalid("Licence public key must be an Ed25519 key")
    return key


def verify(token: str, machine_id: str) -> dict:
    try:
        claims = jwt.decode(
            token,
            public_key(),
            algorithms=["EdDSA"],
            audience=AUDIENCE,
            issuer=ISSUER,
            options={"require": ["exp", "iat", "aud", "iss", "sub", "mid", "ttl"]},
        )
    except jwt.InvalidTokenError as error:
        raise LeaseInvalid(f"Licence could not be verified: {error}") from error
    if claims["mid"] != machine_hash(machine_id):
        raise LeaseInvalid("This licence belongs to another computer")
    if not 0 < int(claims["ttl"]) <= 7 * 24 * 3600:
        raise LeaseInvalid("Licence has an invalid duration")
    return claims


@dataclass(frozen=True)
class Lease:
    claims: dict
    received_at: float  # uptime() when verified
    ttl: int

    @property
    def seconds_left(self) -> int:
        return max(0, int(self.ttl - (uptime() - self.received_at)))

    @property
    def email(self) -> str:
        return str(self.claims["user"]["email"]).strip().lower()


_lock = threading.Lock()
_current: Lease | None = None


def store(claims: dict) -> Lease:
    global _current
    lease = Lease(claims, uptime(), int(claims["ttl"]))
    with _lock:
        _current = lease
    return lease


def current() -> Lease | None:
    """The valid lease, or None once it has run out."""
    global _current
    with _lock:
        if _current is not None and _current.seconds_left <= 0:
            _current = None
        return _current


def clear() -> None:
    global _current
    with _lock:
        _current = None
