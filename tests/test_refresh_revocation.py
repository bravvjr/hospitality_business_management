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
