"""Data access for recipe / BOM entities."""
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.inventory.models import Product
from app.modules.recipes.models import Recipe, RecipeItem


class RecipeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _recipe_options(self):
        return (
            selectinload(Recipe.product).selectinload(Product.base_unit),
            selectinload(Recipe.items)
            .selectinload(RecipeItem.ingredient_product)
            .selectinload(Product.base_unit),
            selectinload(Recipe.items).selectinload(RecipeItem.unit),
        )

    async def list_recipes(
        self,
        *,
        tenant_id: uuid.UUID,
        product_id: uuid.UUID | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Recipe], int]:
        filters = [Recipe.tenant_id == tenant_id]
        if product_id is not None:
            filters.append(Recipe.product_id == product_id)

        total = int(
            (
                await self._session.execute(
                    select(func.count()).select_from(Recipe).where(*filters)
                )
            ).scalar_one()
        )
        result = await self._session.execute(
            select(Recipe)
            .where(*filters)
            .options(*self._recipe_options())
            .order_by(Recipe.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().unique().all()), total

    async def get_recipe(
        self, *, tenant_id: uuid.UUID, recipe_id: uuid.UUID
    ) -> Recipe | None:
        result = await self._session.execute(
            select(Recipe)
            .where(Recipe.tenant_id == tenant_id, Recipe.id == recipe_id)
            .options(*self._recipe_options())
        )
        return result.scalar_one_or_none()

    async def get_recipe_by_product(
        self, *, tenant_id: uuid.UUID, product_id: uuid.UUID
    ) -> Recipe | None:
        result = await self._session.execute(
            select(Recipe)
            .where(Recipe.tenant_id == tenant_id, Recipe.product_id == product_id)
            .options(*self._recipe_options())
        )
        return result.scalar_one_or_none()

    async def get_item(
        self, *, tenant_id: uuid.UUID, recipe_id: uuid.UUID, item_id: uuid.UUID
    ) -> RecipeItem | None:
        result = await self._session.execute(
            select(RecipeItem)
            .where(
                RecipeItem.tenant_id == tenant_id,
                RecipeItem.recipe_id == recipe_id,
                RecipeItem.id == item_id,
            )
            .options(
                selectinload(RecipeItem.ingredient_product).selectinload(Product.base_unit),
                selectinload(RecipeItem.unit),
            )
        )
        return result.scalar_one_or_none()

    async def add(self, entity: Recipe | RecipeItem) -> None:
        self._session.add(entity)
