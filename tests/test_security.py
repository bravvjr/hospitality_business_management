"""Unit tests for password hashing and JWT helpers."""
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import Settings
from app.core.security import (
    InvalidTokenError,
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        jwt_secret_key="unit-test-secret",
        access_token_expire_minutes=60,
        refresh_token_expire_days=7,
    )


@pytest.mark.unit
def test_hash_and_verify_password():
    password_hash = hash_password("strong-password")
    assert verify_password("strong-password", password_hash)
    assert not verify_password("wrong-password", password_hash)


@pytest.mark.unit
def test_access_token_round_trip(settings: Settings):
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    token = create_access_token(
        user_id=user_id,
        tenant_id=tenant_id,
        role_key="owner",
        settings=settings,
    )
    payload = decode_token(token, settings=settings)
    assert payload.user_id == user_id
    assert payload.tenant_id == tenant_id
    assert payload.role_key == "owner"
    assert payload.token_type == "access"


@pytest.mark.unit
def test_expired_token_rejected(settings: Settings):
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "role": "owner",
        "type": "access",
        "iat": now,
        "exp": now - timedelta(minutes=1),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    with pytest.raises(InvalidTokenError):
        decode_token(token, settings=settings)
