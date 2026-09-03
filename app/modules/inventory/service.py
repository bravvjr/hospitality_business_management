"""Inventory business logic (ADR-005)."""
import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.inventory.models import Product, ProductUnit, StockMovement
from app.modules.inventory.repository import InventoryRepository
from app.modules.inventory.schemas import (
    ProductCreateRequest,
    ProductUnitCreateRequest,
    ProductUpdateRequest,
    StockAdjustmentRequest,
    StockLevelRead,
    StockMovementCreateRequest,
    StockMovementRead,
)


class InventoryError(Exception):
    """Business rule violation for inventory operations."""


class InventoryNotFoundError(InventoryError):
    """Requested inventory entity was not found in the current tenant."""


MOVEMENT_RECEIPT = "receipt"
MOVEMENT_ADJUSTMENT = "adjustment"
MOVEMENT_USAGE = "usage"
MOVEMENT_SALE = "sale"

REASON_DEFAULT = {
    MOVEMENT_RECEIPT: "stock_in",
    MOVEMENT_ADJUSTMENT: "adjustment",
    MOVEMENT_USAGE: "usage",
    MOVEMENT_SALE: "sale",
}


class InventoryService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = InventoryRepository(session)

    async def list_units(self):
        return await self._repo.list_units()

    async def list_products(self, *, tenant_id: uuid.UUID, limit: int, offset: int):
        return await self._repo.list_products(
            tenant_id=tenant_id, limit=limit, offset=offset
        )

    async def get_product(self, *, tenant_id: uuid.UUID, product_id: uuid.UUID):
        product = await self._repo.get_product(tenant_id=tenant_id, product_id=product_id)
        if product is None:
            raise InventoryNotFoundError("Product not found")
        return product

    async def create_product(
        self, *, tenant_id: uuid.UUID, payload: ProductCreateRequest
    ) -> Product:
        unit = await self._repo.get_unit(payload.base_unit_id)
        if unit is None:
            raise InventoryError("Unknown base unit")

        if payload.sku:
            existing = await self._repo.get_product_by_sku(
                tenant_id=tenant_id, sku=payload.sku
            )
            if existing is not None:
                raise InventoryError("SKU already exists for this tenant")

        product = Product(
            tenant_id=tenant_id,
            name=payload.name,
            sku=payload.sku,
            category=payload.category,
            base_unit_id=payload.base_unit_id,
            reorder_level_base=payload.reorder_level_base,
            unit_price_minor=payload.unit_price_minor,
            currency=payload.currency.upper() if payload.currency else None,
        )
        await self._repo.add(product)
        await self._repo.flush()

        # Base unit is always a valid conversion with factor 1 and stock role.
        base_product_unit = ProductUnit(
            tenant_id=tenant_id,
            product_id=product.id,
            unit_id=payload.base_unit_id,
            to_base_factor=Decimal("1"),
            is_stock=True,
            is_purchase=True,
            is_recipe=True,
            is_sales=True,
        )
        await self._repo.add(base_product_unit)
        await self._repo.ensure_stock_level(tenant_id=tenant_id, product_id=product.id)
        await self._session.commit()

        return await self.get_product(tenant_id=tenant_id, product_id=product.id)

    async def update_product(
        self,
        *,
        tenant_id: uuid.UUID,
        product_id: uuid.UUID,
        payload: ProductUpdateRequest,
    ) -> Product:
        product = await self.get_product(tenant_id=tenant_id, product_id=product_id)

        if payload.sku is not None and payload.sku != product.sku:
            existing = await self._repo.get_product_by_sku(
                tenant_id=tenant_id, sku=payload.sku
            )
            if existing is not None and existing.id != product.id:
                raise InventoryError("SKU already exists for this tenant")
            product.sku = payload.sku

        if payload.name is not None:
            product.name = payload.name
        if payload.category is not None:
            product.category = payload.category
        if payload.reorder_level_base is not None:
            product.reorder_level_base = payload.reorder_level_base
        if payload.unit_price_minor is not None:
            product.unit_price_minor = payload.unit_price_minor
        if payload.currency is not None:
            product.currency = payload.currency.upper()
        if payload.status is not None:
            product.status = payload.status

        await self._session.commit()
        return await self.get_product(tenant_id=tenant_id, product_id=product.id)

    async def list_product_units(self, *, tenant_id: uuid.UUID, product_id: uuid.UUID):
        await self.get_product(tenant_id=tenant_id, product_id=product_id)
        return await self._repo.list_product_units(
            tenant_id=tenant_id, product_id=product_id
        )

    async def add_product_unit(
        self,
        *,
        tenant_id: uuid.UUID,
        product_id: uuid.UUID,
        payload: ProductUnitCreateRequest,
    ) -> ProductUnit:
        await self.get_product(tenant_id=tenant_id, product_id=product_id)
        unit = await self._repo.get_unit(payload.unit_id)
        if unit is None:
            raise InventoryError("Unknown unit")

        existing = await self._repo.get_product_unit(
            tenant_id=tenant_id, product_id=product_id, unit_id=payload.unit_id
        )
        if existing is not None:
            raise InventoryError("Unit conversion already exists for this product")

        product_unit = ProductUnit(
            tenant_id=tenant_id,
            product_id=product_id,
            unit_id=payload.unit_id,
            to_base_factor=payload.to_base_factor,
            is_stock=payload.is_stock,
            is_purchase=payload.is_purchase,
            is_recipe=payload.is_recipe,
            is_sales=payload.is_sales,
        )
        await self._repo.add(product_unit)
        await self._session.commit()

        units = await self._repo.list_product_units(
            tenant_id=tenant_id, product_id=product_id
        )
        return next(u for u in units if u.unit_id == payload.unit_id)

    async def get_product_unit(
        self, *, tenant_id: uuid.UUID, product_id: uuid.UUID, unit_id: uuid.UUID
    ):
        return await self._repo.get_product_unit(
            tenant_id=tenant_id, product_id=product_id, unit_id=unit_id
        )

    async def record_receipt(
        self,
        *,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        payload: StockMovementCreateRequest,
    ) -> StockMovementRead:
        return await self._append_movement(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            movement_type=MOVEMENT_RECEIPT,
            signed_entered_quantity=payload.quantity,
            payload=payload,
        )

    async def record_usage(
        self,
        *,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        payload: StockMovementCreateRequest,
    ) -> StockMovementRead:
        return await self._append_movement(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            movement_type=MOVEMENT_USAGE,
            signed_entered_quantity=-payload.quantity,
            payload=payload,
        )

    async def record_adjustment(
        self,
        *,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        payload: StockAdjustmentRequest,
    ) -> StockMovementRead:
        if payload.quantity == 0:
            raise InventoryError("Adjustment quantity cannot be zero")
        return await self._append_movement(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            movement_type=MOVEMENT_ADJUSTMENT,
            signed_entered_quantity=payload.quantity,
            payload=payload,
        )

    async def list_stock_levels(
        self, *, tenant_id: uuid.UUID, limit: int, offset: int
    ) -> tuple[list[StockLevelRead], int]:
        levels, total = await self._repo.list_stock_levels(
            tenant_id=tenant_id, limit=limit, offset=offset
        )
        return [self._to_level_read(level) for level in levels], total

    async def list_low_stock(
        self, *, tenant_id: uuid.UUID, limit: int, offset: int
    ) -> tuple[list[StockLevelRead], int]:
        levels, total = await self._repo.list_low_stock_levels(
            tenant_id=tenant_id, limit=limit, offset=offset
        )
        return [self._to_level_read(level) for level in levels], total

    async def list_movements(
        self,
        *,
        tenant_id: uuid.UUID,
        product_id: uuid.UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[StockMovement], int]:
        if product_id is not None:
            await self.get_product(tenant_id=tenant_id, product_id=product_id)
        return await self._repo.list_movements(
            tenant_id=tenant_id, product_id=product_id, limit=limit, offset=offset
        )

    async def record_sale_deduction(
        self,
        *,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        product_id: uuid.UUID,
        quantity: Decimal,
        unit_id: uuid.UUID,
        source_document_id: str,
        idempotency_key: str,
        commit: bool = False,
    ) -> StockMovement:
        """Deduct stock for a completed sale. Caller owns the transaction when commit=False."""
        payload = StockMovementCreateRequest(
            product_id=product_id,
            quantity=quantity,
            unit_id=unit_id,
            reason="sale",
            source_document_type="order",
            source_document_id=source_document_id,
            idempotency_key=idempotency_key,
        )
        return await self._append_movement(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            movement_type=MOVEMENT_SALE,
            signed_entered_quantity=-quantity,
            payload=payload,
            commit=commit,
            as_read=False,
        )

    async def _append_movement(
        self,
        *,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        movement_type: str,
        signed_entered_quantity: Decimal,
        payload: StockMovementCreateRequest,
        commit: bool = True,
        as_read: bool = True,
    ) -> StockMovementRead | StockMovement:
        if payload.idempotency_key:
            existing = await self._repo.get_movement_by_idempotency(
                tenant_id=tenant_id, idempotency_key=payload.idempotency_key
            )
            if existing is not None:
                return StockMovementRead.model_validate(existing) if as_read else existing

        product = await self.get_product(
            tenant_id=tenant_id, product_id=payload.product_id
        )
        if product.status != "active":
            raise InventoryError("Product is not active")

        product_unit = await self._repo.get_product_unit(
            tenant_id=tenant_id,
            product_id=payload.product_id,
            unit_id=payload.unit_id,
        )
        if product_unit is None:
            raise InventoryError("Unit is not configured for this product")
        if movement_type == MOVEMENT_SALE and not product_unit.is_stock:
            raise InventoryError("Unit is not enabled for stock tracking")

        factor = Decimal(product_unit.to_base_factor)
        delta_base = signed_entered_quantity * factor

        level = await self._repo.lock_stock_level(
            tenant_id=tenant_id, product_id=payload.product_id
        )
        new_qty = Decimal(level.quantity_base) + delta_base
        if new_qty < 0:
            raise InventoryError("Insufficient stock for this movement")

        movement = StockMovement(
            tenant_id=tenant_id,
            product_id=payload.product_id,
            movement_type=movement_type,
            quantity_delta_base=delta_base,
            entered_quantity=signed_entered_quantity,
            entered_unit_id=payload.unit_id,
            to_base_factor_snapshot=factor,
            reason=payload.reason or REASON_DEFAULT[movement_type],
            note=payload.note,
            source_document_type=payload.source_document_type,
            source_document_id=payload.source_document_id,
            actor_user_id=actor_user_id,
            idempotency_key=payload.idempotency_key,
        )
        await self._repo.add(movement)
        level.quantity_base = new_qty
        if commit:
            await self._session.commit()
            await self._session.refresh(movement, attribute_names=["entered_unit"])
            return StockMovementRead.model_validate(movement)
        await self._session.flush()
        return StockMovementRead.model_validate(movement) if as_read else movement

    @staticmethod
    def _to_level_read(level) -> StockLevelRead:
        product = level.product
        reorder = product.reorder_level_base
        is_low = reorder is not None and Decimal(level.quantity_base) <= Decimal(reorder)
        return StockLevelRead(
            product_id=product.id,
            product_name=product.name,
            base_unit=product.base_unit,
            quantity_base=level.quantity_base,
            reorder_level_base=reorder,
            is_low_stock=is_low,
        )
