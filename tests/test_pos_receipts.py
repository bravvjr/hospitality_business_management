"""Integration tests for POS sale receipts."""
import uuid

import pytest


async def _register(client, tenant_name: str = "Receipt Cafe"):
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


async def _complete_sale(client, cookies, product_id, kg_id, *, tendered_minor: int):
    order = await client.post("/api/v1/pos/orders", json={}, cookies=cookies)
    assert order.status_code == 201
    order_id = order.json()["id"]
    added = await client.post(
        f"/api/v1/pos/orders/{order_id}/items",
        json={"product_id": product_id, "quantity": "2", "unit_id": kg_id},
        cookies=cookies,
    )
    assert added.status_code == 201
    completed = await client.post(
        f"/api/v1/pos/orders/{order_id}/complete",
        json={"payment_method": "cash", "amount_tendered_minor": tendered_minor},
        cookies=cookies,
    )
    assert completed.status_code == 200
    return order_id, completed.json()


@pytest.mark.integration
async def test_completed_sale_assigns_receipt_and_reprint(client):
    owner = await _register(client)
    cookies = owner.cookies
    product_id, kg_id = await _setup_sellable_product(client, cookies)

    order_id, completed = await _complete_sale(
        client, cookies, product_id, kg_id, tendered_minor=50000
    )
    assert completed["receipt_number"] == 1
    assert completed["change_minor"] == 20000

    receipt = await client.get(f"/api/v1/pos/orders/{order_id}/receipt", cookies=cookies)
    assert receipt.status_code == 200
    body = receipt.json()
    assert body["receipt_number"] == 1
    assert body["business_name"] == "Receipt Cafe"
    assert body["total_minor"] == 30000
    assert body["payments"][0]["method"] == "cash"
    assert body["payments"][0]["change_minor"] == 20000
    assert len(body["items"]) == 1
    assert body["items"][0]["product_name"] == "Chapati"

    text = await client.get(
        f"/api/v1/pos/orders/{order_id}/receipt.txt", cookies=cookies
    )
    assert text.status_code == 200
    assert "Receipt #1" in text.text
    assert "Chapati" in text.text
    assert "300.00 KES" in text.text
    assert "Change" in text.text


@pytest.mark.integration
async def test_receipt_numbers_increment_per_tenant(client):
    owner = await _register(client)
    cookies = owner.cookies
    product_id, kg_id = await _setup_sellable_product(client, cookies)

    first_id, first = await _complete_sale(
        client, cookies, product_id, kg_id, tendered_minor=30000
    )
    second_id, second = await _complete_sale(
        client, cookies, product_id, kg_id, tendered_minor=30000
    )
    assert first["receipt_number"] == 1
    assert second["receipt_number"] == 2

    reprint = await client.get(f"/api/v1/pos/orders/{first_id}/receipt", cookies=cookies)
    assert reprint.json()["receipt_number"] == 1
    reprint_two = await client.get(
        f"/api/v1/pos/orders/{second_id}/receipt", cookies=cookies
    )
    assert reprint_two.json()["receipt_number"] == 2


@pytest.mark.integration
async def test_open_order_has_no_receipt(client):
    owner = await _register(client)
    cookies = owner.cookies
    product_id, kg_id = await _setup_sellable_product(client, cookies)

    order = await client.post("/api/v1/pos/orders", json={}, cookies=cookies)
    order_id = order.json()["id"]
    await client.post(
        f"/api/v1/pos/orders/{order_id}/items",
        json={"product_id": product_id, "quantity": "1", "unit_id": kg_id},
        cookies=cookies,
    )

    denied = await client.get(f"/api/v1/pos/orders/{order_id}/receipt", cookies=cookies)
    assert denied.status_code == 400
