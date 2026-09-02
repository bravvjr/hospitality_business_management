"""Integration tests for auth endpoints."""
import uuid

import pytest


@pytest.mark.integration
async def test_register_login_and_me(client, anonymous_client):
    email = f"owner-{uuid.uuid4()}@example.com"
    password = "secure-pass-123"

    register_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "tenant_name": "Test Cafe",
            "base_currency": "KES",
        },
    )
    assert register_resp.status_code == 201
    body = register_resp.json()
    assert body["user"]["email"] == email
    assert body["tenant"]["name"] == "Test Cafe"
    assert body["membership"]["role"]["key"] == "owner"

    unauth_resp = await anonymous_client.get("/api/v1/auth/me")
    assert unauth_resp.status_code == 401

    me_resp = await client.get("/api/v1/auth/me", cookies=register_resp.cookies)
    assert me_resp.status_code == 200
    assert me_resp.json()["user"]["email"] == email

    logout_resp = await client.post("/api/v1/auth/logout", cookies=register_resp.cookies)
    assert logout_resp.status_code == 200

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == 200
    assert login_resp.json()["membership"]["role"]["key"] == "owner"

    bad_login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "wrong-password"},
    )
    assert bad_login.status_code == 401


@pytest.mark.integration
async def test_register_conflict(client):
    email = f"dup-{uuid.uuid4()}@example.com"
    payload = {
        "email": email,
        "password": "secure-pass-123",
        "tenant_name": "Dup Cafe",
    }
    first = await client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201

    second = await client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 409
