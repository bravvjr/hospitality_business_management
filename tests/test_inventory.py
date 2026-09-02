"""Integration tests for Phase 1 inventory ledger (ADR-005)."""
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.core.db import SessionLocal, apply_tenant_context


async def _register_owner(client, *, tenant_name: str = "Inventory Cafe"):
    email = f"owner-{uuid.uuid4()}@example.com"
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "secure-pass-123",
            "tenant_name": tenant_name,
            "base_currency": "KES",
        },
    )
    assert response.status_code == 201
    return response


async def _kg_unit_id(client, cookies) -> tuple[str, str]:
    units = await client.get("/api/v1/inventory/units", cookies=cookies)
    assert units.status_code == 200
    by_key = {u["key"]: u["id"] for u in units.json()}
    assert "kg" in by_key
    assert "g" in by_key
    return by_key["kg"], by_key["g"]

@pytest.mark.integration
async def test_product_crud_and_uom_conversion(client):
    owner = await _register_owner(client)
    cookies = owner.cookies
    kg_id, g_id = await _kg_unit_id(client, cookies)

    created = await client.post(
        "/api/v1/inventory/products",
        json={
            "name": "Flour",
            "sku": "FLR-001",
            "category": "Dry goods",
            "base_unit_id": kg_id,
            "reorder_level_base": "5",
        },
        cookies=cookies,
    )
    assert created.status_code == 201
    product = created.json()
    assert product["name"] == "Flour"
    assert product["base_unit"]["key"] == "kg"
    product_id = product["id"]

    # Base unit conversion auto-created.
    units = await client.get(
        f"/api/v1/inventory/products/{product_id}/units", cookies=cookies
    )
    assert units.status_code == 200
    assert any(u["unit"]["key"] == "kg" and u["to_base_factor"] == "1.000000" for u in units.json())

    # Add gram conversion: 1000 g = 1 kg → factor 0.001
    added = await client.post(
        f"/api/v1/inventory/products/{product_id}/units",
        json={"unit_id": g_id, "to_base_factor": "0.001", "is_purchase": True},
        cookies=cookies,
    )
    assert added.status_code == 201
    assert Decimal(added.json()["to_base_factor"]) == Decimal("0.001")


@pytest.mark.integration
async def test_stock_receipt_usage_adjustment_and_low_stock(client):
    owner = await _register_owner(client)
    cookies = owner.cookies
    kg_id, g_id = await _kg_unit_id(client, cookies)

    product = (
        await client.post(
            "/api/v1/inventory/products",
            json={
                "name": "Sugar",
                "base_unit_id": kg_id,
                "reorder_level_base": "10",
            },
            cookies=cookies,
        )
    ).json()
    product_id = product["id"]

    await client.post(
        f"/api/v1/inventory/products/{product_id}/units",
        json={"unit_id": g_id, "to_base_factor": "0.001", "is_purchase": True},
        cookies=cookies,
    )

    # Stock in 2 sacks worth via kg.
    receipt = await client.post(
        "/api/v1/inventory/stock/receipts",
        json={
            "product_id": product_id,
            "quantity": "20",
            "unit_id": kg_id,
            "reason": "purchase",
            "idempotency_key": f"recv-{uuid.uuid4()}",
        },
        cookies=cookies,
    )
    assert receipt.status_code == 201
    assert Decimal(receipt.json()["quantity_delta_base"]) == Decimal("20")

    # Idempotent replay returns same movement.
    replay = await client.post(
        "/api/v1/inventory/stock/receipts",
        json={
            "product_id": product_id,
            "quantity": "20",
            "unit_id": kg_id,
            "reason": "purchase",
            "idempotency_key": receipt.json()["idempotency_key"],
        },
        cookies=cookies,
    )
    assert replay.status_code == 201
    assert replay.json()["id"] == receipt.json()["id"]

    # Use 500 g → -0.5 kg
    usage = await client.post(
        "/api/v1/inventory/stock/usages",
        json={
            "product_id": product_id,
            "quantity": "500",
            "unit_id": g_id,
            "reason": "kitchen_use",
        },
        cookies=cookies,
    )
    assert usage.status_code == 201
    assert Decimal(usage.json()["quantity_delta_base"]) == Decimal("-0.500000")

    levels = await client.get("/api/v1/inventory/stock/levels", cookies=cookies)
    assert levels.status_code == 200
    level = next(row for row in levels.json()["items"] if row["product_id"] == product_id)
    assert Decimal(level["quantity_base"]) == Decimal("19.500000")
    assert level["is_low_stock"] is False

    # Adjust down below reorder.
    adjust = await client.post(
        "/api/v1/inventory/stock/adjustments",
        json={
            "product_id": product_id,
            "quantity": "-15",
            "unit_id": kg_id,
            "reason": "count_correction",
        },
        cookies=cookies,
    )
    assert adjust.status_code == 201

    low = await client.get("/api/v1/inventory/stock/levels/low", cookies=cookies)
    assert low.status_code == 200
    assert any(row["product_id"] == product_id for row in low.json()["items"])

    history = await client.get(
        f"/api/v1/inventory/stock/movements?product_id={product_id}",
        cookies=cookies,
    )
    assert history.status_code == 200
    assert history.json()["total"] >= 3
    assert len(history.json()["items"]) >= 3


@pytest.mark.integration
async def test_insufficient_stock_rejected(client):
    owner = await _register_owner(client)
    cookies = owner.cookies
    kg_id, _ = await _kg_unit_id(client, cookies)

    product = (
        await client.post(
            "/api/v1/inventory/products",
            json={"name": "Milk", "base_unit_id": kg_id},
            cookies=cookies,
        )
    ).json()

    denied = await client.post(
        "/api/v1/inventory/stock/usages",
        json={
            "product_id": product["id"],
            "quantity": "1",
            "unit_id": kg_id,
            "reason": "usage",
        },
        cookies=cookies,
    )
    assert denied.status_code == 400


@pytest.mark.integration
async def test_cross_tenant_inventory_isolation(client):
    owner_a = await _register_owner(client, tenant_name="Tenant A")
    owner_b = await _register_owner(client, tenant_name="Tenant B")
    kg_id, _ = await _kg_unit_id(client, owner_a.cookies)

    product_a = (
        await client.post(
            "/api/v1/inventory/products",
            json={"name": "Secret Flour", "base_unit_id": kg_id},
            cookies=owner_a.cookies,
        )
    ).json()

    # B cannot see A's product.
    missing = await client.get(
        f"/api/v1/inventory/products/{product_a['id']}",
        cookies=owner_b.cookies,
    )
    assert missing.status_code == 404

    # DB-layer RLS backstop on products.
    async with SessionLocal() as session:
        await apply_tenant_context(session, uuid.UUID(owner_b.json()["tenant"]["id"]))
        result = await session.execute(
            text("SELECT count(*) FROM products WHERE id = :id"),
            {"id": product_a["id"]},
        )
        assert result.scalar_one() == 0
