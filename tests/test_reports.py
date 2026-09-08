"""Integration tests for Phase 2a/2b reports module."""
import uuid
from datetime import date

import pytest


async def _register(client, tenant_name: str = "Reports Cafe"):
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
    name: str = "Tea",
    price_minor: int = 10000,
    stock_quantity: str = "10",
):
    units = await client.get("/api/v1/inventory/units", cookies=cookies)
    kg_id = next(u["id"] for u in units.json() if u["key"] == "kg")
    product = await client.post(
        "/api/v1/inventory/products",
        json={
            "name": name,
            "base_unit_id": kg_id,
            "unit_price_minor": price_minor,
            "currency": "KES",
            "reorder_level_base": "5",
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


async def _complete_sale(client, cookies, product_id, kg_id, quantity: str = "2"):
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
async def test_reports_sales_expenses_and_pnl(client):
    owner = await _register(client)
    cookies = owner.cookies
    product_id, kg_id = await _setup_sellable_product(client, cookies, price_minor=15000)
    sale_total = await _complete_sale(client, cookies, product_id, kg_id)

    utilities_id = (
        await client.post(
            "/api/v1/expenses/categories",
            json={"name": "Utilities"},
            cookies=cookies,
        )
    ).json()["id"]
    supplies_id = (
        await client.post(
            "/api/v1/expenses/categories",
            json={"name": "Supplies"},
            cookies=cookies,
        )
    ).json()["id"]

    today = str(date.today())
    expense_one = await client.post(
        "/api/v1/expenses/expenses",
        json={
            "category_id": utilities_id,
            "amount_minor": 5000,
            "currency": "KES",
            "description": "Electricity",
            "expense_date": today,
        },
        cookies=cookies,
    )
    assert expense_one.status_code == 201
    expense_two = await client.post(
        "/api/v1/expenses/expenses",
        json={
            "category_id": supplies_id,
            "amount_minor": 3000,
            "currency": "KES",
            "description": "Cleaning",
            "expense_date": today,
        },
        cookies=cookies,
    )
    assert expense_two.status_code == 201

    sales = await client.get(
        "/api/v1/reports/sales/summary",
        params={"from": today, "to": today, "group_by": "day"},
        cookies=cookies,
    )
    assert sales.status_code == 200
    sales_body = sales.json()
    assert sales_body["currency"] == "KES"
    assert sales_body["total_minor"] == sale_total
    assert sales_body["order_count"] == 1
    assert sales_body["average_ticket_minor"] == sale_total
    assert len(sales_body["buckets"]) == 1
    assert sales_body["buckets"][0]["total_minor"] == sale_total

    by_category = await client.get(
        "/api/v1/reports/expenses/by-category",
        params={"from": today, "to": today},
        cookies=cookies,
    )
    assert by_category.status_code == 200
    categories = by_category.json()["categories"]
    assert len(categories) == 2
    totals = {row["category_name"]: row["total_minor"] for row in categories}
    assert totals["Utilities"] == 5000
    assert totals["Supplies"] == 3000

    pnl = await client.get(
        "/api/v1/reports/pnl",
        params={"from": today, "to": today},
        cookies=cookies,
    )
    assert pnl.status_code == 200
    pnl_body = pnl.json()
    assert pnl_body["revenue_minor"] == sale_total
    assert pnl_body["expense_minor"] == 8000
    assert pnl_body["net_minor"] == sale_total - 8000
    assert pnl_body["order_count"] == 1
    assert pnl_body["expense_count"] == 2


@pytest.mark.integration
async def test_reports_rejects_invalid_date_range(client):
    owner = await _register(client)
    cookies = owner.cookies
    today = str(date.today())

    denied = await client.get(
        "/api/v1/reports/pnl",
        params={"from": today, "to": "2020-01-01"},
        cookies=cookies,
    )
    assert denied.status_code == 400


@pytest.mark.integration
async def test_cashier_cannot_access_reports(client):
    owner = await _register(client)
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
    denied = await client.get(
        "/api/v1/reports/pnl",
        params={"from": str(date.today()), "to": str(date.today())},
        cookies=cashier_login.cookies,
    )
    assert denied.status_code == 403


@pytest.mark.integration
async def test_reports_sales_by_product_and_payment_method(client):
    owner = await _register(client)
    cookies = owner.cookies
    tea_id, kg_id = await _setup_sellable_product(
        client, cookies, name="Tea", price_minor=15000
    )
    chapati_id, _ = await _setup_sellable_product(
        client, cookies, name="Chapati", price_minor=20000
    )
    tea_total = await _complete_sale(client, cookies, tea_id, kg_id, quantity="2")
    chapati_total = await _complete_sale(client, cookies, chapati_id, kg_id, quantity="1")

    today = str(date.today())
    by_product = await client.get(
        "/api/v1/reports/sales/by-product",
        params={"from": today, "to": today, "sort": "revenue"},
        cookies=cookies,
    )
    assert by_product.status_code == 200
    products = by_product.json()["products"]
    assert len(products) == 2
    assert products[0]["product_name"] == "Tea"
    assert products[0]["total_minor"] == tea_total
    assert products[1]["product_name"] == "Chapati"
    assert products[1]["total_minor"] == chapati_total

    by_method = await client.get(
        "/api/v1/reports/sales/by-payment-method",
        params={"from": today, "to": today},
        cookies=cookies,
    )
    assert by_method.status_code == 200
    methods = by_method.json()["methods"]
    assert len(methods) == 1
    assert methods[0]["method"] == "cash"
    assert methods[0]["total_minor"] == tea_total + chapati_total
    assert methods[0]["payment_count"] == 2


@pytest.mark.integration
async def test_reports_inventory_movements(client):
    owner = await _register(client)
    cookies = owner.cookies
    product_id, kg_id = await _setup_sellable_product(client, cookies, price_minor=10000)
    await _complete_sale(client, cookies, product_id, kg_id, quantity="1")

    today = str(date.today())
    movements = await client.get(
        "/api/v1/reports/inventory/movements",
        params={"from": today, "to": today},
        cookies=cookies,
    )
    assert movements.status_code == 200
    types = {row["movement_type"]: row for row in movements.json()["types"]}
    assert "receipt" in types
    assert "sale" in types
    assert types["receipt"]["movement_count"] == 1
    assert types["sale"]["movement_count"] == 1
    assert float(types["receipt"]["total_quantity_delta_base"]) == 10
    assert float(types["sale"]["total_quantity_delta_base"]) == -1

    sale_only = await client.get(
        "/api/v1/reports/inventory/movements",
        params={"from": today, "to": today, "movement_type": "sale"},
        cookies=cookies,
    )
    assert sale_only.status_code == 200
    sale_types = sale_only.json()["types"]
    assert len(sale_types) == 1
    assert sale_types[0]["movement_type"] == "sale"


@pytest.mark.integration
async def test_report_csv_exports(client):
    owner = await _register(client)
    cookies = owner.cookies
    product_id, kg_id = await _setup_sellable_product(client, cookies, price_minor=12000)
    sale_total = await _complete_sale(client, cookies, product_id, kg_id, quantity="1")

    utilities_id = (
        await client.post(
            "/api/v1/expenses/categories",
            json={"name": "Utilities"},
            cookies=cookies,
        )
    ).json()["id"]
    await client.post(
        "/api/v1/expenses/expenses",
        json={
            "category_id": utilities_id,
            "amount_minor": 4000,
            "currency": "KES",
            "description": "Water",
            "expense_date": str(date.today()),
        },
        cookies=cookies,
    )

    today = str(date.today())
    pnl_csv = await client.get(
        "/api/v1/reports/exports/pnl.csv",
        params={"from": today, "to": today},
        cookies=cookies,
    )
    assert pnl_csv.status_code == 200
    assert pnl_csv.headers["content-type"].startswith("text/csv")
    assert "revenue_minor" in pnl_csv.text
    assert str(sale_total) in pnl_csv.text
    assert "4000" in pnl_csv.text

    product_csv = await client.get(
        "/api/v1/reports/exports/sales-by-product.csv",
        params={"from": today, "to": today},
        cookies=cookies,
    )
    assert product_csv.status_code == 200
    assert "Tea" in product_csv.text

    movements_csv = await client.get(
        "/api/v1/reports/exports/inventory-movements.csv",
        params={"from": today, "to": today},
        cookies=cookies,
    )
    assert movements_csv.status_code == 200
    assert "movement_type" in movements_csv.text
    assert "receipt" in movements_csv.text


@pytest.mark.integration
async def test_report_export_rate_limited():
    from httpx import ASGITransport, AsyncClient

    from app.core.config import Settings, get_settings
    from app.core.db import engine
    from app.core.rate_limit import reset_limiter
    from app.main import create_app

    application = create_app()
    application.dependency_overrides[get_settings] = lambda: Settings(
        rate_limit_enabled=True,
        reports_export_rate_limit_max=1,
        reports_export_rate_limit_window_seconds=60,
    )
    reset_limiter(
        Settings(
            rate_limit_enabled=True,
            reports_export_rate_limit_max=1,
            reports_export_rate_limit_window_seconds=60,
        )
    )

    try:
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://test"
        ) as client:
            owner = await _register(client)
            cookies = owner.cookies
            today = str(date.today())
            params = {"from": today, "to": today}

            first = await client.get(
                "/api/v1/reports/exports/pnl.csv",
                params=params,
                cookies=cookies,
            )
            assert first.status_code == 200

            second = await client.get(
                "/api/v1/reports/exports/pnl.csv",
                params=params,
                cookies=cookies,
            )
            assert second.status_code == 429
    finally:
        reset_limiter(Settings(rate_limit_enabled=False))
        await engine.dispose()
