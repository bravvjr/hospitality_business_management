"""Health / smoke tests.

Unit tests touch no external services (via ASGITransport). The readiness test
is marked integration because it requires a reachable database.
"""
import pytest


@pytest.mark.unit
async def test_root(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert "service" in body
    assert body["health"] == "/api/v1/health/live"


@pytest.mark.unit
async def test_liveness(client):
    resp = await client.get("/api/v1/health/live")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"]


@pytest.mark.integration
async def test_readiness_with_db(client):
    resp = await client.get("/api/v1/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"
