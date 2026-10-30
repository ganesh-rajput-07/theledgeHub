import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import jwt
from cryptography.fernet import Fernet, InvalidToken
from pwdlib import PasswordHash

from app.core.config import get_settings

# ---------------------------------------------------------------- passwords

_password_hash = PasswordHash.recommended()  # Argon2id
# Verified against when the email is unknown, so login takes the same time either way.
_DUMMY_HASH = _password_hash.hash("timing-equalizer")


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if password_hash is None:
        _password_hash.verify(password, _DUMMY_HASH)
        return False
    return _password_hash.verify(password, password_hash)


# ---------------------------------------------------------------- tokens

ACCESS = "access"
REFRESH = "refresh"


class TokenError(Exception):
    pass


@dataclass(frozen=True)
class TokenClaims:
    user_id: uuid.UUID
    token_type: str
    jti: uuid.UUID
    expires_at: datetime


def create_token(user_id: uuid.UUID, token_type: str, jti: uuid.UUID | None = None) -> tuple[str, TokenClaims]:
    settings = get_settings()
    lifetime = (
        timedelta(minutes=settings.access_token_expire_minutes)
        if token_type == ACCESS
        else timedelta(days=settings.refresh_token_expire_days)
    )
    claims = TokenClaims(user_id, token_type, jti or uuid.uuid4(), datetime.now(UTC) + lifetime)
    payload = {
        "sub": str(claims.user_id),
        "type": token_type,
        "jti": str(claims.jti),
        "iat": datetime.now(UTC),
        "exp": claims.expires_at,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm), claims


def decode_token(token: str, expected_type: str) -> TokenClaims:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],  # pinned: never trust the token's own "alg"
            options={"require": ["sub", "exp", "type", "jti"]},
        )
        claims = TokenClaims(
            uuid.UUID(payload["sub"]),
            payload["type"],
            uuid.UUID(payload["jti"]),
            datetime.fromtimestamp(payload["exp"], UTC),
        )
    except (jwt.PyJWTError, ValueError) as exc:
        raise TokenError("Invalid or expired token") from exc
    if claims.token_type != expected_type:
        raise TokenError(f"Expected a {expected_type} token")
    return claims


# ---------------------------------------------------------------- provider API keys at rest


@lru_cache
def _fernet() -> Fernet:
    return Fernet(get_settings().encryption_key.encode())


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Stored secret cannot be decrypted (was ENCRYPTION_KEY changed?)") from exc


def secret_hint(secret: str) -> str:
    """Last 4 characters only - enough for a user to recognise which key is stored."""
    return f"…{secret[-4:]}" if len(secret) >= 8 else "…"
