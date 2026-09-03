"""Integration tests for Phase 1 expenses module."""
import uuid
from datetime import date

import pytest
from sqlalchemy import text

from app.core.db import SessionLocal, apply_tenant_context


async def _register_owner(client, *, tenant_name: str = "Expense Cafe"):
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


@pytest.mark.integration
async def test_category_and_expense_crud(client):
    owner = await _register_owner(client)
    cookies = owner.cookies

    category = await client.post(
        "/api/v1/expenses/categories",
        json={"name": "Supplies"},
        cookies=cookies,
    )
    assert category.status_code == 201
    category_id = category.json()["id"]

    dup = await client.post(
        "/api/v1/expenses/categories",
        json={"name": "Supplies"},
        cookies=cookies,
    )
    assert dup.status_code == 400

    expense = await client.post(
        "/api/v1/expenses/expenses",
        json={
            "category_id": category_id,
            "amount_minor": 250000,
            "currency": "KES",
            "description": "Cleaning supplies",
            "expense_date": "2026-09-01",
            "note": "Monthly restock",
        },
        cookies=cookies,
    )
    assert expense.status_code == 201
    body = expense.json()
    assert body["amount_minor"] == 250000
    assert body["category"]["name"] == "Supplies"
    assert body["recorded_by_user_id"] == owner.json()["user"]["id"]
    expense_id = body["id"]

    listed = await client.get("/api/v1/expenses/expenses", cookies=cookies)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    fetched = await client.get(f"/api/v1/expenses/expenses/{expense_id}", cookies=cookies)
    assert fetched.status_code == 200
    assert fetched.json()["description"] == "Cleaning supplies"

    updated = await client.patch(
        f"/api/v1/expenses/expenses/{expense_id}",
        json={"description": "Cleaning supplies (updated)"},
        cookies=cookies,
    )
    assert updated.status_code == 200
    assert updated.json()["description"] == "Cleaning supplies (updated)"


@pytest.mark.integration
async def test_expense_summary(client):
    owner = await _register_owner(client)
    cookies = owner.cookies

    category_id = (
        await client.post(
            "/api/v1/expenses/categories",
            json={"name": "Utilities"},
            cookies=cookies,
        )
    ).json()["id"]

    for amount in (10000, 20000):
        resp = await client.post(
            "/api/v1/expenses/expenses",
            json={
                "category_id": category_id,
                "amount_minor": amount,
                "currency": "KES",
                "description": f"Bill {amount}",
                "expense_date": "2026-09-02",
            },
            cookies=cookies,
        )
        assert resp.status_code == 201

    summary = await client.get(
        "/api/v1/expenses/summary",
        params={"from": "2026-09-01", "to": "2026-09-30"},
        cookies=cookies,
    )
    assert summary.status_code == 200
    data = summary.json()
    assert data["currency"] == "KES"
    assert data["total_minor"] == 30000
    assert data["expense_count"] == 2


@pytest.mark.integration
async def test_expenses_blocked_without_finance_entitlement(client):
    owner = await _register_owner(client)
    tenant_id = uuid.UUID(owner.json()["tenant"]["id"])

    from app.modules.tenant.entitlements import FINANCE
    from app.modules.tenant.models import TenantEntitlement

    async with SessionLocal() as session:
        await apply_tenant_context(session, tenant_id)
        entitlement = await session.get(TenantEntitlement, (tenant_id, FINANCE))
        assert entitlement is not None
        entitlement.enabled = False
        await session.commit()

    denied = await client.get("/api/v1/expenses/categories", cookies=owner.cookies)
    assert denied.status_code == 403


@pytest.mark.integration
async def test_cross_tenant_expense_isolation(client):
    owner_a = await _register_owner(client, tenant_name="A Expenses")
    owner_b = await _register_owner(client, tenant_name="B Expenses")

    category_id = (
        await client.post(
            "/api/v1/expenses/categories",
            json={"name": "Rent"},
            cookies=owner_a.cookies,
        )
    ).json()["id"]

    expense_id = (
        await client.post(
            "/api/v1/expenses/expenses",
            json={
                "category_id": category_id,
                "amount_minor": 500000,
                "currency": "KES",
                "description": "Shop rent",
                "expense_date": str(date.today()),
            },
            cookies=owner_a.cookies,
        )
    ).json()["id"]

    denied = await client.get(
        f"/api/v1/expenses/expenses/{expense_id}",
        cookies=owner_b.cookies,
    )
    assert denied.status_code == 404

    async with SessionLocal() as session:
        await apply_tenant_context(session, uuid.UUID(owner_b.json()["tenant"]["id"]))
        result = await session.execute(
            text("SELECT count(*) FROM expenses WHERE id = :id"),
            {"id": expense_id},
        )
        assert result.scalar_one() == 0
