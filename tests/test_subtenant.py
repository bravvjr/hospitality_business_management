"""Sub-tenant hierarchy + downward RBAC inheritance tests (ADR-012)."""
import uuid

import pytest


async def _register(client, tenant_name: str):
    email = f"owner-{uuid.uuid4()}@example.com"
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "secure-pass-123",
            "tenant_name": tenant_name,
            "base_currency": "KES",
        },
    )
    assert resp.status_code == 201
    return resp


@pytest.mark.integration
async def test_owner_creates_and_administers_sub_tenant(client):
    owner = await _register(client, "HQ")
    parent_id = owner.json()["tenant"]["id"]

    # Create a sub-tenant (branch).
    created = await client.post(
        "/api/v1/tenants",
        json={"name": "Branch A", "base_currency": "KES"},
        cookies=owner.cookies,
    )
    assert created.status_code == 201
    child = created.json()
    assert child["parent_tenant_id"] == parent_id

    # It shows up under the parent.
    listed = await client.get("/api/v1/tenants", cookies=owner.cookies)
    assert listed.status_code == 200
    assert child["id"] in {t["id"] for t in listed.json()}

    # Owner switches into the child via inherited access (no membership there).
    switched = await client.post(
        "/api/v1/auth/switch-tenant",
        json={"tenant_id": child["id"]},
        cookies=owner.cookies,
    )
    assert switched.status_code == 200
    assert switched.json()["tenant"]["id"] == child["id"]
    assert switched.json()["membership"]["role"]["key"] == "owner"  # inherited

    # Owner manages staff on the child using inherited authority.
    add = await client.post(
        "/api/v1/auth/staff",
        json={
            "email": f"cashier-{uuid.uuid4()}@example.com",
            "password": "cashier-pass-123",
            "role_key": "cashier",
        },
        cookies=switched.cookies,
    )
    assert add.status_code == 201
    staff = await client.get("/api/v1/auth/staff", cookies=switched.cookies)
    # Only the child's own membership (the cashier) — the owner's membership is on HQ.
    assert {m["membership"]["role"]["key"] for m in staff.json()} == {"cashier"}


@pytest.mark.integration
async def test_inherited_role_is_not_elevated(client):
    owner = await _register(client, "HQ2")
    child = (
        await client.post(
            "/api/v1/tenants",
            json={"name": "Branch B", "base_currency": "KES"},
            cookies=owner.cookies,
        )
    ).json()

    # A cashier at the parent inherits only the cashier role at the child.
    cashier_email = f"cashier-{uuid.uuid4()}@example.com"
    await client.post(
        "/api/v1/auth/staff",
        json={"email": cashier_email, "password": "cashier-pass-123", "role_key": "cashier"},
        cookies=owner.cookies,
    )
    cashier_login = await client.post(
        "/api/v1/auth/login",
        json={"email": cashier_email, "password": "cashier-pass-123"},
    )

    # Cashier can switch into the child (inherited) ...
    switched = await client.post(
        "/api/v1/auth/switch-tenant",
        json={"tenant_id": child["id"]},
        cookies=cashier_login.cookies,
    )
    assert switched.status_code == 200
    assert switched.json()["membership"]["role"]["key"] == "cashier"

    # ... but cannot manage staff or create sub-tenants there.
    assert (await client.get("/api/v1/auth/staff", cookies=switched.cookies)).status_code == 403
    denied = await client.post(
        "/api/v1/tenants",
        json={"name": "Nope", "base_currency": "KES"},
        cookies=switched.cookies,
    )
    assert denied.status_code == 403


@pytest.mark.integration
async def test_outsider_cannot_access_foreign_sub_tenant(client):
    owner_a = await _register(client, "A HQ")
    child = (
        await client.post(
            "/api/v1/tenants",
            json={"name": "A Branch", "base_currency": "KES"},
            cookies=owner_a.cookies,
        )
    ).json()

    owner_b = await _register(client, "B HQ")
    denied = await client.post(
        "/api/v1/auth/switch-tenant",
        json={"tenant_id": child["id"]},
        cookies=owner_b.cookies,
    )
    assert denied.status_code == 403
