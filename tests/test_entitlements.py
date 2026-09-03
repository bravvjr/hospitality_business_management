"""Tenant module entitlement tests (ADR-012 subproducts)."""
import uuid

import pytest

from app.core.db import SessionLocal, apply_tenant_context
from app.modules.tenant.entitlements import INVENTORY
from app.modules.tenant.models import TenantEntitlement
from app.modules.tenant.repository import TenantRepository


async def _register(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"owner-{uuid.uuid4()}@example.com",
            "password": "secure-pass-123",
            "tenant_name": "Entitlement Cafe",
        },
    )
    assert resp.status_code == 201
    return resp


@pytest.mark.integration
async def test_register_grants_default_entitlements(client):
    reg = await _register(client)
    tenant_id = uuid.UUID(reg.json()["tenant"]["id"])

    async with SessionLocal() as session:
        await apply_tenant_context(session, tenant_id)
        repo = TenantRepository(session)
        assert await repo.is_module_enabled(tenant_id=tenant_id, module_key="inventory")
        assert await repo.is_module_enabled(tenant_id=tenant_id, module_key="pos")


@pytest.mark.integration
async def test_inventory_blocked_when_module_disabled(client):
    reg = await _register(client)
    tenant_id = uuid.UUID(reg.json()["tenant"]["id"])

    async with SessionLocal() as session:
        await apply_tenant_context(session, tenant_id)
        entitlement = await session.get(TenantEntitlement, (tenant_id, INVENTORY))
        assert entitlement is not None
        entitlement.enabled = False
        await session.commit()

    denied = await client.get("/api/v1/inventory/units", cookies=reg.cookies)
    assert denied.status_code == 403
    assert denied.json()["detail"] == "Module not enabled for this tenant"
