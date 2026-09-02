"""Offset pagination envelope on high-volume list endpoints."""
import uuid

import pytest


async def _register_owner(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"owner-{uuid.uuid4()}@example.com",
            "password": "secure-pass-123",
            "tenant_name": "Pagination Cafe",
            "base_currency": "KES",
        },
    )
    assert response.status_code == 201
    return response


@pytest.mark.integration
async def test_products_offset_pagination(client):
    owner = await _register_owner(client)
    cookies = owner.cookies

    units = await client.get("/api/v1/inventory/units", cookies=cookies)
    kg_id = next(u["id"] for u in units.json() if u["key"] == "kg")

    for i in range(3):
        created = await client.post(
            "/api/v1/inventory/products",
            json={
                "name": f"Product {i}",
                "sku": f"PAG-{i}",
                "base_unit_id": kg_id,
            },
            cookies=cookies,
        )
        assert created.status_code == 201

    page1 = await client.get(
        "/api/v1/inventory/products?limit=2&offset=0", cookies=cookies
    )
    assert page1.status_code == 200
    body1 = page1.json()
    assert body1["total"] == 3
    assert body1["limit"] == 2
    assert body1["offset"] == 0
    assert len(body1["items"]) == 2

    page2 = await client.get(
        "/api/v1/inventory/products?limit=2&offset=2", cookies=cookies
    )
    assert page2.status_code == 200
    body2 = page2.json()
    assert body2["total"] == 3
    assert body2["offset"] == 2
    assert len(body2["items"]) == 1

    ids = {item["id"] for item in body1["items"]} | {item["id"] for item in body2["items"]}
    assert len(ids) == 3

    bad = await client.get(
        "/api/v1/inventory/products?limit=0", cookies=cookies
    )
    assert bad.status_code == 422
