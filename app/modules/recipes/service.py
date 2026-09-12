"""Recipe / BOM business logic (Phase 2a + 2b consumption)."""
import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.inventory.repository import InventoryRepository
from app.modules.inventory.service import InventoryService
from app.modules.recipes.models import Recipe, RecipeItem
from app.modules.recipes.repository import RecipeRepository
from app.modules.recipes.schemas import (
    RecipeCreateRequest,
    RecipeItemCreateRequest,
    RecipeItemRead,
    RecipeItemUpdateRequest,
    RecipeRead,
    RecipeSummaryRead,
    RecipeUpdateRequest,
)


class RecipeError(Exception):
    """Business rule violation for recipe operations."""


class RecipeNotFoundError(RecipeError):
    """Requested recipe entity was not found in the current tenant."""


class RecipeService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = RecipeRepository(session)
        self._inventory = InventoryRepository(session)

    async def list_recipes(
        self,
        *,
        tenant_id: uuid.UUID,
        product_id: uuid.UUID | None,
        limit: int,
        offset: int,
    ) -> tuple[list[RecipeSummaryRead], int]:
        recipes, total = await self._repo.list_recipes(
            tenant_id=tenant_id,
            product_id=product_id,
            limit=limit,
            offset=offset,
        )
        return [self._to_summary(recipe) for recipe in recipes], total

    async def get_recipe(self, *, tenant_id: uuid.UUID, recipe_id: uuid.UUID) -> RecipeRead:
        recipe = await self._repo.get_recipe(tenant_id=tenant_id, recipe_id=recipe_id)
        if recipe is None:
            raise RecipeNotFoundError("Recipe not found")
        return RecipeRead.model_validate(recipe)

    async def create_recipe(
        self, *, tenant_id: uuid.UUID, payload: RecipeCreateRequest
    ) -> RecipeRead:
        product = await self._inventory.get_product(
            tenant_id=tenant_id, product_id=payload.product_id
        )
        if product is None:
            raise RecipeError("Product not found")
        if product.status != "active":
            raise RecipeError("Product must be active")

        existing = await self._repo.get_recipe_by_product(
            tenant_id=tenant_id, product_id=payload.product_id
        )
        if existing is not None:
            raise RecipeError("A recipe already exists for this product")

        recipe = Recipe(
            tenant_id=tenant_id,
            product_id=payload.product_id,
            yields_quantity=payload.yields_quantity,
            notes=payload.notes,
        )
        await self._repo.add(recipe)
        await self._session.flush()

        seen_ingredients: set[uuid.UUID] = set()
        for index, item_payload in enumerate(payload.items):
            if item_payload.ingredient_product_id in seen_ingredients:
                raise RecipeError("Duplicate ingredient on recipe")
            seen_ingredients.add(item_payload.ingredient_product_id)
            await self._build_item(
                tenant_id=tenant_id,
                recipe=recipe,
                payload=item_payload,
                sort_order=item_payload.sort_order or index,
            )

        await self._session.commit()
        return await self.get_recipe(tenant_id=tenant_id, recipe_id=recipe.id)

    async def update_recipe(
        self,
        *,
        tenant_id: uuid.UUID,
        recipe_id: uuid.UUID,
        payload: RecipeUpdateRequest,
    ) -> RecipeRead:
        recipe = await self._repo.get_recipe(tenant_id=tenant_id, recipe_id=recipe_id)
        if recipe is None:
            raise RecipeNotFoundError("Recipe not found")

        if payload.yields_quantity is not None:
            recipe.yields_quantity = payload.yields_quantity
        if payload.status is not None:
            recipe.status = payload.status
        if payload.notes is not None:
            recipe.notes = payload.notes

        await self._session.commit()
        return await self.get_recipe(tenant_id=tenant_id, recipe_id=recipe.id)

    async def delete_recipe(self, *, tenant_id: uuid.UUID, recipe_id: uuid.UUID) -> None:
        recipe = await self._repo.get_recipe(tenant_id=tenant_id, recipe_id=recipe_id)
        if recipe is None:
            raise RecipeNotFoundError("Recipe not found")
        await self._session.delete(recipe)
        await self._session.commit()

    async def add_item(
        self,
        *,
        tenant_id: uuid.UUID,
        recipe_id: uuid.UUID,
        payload: RecipeItemCreateRequest,
    ) -> RecipeItemRead:
        recipe = await self._repo.get_recipe(tenant_id=tenant_id, recipe_id=recipe_id)
        if recipe is None:
            raise RecipeNotFoundError("Recipe not found")
        if any(
            item.ingredient_product_id == payload.ingredient_product_id
            for item in recipe.items
        ):
            raise RecipeError("Ingredient already exists on this recipe")

        item = await self._build_item(
            tenant_id=tenant_id,
            recipe=recipe,
            payload=payload,
            sort_order=payload.sort_order,
        )
        await self._session.commit()
        refreshed = await self._repo.get_item(
            tenant_id=tenant_id, recipe_id=recipe_id, item_id=item.id
        )
        assert refreshed is not None
        return RecipeItemRead.model_validate(refreshed)

    async def update_item(
        self,
        *,
        tenant_id: uuid.UUID,
        recipe_id: uuid.UUID,
        item_id: uuid.UUID,
        payload: RecipeItemUpdateRequest,
    ) -> RecipeItemRead:
        recipe = await self._repo.get_recipe(tenant_id=tenant_id, recipe_id=recipe_id)
        if recipe is None:
            raise RecipeNotFoundError("Recipe not found")
        item = await self._repo.get_item(
            tenant_id=tenant_id, recipe_id=recipe_id, item_id=item_id
        )
        if item is None:
            raise RecipeNotFoundError("Recipe item not found")

        if payload.quantity is not None:
            item.quantity = payload.quantity
        if payload.sort_order is not None:
            item.sort_order = payload.sort_order
        if payload.unit_id is not None:
            await self._validate_ingredient_unit(
                tenant_id=tenant_id,
                ingredient_product_id=item.ingredient_product_id,
                unit_id=payload.unit_id,
            )
            item.unit_id = payload.unit_id

        await self._session.commit()
        refreshed = await self._repo.get_item(
            tenant_id=tenant_id, recipe_id=recipe_id, item_id=item_id
        )
        assert refreshed is not None
        return RecipeItemRead.model_validate(refreshed)

    async def consume_for_sale_line(
        self,
        *,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        order_item_id: uuid.UUID,
        product_id: uuid.UUID,
        quantity: Decimal,
        to_base_factor_snapshot: Decimal,
        inventory: InventoryService,
        source_document_id: str,
        commit: bool = False,
    ) -> bool:
        """Deduct ingredient stock when the sold product has an active recipe.

        Returns True when recipe consumption was applied. When there is no recipe,
        it is inactive, or it has no items, returns False so the caller can fall
        back to deducting the sold product directly (sell-as-stocked).
        """
        recipe = await self._repo.get_recipe_by_product(
            tenant_id=tenant_id, product_id=product_id
        )
        if recipe is None or recipe.status != "active" or not recipe.items:
            return False

        order_base_qty = quantity * to_base_factor_snapshot
        batch_multiplier = order_base_qty / Decimal(recipe.yields_quantity)

        for recipe_item in recipe.items:
            ingredient_qty = Decimal(recipe_item.quantity) * batch_multiplier
            await inventory.record_sale_deduction(
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                product_id=recipe_item.ingredient_product_id,
                quantity=ingredient_qty,
                unit_id=recipe_item.unit_id,
                source_document_id=source_document_id,
                idempotency_key=f"sale:{order_item_id}:{recipe_item.id}",
                commit=commit,
            )
        return True

    async def delete_item(
        self,
        *,
        tenant_id: uuid.UUID,
        recipe_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> None:
        recipe = await self._repo.get_recipe(tenant_id=tenant_id, recipe_id=recipe_id)
        if recipe is None:
            raise RecipeNotFoundError("Recipe not found")
        item = await self._repo.get_item(
            tenant_id=tenant_id, recipe_id=recipe_id, item_id=item_id
        )
        if item is None:
            raise RecipeNotFoundError("Recipe item not found")
        await self._session.delete(item)
        await self._session.commit()

    async def _build_item(
        self,
        *,
        tenant_id: uuid.UUID,
        recipe: Recipe,
        payload: RecipeItemCreateRequest,
        sort_order: int,
    ) -> RecipeItem:
        if payload.ingredient_product_id == recipe.product_id:
            raise RecipeError("A recipe cannot include the meal product as an ingredient")
        await self._validate_ingredient_unit(
            tenant_id=tenant_id,
            ingredient_product_id=payload.ingredient_product_id,
            unit_id=payload.unit_id,
        )
        item = RecipeItem(
            tenant_id=tenant_id,
            recipe_id=recipe.id,
            ingredient_product_id=payload.ingredient_product_id,
            quantity=payload.quantity,
            unit_id=payload.unit_id,
            sort_order=sort_order,
        )
        await self._repo.add(item)
        return item

    async def _validate_ingredient_unit(
        self,
        *,
        tenant_id: uuid.UUID,
        ingredient_product_id: uuid.UUID,
        unit_id: uuid.UUID,
    ) -> None:
        product = await self._inventory.get_product(
            tenant_id=tenant_id, product_id=ingredient_product_id
        )
        if product is None:
            raise RecipeError("Ingredient product not found")
        if product.status != "active":
            raise RecipeError("Ingredient product must be active")

        product_unit = await self._inventory.get_product_unit(
            tenant_id=tenant_id,
            product_id=ingredient_product_id,
            unit_id=unit_id,
        )
        if product_unit is None:
            raise RecipeError("Unit is not configured for this ingredient product")
        if not product_unit.is_recipe and not product_unit.is_stock:
            raise RecipeError("Unit must be enabled for recipe or stock on the ingredient")

    @staticmethod
    def _to_summary(recipe: Recipe) -> RecipeSummaryRead:
        data = RecipeRead.model_validate(recipe).model_dump()
        return RecipeSummaryRead(
            id=data["id"],
            tenant_id=data["tenant_id"],
            product_id=data["product_id"],
            product=data["product"],
            yields_quantity=data["yields_quantity"],
            status=data["status"],
            item_count=len(recipe.items),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )
