"""Refresh-token rotation and revocation tests (ADR-003)."""
import uuid

import pytest


async def _register(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"owner-{uuid.uuid4()}@example.com",
            "password": "secure-pass-123",
            "tenant_name": "Refresh Cafe",
        },
    )
    assert resp.status_code == 201
    return resp


@pytest.mark.integration
async def test_refresh_rotates_and_old_token_is_revoked(client):
    reg = await _register(client)

    # First refresh with the registration cookies succeeds and rotates the token.
    first = await client.post("/api/v1/auth/refresh", cookies=reg.cookies)
    assert first.status_code == 200

    # Re-using the ORIGINAL refresh token (pre-rotation) is now rejected.
    replay = await client.post("/api/v1/auth/refresh", cookies=reg.cookies)
    assert replay.status_code == 401

    # The rotated token works.
    second = await client.post("/api/v1/auth/refresh", cookies=first.cookies)
    assert second.status_code == 200


@pytest.mark.integration
async def test_logout_revokes_refresh_token(client):
    reg = await _register(client)

    logout = await client.post("/api/v1/auth/logout", cookies=reg.cookies)
    assert logout.status_code == 200

    # The refresh token presented at logout can no longer be used.
    after = await client.post("/api/v1/auth/refresh", cookies=reg.cookies)
    assert after.status_code == 401


@pytest.mark.integration
async def test_prune_removes_expired_refresh_sessions(client):
    from datetime import UTC, datetime, timedelta

    from app.core.db import SessionLocal
    from app.modules.auth.repository import AuthRepository
    from app.modules.auth.service import AuthService

    reg = await _register(client)
    user_id = uuid.UUID(reg.json()["user"]["id"])
    tenant_id = uuid.UUID(reg.json()["tenant"]["id"])

    expired_jti = uuid.uuid4()
    async with SessionLocal() as session:
        await AuthRepository(session).create_refresh_session(
            jti=expired_jti,
            user_id=user_id,
            tenant_id=tenant_id,
            expires_at=datetime.now(UTC) - timedelta(days=1),
        )
        await session.commit()

    async with SessionLocal() as session:
        deleted = await AuthService(session).prune_expired_refresh_sessions()
    assert deleted >= 1

    async with SessionLocal() as session:
        assert await AuthRepository(session).get_refresh_session(expired_jti) is None
