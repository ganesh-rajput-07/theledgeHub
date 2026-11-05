"""Licence leases: short-lived, Ed25519-signed JWTs that let the desktop app work offline.

Only this server holds the private key. The desktop app ships the public key and verifies the signature, the
audience, the machine and the time, so a lease can't be forged, edited, or moved to another computer.
"""

import hashlib
import uuid
from datetime import UTC, datetime, time, timedelta
from functools import lru_cache
from pathlib import Path

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from app.config import get_settings
from app.money import IST

ISSUER = "knowledgehub-licensing"
AUDIENCE = "knowledgehub-desktop"


class LeaseKeyMissing(RuntimeError):
    pass


def generate_keypair(private_path: Path) -> str:
    """Write a new private key (owner-only permissions) and return the public key PEM."""
    key = Ed25519PrivateKey.generate()
    private_path.parent.mkdir(parents=True, exist_ok=True)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    private_path.touch(mode=0o600, exist_ok=False)
    private_path.write_bytes(pem)
    return public_pem(key.public_key())


def public_pem(key: Ed25519PublicKey) -> str:
    return key.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()


@lru_cache
def private_key() -> Ed25519PrivateKey:
    path = Path(get_settings().lease_private_key_file)
    if not path.is_file():
        raise LeaseKeyMissing(f"Lease signing key not found at {path}. Run: python -m app.cli generate-keys")
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise LeaseKeyMissing("The lease signing key must be an Ed25519 key.")
    return key


def key_id(key: Ed25519PublicKey) -> str:
    raw = key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return hashlib.sha256(raw).hexdigest()[:16]


def access_ends_at(last_day, grace_days: int) -> datetime:
    """End of the last usable day (subscription end + grace) at midnight India time, in UTC."""
    final = last_day + timedelta(days=grace_days)
    return datetime.combine(final + timedelta(days=1), time(0, 0), tzinfo=IST).astimezone(UTC)


def issue(*, claims: dict, hours: int, access_ends: datetime, now: datetime | None = None) -> tuple[str, datetime]:
    now = now or datetime.now(UTC)
    expires = min(now + timedelta(hours=hours), access_ends)
    key = private_key()
    payload = {
        **claims,
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()) - 60,
        "exp": int(expires.timestamp()),
        "ttl": int((expires - now).total_seconds()),  # the app counts this down on its own uptime clock
        "jti": str(uuid.uuid4()),
    }
    token = jwt.encode(payload, key, algorithm="EdDSA", headers={"kid": key_id(key.public_key())})
    return token, expires


def verify(token: str, public_key_pem: str, machine_hash: str) -> dict:
    """Reference check for the desktop app (it does the same on its side). Raises jwt.InvalidTokenError."""
    key = serialization.load_pem_public_key(public_key_pem.encode())
    claims = jwt.decode(
        token,
        key,
        algorithms=["EdDSA"],
        audience=AUDIENCE,
        issuer=ISSUER,
        options={"require": ["exp", "iat", "aud", "iss", "sub", "mid"]},
    )
    if claims["mid"] != machine_hash:
        raise jwt.InvalidTokenError("Lease belongs to another computer")
    return claims


def machine_hash(machine_id: str) -> str:
    return hashlib.sha256(f"kh-machine:{machine_id}".encode()).hexdigest()
