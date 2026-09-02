"""Data access for inventory entities."""
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.inventory.models import Product, ProductUnit, StockLevel, StockMovement, Unit


class InventoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_units(self) -> list[Unit]:
        result = await self._session.execute(select(Unit).order_by(Unit.name.asc()))
        return list(result.scalars().all())

    async def get_unit(self, unit_id: uuid.UUID) -> Unit | None:
        result = await self._session.execute(select(Unit).where(Unit.id == unit_id))
        return result.scalar_one_or_none()

    async def list_products(self, *, tenant_id: uuid.UUID) -> list[Product]:
        result = await self._session.execute(
            select(Product)
            .options(selectinload(Product.base_unit))
            .where(Product.tenant_id == tenant_id)
            .order_by(Product.name.asc())
        )
        return list(result.scalars().all())

    async def get_product(
        self, *, tenant_id: uuid.UUID, product_id: uuid.UUID
    ) -> Product | None:
        result = await self._session.execute(
            select(Product)
            .options(selectinload(Product.base_unit))
            .where(Product.tenant_id == tenant_id, Product.id == product_id)
        )
        return result.scalar_one_or_none()

    async def get_product_by_sku(
        self, *, tenant_id: uuid.UUID, sku: str
    ) -> Product | None:
        result = await self._session.execute(
            select(Product).where(Product.tenant_id == tenant_id, Product.sku == sku)
        )
        return result.scalar_one_or_none()

    async def list_product_units(
        self, *, tenant_id: uuid.UUID, product_id: uuid.UUID
    ) -> list[ProductUnit]:
        result = await self._session.execute(
            select(ProductUnit)
            .options(selectinload(ProductUnit.unit))
            .where(ProductUnit.tenant_id == tenant_id, ProductUnit.product_id == product_id)
            .order_by(ProductUnit.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_product_unit(
        self, *, tenant_id: uuid.UUID, product_id: uuid.UUID, unit_id: uuid.UUID
    ) -> ProductUnit | None:
        result = await self._session.execute(
            select(ProductUnit)
            .options(selectinload(ProductUnit.unit))
            .where(
                ProductUnit.tenant_id == tenant_id,
                ProductUnit.product_id == product_id,
                ProductUnit.unit_id == unit_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_stock_level(
        self, *, tenant_id: uuid.UUID, product_id: uuid.UUID
    ) -> StockLevel | None:
        result = await self._session.execute(
            select(StockLevel).where(
                StockLevel.tenant_id == tenant_id,
                StockLevel.product_id == product_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_stock_levels(self, *, tenant_id: uuid.UUID) -> list[StockLevel]:
        result = await self._session.execute(
            select(StockLevel)
            .options(
                selectinload(StockLevel.product).selectinload(Product.base_unit),
            )
            .where(StockLevel.tenant_id == tenant_id)
            .order_by(StockLevel.product_id.asc())
        )
        return list(result.scalars().all())

    async def list_low_stock_levels(self, *, tenant_id: uuid.UUID) -> list[StockLevel]:
        result = await self._session.execute(
            select(StockLevel)
            .join(Product, Product.id == StockLevel.product_id)
            .options(
                selectinload(StockLevel.product).selectinload(Product.base_unit),
            )
            .where(
                StockLevel.tenant_id == tenant_id,
                Product.reorder_level_base.is_not(None),
                StockLevel.quantity_base <= Product.reorder_level_base,
                Product.status == "active",
            )
            .order_by(StockLevel.quantity_base.asc())
        )
        return list(result.scalars().all())

    async def get_movement_by_idempotency(
        self, *, tenant_id: uuid.UUID, idempotency_key: str
    ) -> StockMovement | None:
        result = await self._session.execute(
            select(StockMovement)
            .options(selectinload(StockMovement.entered_unit))
            .where(
                StockMovement.tenant_id == tenant_id,
                StockMovement.idempotency_key == idempotency_key,
            )
        )
        return result.scalar_one_or_none()

    async def list_movements(
        self,
        *,
        tenant_id: uuid.UUID,
        product_id: uuid.UUID | None = None,
        limit: int = 100,
    ) -> list[StockMovement]:
        stmt = (
            select(StockMovement)
            .options(selectinload(StockMovement.entered_unit))
            .where(StockMovement.tenant_id == tenant_id)
            .order_by(StockMovement.created_at.desc())
            .limit(limit)
        )
        if product_id is not None:
            stmt = stmt.where(StockMovement.product_id == product_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def add(self, entity: object) -> None:
        self._session.add(entity)

    async def flush(self) -> None:
        await self._session.flush()

    async def ensure_stock_level(
        self, *, tenant_id: uuid.UUID, product_id: uuid.UUID
    ) -> StockLevel:
        level = await self.get_stock_level(tenant_id=tenant_id, product_id=product_id)
        if level is not None:
            return level
        level = StockLevel(
            tenant_id=tenant_id,
            product_id=product_id,
            quantity_base=Decimal("0"),
        )
        self._session.add(level)
        await self._session.flush()
        return level
