"""Data access for POS orders and payments."""
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.pos.models import Order, OrderItem, Payment


class PosRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_order(
        self, *, tenant_id: uuid.UUID, order_id: uuid.UUID
    ) -> Order | None:
        result = await self._session.execute(
            select(Order)
            .options(
                selectinload(Order.items),
                selectinload(Order.payments),
            )
            .where(Order.tenant_id == tenant_id, Order.id == order_id)
        )
        return result.scalar_one_or_none()

    async def list_orders(
        self,
        *,
        tenant_id: uuid.UUID,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Order], int]:
        filters = [Order.tenant_id == tenant_id]
        if status is not None:
            filters.append(Order.status == status)

        total = int(
            (
                await self._session.execute(
                    select(func.count()).select_from(Order).where(*filters)
                )
            ).scalar_one()
        )
        result = await self._session.execute(
            select(Order)
            .options(
                selectinload(Order.items),
                selectinload(Order.payments),
            )
            .where(*filters)
            .order_by(Order.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), total

    async def get_item(
        self, *, tenant_id: uuid.UUID, order_id: uuid.UUID, item_id: uuid.UUID
    ) -> OrderItem | None:
        result = await self._session.execute(
            select(OrderItem).where(
                OrderItem.tenant_id == tenant_id,
                OrderItem.order_id == order_id,
                OrderItem.id == item_id,
            )
        )
        return result.scalar_one_or_none()

    async def add(self, entity: Order | OrderItem | Payment) -> None:
        self._session.add(entity)

    async def delete_item(self, item: OrderItem) -> None:
        await self._session.delete(item)

    async def flush(self) -> None:
        await self._session.flush()
