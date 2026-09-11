"""Integration tests for Phase 2a recipes / BOM module."""
import uuid

import pytest


async def _register(client, tenant_name: str = "Recipe Kitchen"):
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


async def _create_product(
    client,
    cookies,
    *,
    name: str,
    unit_key: str = "kg",
    price_minor: int | None = None,
):
    units = await client.get("/api/v1/inventory/units", cookies=cookies)
    unit_id = next(u["id"] for u in units.json() if u["key"] == unit_key)
    payload = {
        "name": name,
        "base_unit_id": unit_id,
    }
    if price_minor is not None:
        payload["unit_price_minor"] = price_minor
        payload["currency"] = "KES"
    product = await client.post(
        "/api/v1/inventory/products",
        json=payload,
        cookies=cookies,
    )
    assert product.status_code == 201
    return product.json()["id"], unit_id


@pytest.mark.integration
async def test_recipe_crud_and_items(client):
    owner = await _register(client)
    cookies = owner.cookies

    meal_id, kg_id = await _create_product(
        client, cookies, name="Burger Meal", price_minor=50000
    )
    flour_id, _ = await _create_product(client, cookies, name="Flour")
    beef_id, _ = await _create_product(client, cookies, name="Beef Patty")

    created = await client.post(
        "/api/v1/recipes",
        json={
            "product_id": meal_id,
            "yields_quantity": "1",
            "notes": "House burger",
            "items": [
                {
                    "ingredient_product_id": flour_id,
                    "quantity": "0.1",
                    "unit_id": kg_id,
                },
                {
                    "ingredient_product_id": beef_id,
                    "quantity": "0.2",
                    "unit_id": kg_id,
                },
            ],
        },
        cookies=cookies,
    )
    assert created.status_code == 201
    recipe = created.json()
    assert recipe["product_id"] == meal_id
    assert recipe["product"]["name"] == "Burger Meal"
    assert len(recipe["items"]) == 2
    recipe_id = recipe["id"]

    listed = await client.get("/api/v1/recipes", cookies=cookies)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["item_count"] == 2

    fetched = await client.get(f"/api/v1/recipes/{recipe_id}", cookies=cookies)
    assert fetched.status_code == 200
    assert fetched.json()["notes"] == "House burger"

    updated = await client.patch(
        f"/api/v1/recipes/{recipe_id}",
        json={"notes": "Updated burger recipe"},
        cookies=cookies,
    )
    assert updated.status_code == 200
    assert updated.json()["notes"] == "Updated burger recipe"

    duplicate = await client.post(
        "/api/v1/recipes",
        json={"product_id": meal_id, "items": []},
        cookies=cookies,
    )
    assert duplicate.status_code == 400

    cheese_id, _ = await _create_product(client, cookies, name="Cheese")
    added_item = await client.post(
        f"/api/v1/recipes/{recipe_id}/items",
        json={
            "ingredient_product_id": cheese_id,
            "quantity": "0.05",
            "unit_id": kg_id,
        },
        cookies=cookies,
    )
    assert added_item.status_code == 201

    item_id = added_item.json()["id"]
    patched_item = await client.patch(
        f"/api/v1/recipes/{recipe_id}/items/{item_id}",
        json={"quantity": "0.06"},
        cookies=cookies,
    )
    assert patched_item.status_code == 200
    assert patched_item.json()["quantity"] == "0.06"

    deleted_item = await client.delete(
        f"/api/v1/recipes/{recipe_id}/items/{item_id}",
        cookies=cookies,
    )
    assert deleted_item.status_code == 204

    deleted = await client.delete(f"/api/v1/recipes/{recipe_id}", cookies=cookies)
    assert deleted.status_code == 204

    missing = await client.get(f"/api/v1/recipes/{recipe_id}", cookies=cookies)
    assert missing.status_code == 404


@pytest.mark.integration
async def test_recipe_rejects_meal_as_ingredient(client):
    owner = await _register(client)
    cookies = owner.cookies
    meal_id, kg_id = await _create_product(
        client, cookies, name="Pizza", price_minor=12000
    )

    response = await client.post(
        "/api/v1/recipes",
        json={
            "product_id": meal_id,
            "items": [
                {
                    "ingredient_product_id": meal_id,
                    "quantity": "1",
                    "unit_id": kg_id,
                }
            ],
        },
        cookies=cookies,
    )
    assert response.status_code == 400
