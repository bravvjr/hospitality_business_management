"""Cross-tenant isolation tests (ADR-002 / ADR-010).

Covers both layers of defense-in-depth:
- API/service layer: a tenant cannot see or mutate another tenant's staff.
- Database layer: PostgreSQL RLS filters `memberships` by the active tenant GUC,
  so even a raw query cannot read another tenant's rows.
"""
import uuid

import pytest
from sqlalchemy import text

from app.core.db import SessionLocal, apply_tenant_context


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
async def test_api_layer_cross_tenant_isolation(client):
    owner_a = await _register(client, "Tenant A")
    owner_b = await _register(client, "Tenant B")

    tenant_a = owner_a.json()["tenant"]["id"]
    tenant_b = owner_b.json()["tenant"]["id"]
    assert tenant_a != tenant_b

    # A adds a cashier to its own tenant.
    add = await client.post(
        "/api/v1/auth/staff",
        json={
            "email": f"cashier-{uuid.uuid4()}@example.com",
            "password": "cashier-pass-123",
            "role_key": "cashier",
        },
        cookies=owner_a.cookies,
    )
    assert add.status_code == 201

    # A sees exactly its own 2 members; B sees only its 1.
    staff_a = (await client.get("/api/v1/auth/staff", cookies=owner_a.cookies)).json()[
        "items"
    ]
    staff_b = (await client.get("/api/v1/auth/staff", cookies=owner_b.cookies)).json()[
        "items"
    ]
    assert len(staff_a) == 2
    assert len(staff_b) == 1

    a_membership_ids = {m["membership"]["id"] for m in staff_a}
    b_membership_ids = {m["membership"]["id"] for m in staff_b}
    assert a_membership_ids.isdisjoint(b_membership_ids)

    # A cannot touch B's membership.
    b_membership_id = owner_b.json()["membership"]["id"]
    patch = await client.patch(
        f"/api/v1/auth/staff/{b_membership_id}",
        json={"role_key": "cashier"},
        cookies=owner_a.cookies,
    )
    assert patch.status_code == 404
    delete = await client.delete(
        f"/api/v1/auth/staff/{b_membership_id}",
        cookies=owner_a.cookies,
    )
    assert delete.status_code == 404


@pytest.mark.integration
async def test_db_layer_rls_filters_memberships(client):
    owner_a = await _register(client, "RLS Tenant A")
    owner_b = await _register(client, "RLS Tenant B")
    tenant_a = uuid.UUID(owner_a.json()["tenant"]["id"])
    tenant_b = uuid.UUID(owner_b.json()["tenant"]["id"])

    # With tenant A's context set, a raw membership query returns only A's rows.
    async with SessionLocal() as session:
        await apply_tenant_context(session, tenant_a)
        rows = (await session.execute(text("SELECT tenant_id FROM memberships"))).scalars().all()
    assert rows, "expected at least tenant A's own membership"
    assert all(str(t) == str(tenant_a) for t in rows)
    assert all(str(t) != str(tenant_b) for t in rows)

    # Switching context to B yields a disjoint set (B's rows only).
    async with SessionLocal() as session:
        await apply_tenant_context(session, tenant_b)
        rows_b = (await session.execute(text("SELECT tenant_id FROM memberships"))).scalars().all()
    assert rows_b
    assert all(str(t) == str(tenant_b) for t in rows_b)
