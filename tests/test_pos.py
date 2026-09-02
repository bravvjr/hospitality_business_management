"""Integration tests for Phase 1 POS / sales (ADR-006)."""
import uuid
from decimal import Decimal

import pytest


async def _register(client, tenant_name: str = "POS Cafe"):
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


async def _setup_sellable_product(client, cookies, *, price_minor: int = 15000):
    units = await client.get("/api/v1/inventory/units", cookies=cookies)
    kg_id = next(u["id"] for u in units.json() if u["key"] == "kg")
    product = await client.post(
        "/api/v1/inventory/products",
        json={
            "name": "Chapati",
            "base_unit_id": kg_id,
            "unit_price_minor": price_minor,
            "currency": "KES",
            "reorder_level_base": "1",
        },
        cookies=cookies,
    )
    assert product.status_code == 201
    product_id = product.json()["id"]

    # Stock in enough to sell.
    receipt = await client.post(
        "/api/v1/inventory/stock/receipts",
        json={
            "product_id": product_id,
            "quantity": "10",
            "unit_id": kg_id,
            "reason": "purchase",
        },
        cookies=cookies,
    )
    assert receipt.status_code == 201
    return product_id, kg_id


@pytest.mark.integration
async def test_pos_sale_flow_cash_and_stock_deduction(client):
    owner = await _register(client)
    cookies = owner.cookies
    product_id, kg_id = await _setup_sellable_product(client, cookies, price_minor=20000)

    order = await client.post("/api/v1/pos/orders", json={}, cookies=cookies)
    assert order.status_code == 201
    assert order.json()["status"] == "open"
    order_id = order.json()["id"]

    # Add 2 units @ 200.00 KES = 40000
    added = await client.post(
        f"/api/v1/pos/orders/{order_id}/items",
        json={"product_id": product_id, "quantity": "2", "unit_id": kg_id},
        cookies=cookies,
    )
    assert added.status_code == 201
    assert added.json()["total_minor"] == 40000
    assert len(added.json()["items"]) == 1
    item_id = added.json()["items"][0]["id"]

    # Change qty to 3 → 60000
    updated = await client.patch(
        f"/api/v1/pos/orders/{order_id}/items/{item_id}",
        json={"quantity": "3"},
        cookies=cookies,
    )
    assert updated.status_code == 200
    assert updated.json()["total_minor"] == 60000

    # Add same product again merges lines → 4
    merged = await client.post(
        f"/api/v1/pos/orders/{order_id}/items",
        json={"product_id": product_id, "quantity": "1", "unit_id": kg_id},
        cookies=cookies,
    )
    assert merged.status_code == 201
    assert len(merged.json()["items"]) == 1
    assert Decimal(merged.json()["items"][0]["quantity"]) == Decimal("4")
    assert merged.json()["total_minor"] == 80000

    completed = await client.post(
        f"/api/v1/pos/orders/{order_id}/complete",
        json={"payment_method": "cash", "amount_tendered_minor": 100000},
        cookies=cookies,
    )
    assert completed.status_code == 200
    body = completed.json()
    assert body["status"] == "completed"
    assert body["payments"][0]["method"] == "cash"
    assert body["payments"][0]["amount_minor"] == 100000

    levels = await client.get("/api/v1/inventory/stock/levels", cookies=cookies)
    level = next(row for row in levels.json()["items"] if row["product_id"] == product_id)
    assert Decimal(level["quantity_base"]) == Decimal("6")  # 10 - 4

    history = await client.get("/api/v1/pos/orders?status=completed", cookies=cookies)
    assert history.status_code == 200
    assert any(o["id"] == order_id for o in history.json()["items"])


@pytest.mark.integration
async def test_remove_item_and_reject_empty_complete(client):
    owner = await _register(client)
    cookies = owner.cookies
    product_id, kg_id = await _setup_sellable_product(client, cookies)

    order = (await client.post("/api/v1/pos/orders", json={}, cookies=cookies)).json()
    order_id = order["id"]
    added = await client.post(
        f"/api/v1/pos/orders/{order_id}/items",
        json={"product_id": product_id, "quantity": "1", "unit_id": kg_id},
        cookies=cookies,
    )
    item_id = added.json()["items"][0]["id"]

    removed = await client.delete(
        f"/api/v1/pos/orders/{order_id}/items/{item_id}",
        cookies=cookies,
    )
    assert removed.status_code == 200
    assert removed.json()["items"] == []
    assert removed.json()["total_minor"] == 0

    denied = await client.post(
        f"/api/v1/pos/orders/{order_id}/complete",
        json={"payment_method": "cash"},
        cookies=cookies,
    )
    assert denied.status_code == 400


@pytest.mark.integration
async def test_insufficient_stock_blocks_sale(client):
    owner = await _register(client)
    cookies = owner.cookies
    units = await client.get("/api/v1/inventory/units", cookies=cookies)
    kg_id = next(u["id"] for u in units.json() if u["key"] == "kg")
    product = await client.post(
        "/api/v1/inventory/products",
        json={
            "name": "Juice",
            "base_unit_id": kg_id,
            "unit_price_minor": 5000,
            "currency": "KES",
        },
        cookies=cookies,
    )
    product_id = product.json()["id"]
    # No stock receipt.

    order = (await client.post("/api/v1/pos/orders", json={}, cookies=cookies)).json()
    await client.post(
        f"/api/v1/pos/orders/{order['id']}/items",
        json={"product_id": product_id, "quantity": "1", "unit_id": kg_id},
        cookies=cookies,
    )
    denied = await client.post(
        f"/api/v1/pos/orders/{order['id']}/complete",
        json={"payment_method": "cash"},
        cookies=cookies,
    )
    assert denied.status_code == 400


@pytest.mark.integration
async def test_mpesa_not_enabled_yet(client):
    owner = await _register(client)
    cookies = owner.cookies
    product_id, kg_id = await _setup_sellable_product(client, cookies)
    order = (await client.post("/api/v1/pos/orders", json={}, cookies=cookies)).json()
    await client.post(
        f"/api/v1/pos/orders/{order['id']}/items",
        json={"product_id": product_id, "quantity": "1", "unit_id": kg_id},
        cookies=cookies,
    )
    denied = await client.post(
        f"/api/v1/pos/orders/{order['id']}/complete",
        json={"payment_method": "mpesa"},
        cookies=cookies,
    )
    assert denied.status_code == 400
