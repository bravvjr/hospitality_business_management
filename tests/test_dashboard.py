"""Integration tests for Phase 1 dashboard KPIs."""
import uuid
from datetime import date

import pytest


async def _register(client, tenant_name: str = "Dashboard Cafe"):
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


async def _setup_sellable_product(
    client,
    cookies,
    *,
    price_minor: int = 10000,
    stock_quantity: str = "10",
    reorder_level_base: str = "5",
):
    units = await client.get("/api/v1/inventory/units", cookies=cookies)
    kg_id = next(u["id"] for u in units.json() if u["key"] == "kg")
    product = await client.post(
        "/api/v1/inventory/products",
        json={
            "name": "Tea",
            "base_unit_id": kg_id,
            "unit_price_minor": price_minor,
            "currency": "KES",
            "reorder_level_base": reorder_level_base,
        },
        cookies=cookies,
    )
    assert product.status_code == 201
    product_id = product.json()["id"]
    receipt = await client.post(
        "/api/v1/inventory/stock/receipts",
        json={
            "product_id": product_id,
            "quantity": stock_quantity,
            "unit_id": kg_id,
            "reason": "purchase",
        },
        cookies=cookies,
    )
    assert receipt.status_code == 201
    return product_id, kg_id


async def _complete_sale(client, cookies, product_id, kg_id, quantity: str = "6"):
    order = await client.post("/api/v1/pos/orders", json={}, cookies=cookies)
    assert order.status_code == 201
    order_id = order.json()["id"]
    added = await client.post(
        f"/api/v1/pos/orders/{order_id}/items",
        json={"product_id": product_id, "quantity": quantity, "unit_id": kg_id},
        cookies=cookies,
    )
    assert added.status_code == 201
    total_minor = added.json()["total_minor"]
    completed = await client.post(
        f"/api/v1/pos/orders/{order_id}/complete",
        json={"payment_method": "cash", "amount_tendered_minor": total_minor},
        cookies=cookies,
    )
    assert completed.status_code == 200
    return total_minor


@pytest.mark.integration
async def test_dashboard_summary_and_recent(client):
    owner = await _register(client)
    cookies = owner.cookies
    product_id, kg_id = await _setup_sellable_product(client, cookies, price_minor=15000)

    sale_total = await _complete_sale(client, cookies, product_id, kg_id)

    category_id = (
        await client.post(
            "/api/v1/expenses/categories",
            json={"name": "Utilities"},
            cookies=cookies,
        )
    ).json()["id"]
    expense = await client.post(
        "/api/v1/expenses/expenses",
        json={
            "category_id": category_id,
            "amount_minor": 5000,
            "currency": "KES",
            "description": "Electricity",
            "expense_date": str(date.today()),
        },
        cookies=cookies,
    )
    assert expense.status_code == 201

    summary = await client.get(
        "/api/v1/dashboard/summary",
        params={"date": str(date.today())},
        cookies=cookies,
    )
    assert summary.status_code == 200
    body = summary.json()
    assert body["currency"] == "KES"
    assert body["sales_total_minor"] == sale_total
    assert body["sales_count"] == 1
    assert body["expenses_total_minor"] == 5000
    assert body["expenses_count"] == 1
    assert body["net_position_minor"] == sale_total - 5000
    assert body["low_stock_count"] == 1

    recent = await client.get("/api/v1/dashboard/recent", cookies=cookies)
    assert recent.status_code == 200
    recent_body = recent.json()
    assert len(recent_body["sales"]) == 1
    assert recent_body["sales"][0]["total_minor"] == sale_total
    assert len(recent_body["expenses"]) == 1
    assert recent_body["expenses"][0]["description"] == "Electricity"


@pytest.mark.integration
async def test_dashboard_low_stock_list(client):
    owner = await _register(client)
    cookies = owner.cookies
    await _setup_sellable_product(client, cookies, stock_quantity="1")

    low_stock = await client.get("/api/v1/dashboard/low-stock", cookies=cookies)
    assert low_stock.status_code == 200
    items = low_stock.json()
    assert len(items) == 1
    assert items[0]["product_name"] == "Tea"
    assert items[0]["unit_symbol"] == "kg"


@pytest.mark.integration
async def test_kitchen_role_cannot_access_dashboard(client):
    owner = await _register(client)
    kitchen_email = f"kitchen-{uuid.uuid4()}@example.com"
    await client.post(
        "/api/v1/auth/staff",
        json={"email": kitchen_email, "password": "kitchen-pass-123", "role_key": "kitchen"},
        cookies=owner.cookies,
    )
    kitchen_login = await client.post(
        "/api/v1/auth/login",
        json={"email": kitchen_email, "password": "kitchen-pass-123"},
    )
    denied = await client.get("/api/v1/dashboard/summary", cookies=kitchen_login.cookies)
    assert denied.status_code == 403
