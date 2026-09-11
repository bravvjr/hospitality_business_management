"""Integration tests for Phase 2a recipes / BOM module and Phase 2b POS consumption."""
import uuid
from decimal import Decimal

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


async def _stock_in(client, cookies, product_id, unit_id, quantity: str):
    receipt = await client.post(
        "/api/v1/inventory/stock/receipts",
        json={
            "product_id": product_id,
            "quantity": quantity,
            "unit_id": unit_id,
            "reason": "purchase",
        },
        cookies=cookies,
    )
    assert receipt.status_code == 201


async def _level_base(client, cookies, product_id) -> Decimal:
    levels = await client.get("/api/v1/inventory/stock/levels", cookies=cookies)
    assert levels.status_code == 200
    row = next(r for r in levels.json()["items"] if r["product_id"] == product_id)
    return Decimal(row["quantity_base"])


@pytest.mark.integration
async def test_sale_with_recipe_deducts_ingredients_not_meal(client):
    owner = await _register(client)
    cookies = owner.cookies

    meal_id, kg_id = await _create_product(
        client, cookies, name="Burger Meal", price_minor=50000
    )
    flour_id, _ = await _create_product(client, cookies, name="Flour")
    beef_id, _ = await _create_product(client, cookies, name="Beef Patty")

    await _stock_in(client, cookies, flour_id, kg_id, "10")
    await _stock_in(client, cookies, beef_id, kg_id, "10")

    recipe = await client.post(
        "/api/v1/recipes",
        json={
            "product_id": meal_id,
            "yields_quantity": "1",
            "items": [
                {"ingredient_product_id": flour_id, "quantity": "0.1", "unit_id": kg_id},
                {"ingredient_product_id": beef_id, "quantity": "0.2", "unit_id": kg_id},
            ],
        },
        cookies=cookies,
    )
    assert recipe.status_code == 201

    order = await client.post("/api/v1/pos/orders", json={}, cookies=cookies)
    order_id = order.json()["id"]
    await client.post(
        f"/api/v1/pos/orders/{order_id}/items",
        json={"product_id": meal_id, "quantity": "2", "unit_id": kg_id},
        cookies=cookies,
    )

    completed = await client.post(
        f"/api/v1/pos/orders/{order_id}/complete",
        json={"payment_method": "cash"},
        cookies=cookies,
    )
    assert completed.status_code == 200

    # Meal has no stock receipt; ingredients are consumed instead.
    flour_level = await _level_base(client, cookies, flour_id)
    beef_level = await _level_base(client, cookies, beef_id)
    assert flour_level == Decimal("9.8")  # 10 - (0.1 * 2)
    assert beef_level == Decimal("9.6")  # 10 - (0.2 * 2)

    levels_resp = await client.get("/api/v1/inventory/stock/levels", cookies=cookies)
    meal_levels = [r for r in levels_resp.json()["items"] if r["product_id"] == meal_id]
    assert len(meal_levels) == 1
    assert Decimal(meal_levels[0]["quantity_base"]) == Decimal("0")


@pytest.mark.integration
async def test_insufficient_ingredient_blocks_recipe_sale(client):
    owner = await _register(client)
    cookies = owner.cookies

    meal_id, kg_id = await _create_product(
        client, cookies, name="Pasta Bowl", price_minor=30000
    )
    pasta_id, _ = await _create_product(client, cookies, name="Pasta")
    sauce_id, _ = await _create_product(client, cookies, name="Sauce")

    await _stock_in(client, cookies, pasta_id, kg_id, "0.5")
    await _stock_in(client, cookies, sauce_id, kg_id, "10")

    await client.post(
        "/api/v1/recipes",
        json={
            "product_id": meal_id,
            "items": [
                {"ingredient_product_id": pasta_id, "quantity": "0.3", "unit_id": kg_id},
                {"ingredient_product_id": sauce_id, "quantity": "0.1", "unit_id": kg_id},
            ],
        },
        cookies=cookies,
    )

    order = await client.post("/api/v1/pos/orders", json={}, cookies=cookies)
    order_id = order.json()["id"]
    await client.post(
        f"/api/v1/pos/orders/{order_id}/items",
        json={"product_id": meal_id, "quantity": "2", "unit_id": kg_id},
        cookies=cookies,
    )

    denied = await client.post(
        f"/api/v1/pos/orders/{order_id}/complete",
        json={"payment_method": "cash"},
        cookies=cookies,
    )
    assert denied.status_code == 400

    assert await _level_base(client, cookies, pasta_id) == Decimal("0.5")
    assert await _level_base(client, cookies, sauce_id) == Decimal("10")


@pytest.mark.integration
async def test_inactive_recipe_falls_back_to_sell_as_stocked(client):
    owner = await _register(client)
    cookies = owner.cookies

    meal_id, kg_id = await _create_product(
        client, cookies, name="Soup", price_minor=15000
    )
    carrot_id, _ = await _create_product(client, cookies, name="Carrot")

    await _stock_in(client, cookies, meal_id, kg_id, "5")

    recipe = await client.post(
        "/api/v1/recipes",
        json={
            "product_id": meal_id,
            "items": [
                {"ingredient_product_id": carrot_id, "quantity": "0.1", "unit_id": kg_id},
            ],
        },
        cookies=cookies,
    )
    recipe_id = recipe.json()["id"]
    await client.patch(
        f"/api/v1/recipes/{recipe_id}",
        json={"status": "inactive"},
        cookies=cookies,
    )

    order = await client.post("/api/v1/pos/orders", json={}, cookies=cookies)
    order_id = order.json()["id"]
    await client.post(
        f"/api/v1/pos/orders/{order_id}/items",
        json={"product_id": meal_id, "quantity": "1", "unit_id": kg_id},
        cookies=cookies,
    )

    completed = await client.post(
        f"/api/v1/pos/orders/{order_id}/complete",
        json={"payment_method": "cash"},
        cookies=cookies,
    )
    assert completed.status_code == 200
    assert await _level_base(client, cookies, meal_id) == Decimal("4")
