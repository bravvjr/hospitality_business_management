"""Password hashing and JWT helpers (ADR-003)."""
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import Settings, get_settings

_password_hasher = PasswordHasher()


class AuthError(Exception):
    """Base class for authentication failures."""


class InvalidTokenError(AuthError):
    """JWT is missing, expired, or malformed."""


class InvalidCredentialsError(AuthError):
    """Email/password pair is wrong."""


@dataclass(frozen=True, slots=True)
class TokenPayload:
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    role_key: str
    token_type: str


def hash_password(plain_password: str) -> str:
    return _password_hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, plain_password)
    except VerifyMismatchError:
        return False


def _encode_token(
    *,
    settings: Settings,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    role_key: str,
    token_type: str,
    expires_delta: timedelta,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "role": role_key,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(
    *,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    role_key: str,
    settings: Settings | None = None,
) -> str:
    settings = settings or get_settings()
    return _encode_token(
        settings=settings,
        user_id=user_id,
        tenant_id=tenant_id,
        role_key=role_key,
        token_type="access",
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(
    *,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    role_key: str,
    settings: Settings | None = None,
) -> str:
    settings = settings or get_settings()
    return _encode_token(
        settings=settings,
        user_id=user_id,
        tenant_id=tenant_id,
        role_key=role_key,
        token_type="refresh",
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(token: str, *, settings: Settings | None = None) -> TokenPayload:
    settings = settings or get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError("Invalid or expired token") from exc

    try:
        return TokenPayload(
            user_id=uuid.UUID(payload["sub"]),
            tenant_id=uuid.UUID(payload["tenant_id"]),
            role_key=payload["role"],
            token_type=payload["type"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidTokenError("Token payload is missing required claims") from exc
