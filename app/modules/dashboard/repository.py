"""Read-only aggregations for dashboard KPIs."""
import uuid
from datetime import UTC, date, datetime, time

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.expenses.models import Expense
from app.modules.inventory.models import Product, StockLevel
from app.modules.pos.models import Order


class DashboardRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _day_bounds(target_date: date) -> tuple[datetime, datetime]:
        start = datetime.combine(target_date, time.min, tzinfo=UTC)
        end = datetime.combine(target_date, time.max, tzinfo=UTC)
        return start, end

    async def summarize_sales(
        self,
        *,
        tenant_id: uuid.UUID,
        currency: str,
        target_date: date,
    ) -> tuple[int, int]:
        start, end = self._day_bounds(target_date)
        result = await self._session.execute(
            select(
                func.coalesce(func.sum(Order.total_minor), 0),
                func.count(),
            ).where(
                Order.tenant_id == tenant_id,
                Order.status == "completed",
                Order.currency == currency,
                Order.completed_at.is_not(None),
                Order.completed_at >= start,
                Order.completed_at <= end,
            )
        )
        total_minor, count = result.one()
        return int(total_minor), int(count)

    async def summarize_expenses(
        self,
        *,
        tenant_id: uuid.UUID,
        currency: str,
        target_date: date,
    ) -> tuple[int, int]:
        result = await self._session.execute(
            select(
                func.coalesce(func.sum(Expense.amount_minor), 0),
                func.count(),
            ).where(
                Expense.tenant_id == tenant_id,
                Expense.currency == currency,
                Expense.expense_date == target_date,
            )
        )
        total_minor, count = result.one()
        return int(total_minor), int(count)

    async def count_low_stock(self, *, tenant_id: uuid.UUID) -> int:
        filters = (
            StockLevel.tenant_id == tenant_id,
            Product.reorder_level_base.is_not(None),
            StockLevel.quantity_base <= Product.reorder_level_base,
            Product.status == "active",
        )
        result = await self._session.execute(
            select(func.count())
            .select_from(StockLevel)
            .join(Product, Product.id == StockLevel.product_id)
            .where(*filters)
        )
        return int(result.scalar_one())

    async def list_low_stock(
        self, *, tenant_id: uuid.UUID, limit: int
    ) -> list[StockLevel]:
        filters = (
            StockLevel.tenant_id == tenant_id,
            Product.reorder_level_base.is_not(None),
            StockLevel.quantity_base <= Product.reorder_level_base,
            Product.status == "active",
        )
        result = await self._session.execute(
            select(StockLevel)
            .join(Product, Product.id == StockLevel.product_id)
            .options(
                selectinload(StockLevel.product).selectinload(Product.base_unit),
            )
            .where(*filters)
            .order_by(StockLevel.quantity_base.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_recent_sales(
        self, *, tenant_id: uuid.UUID, limit: int
    ) -> list[tuple[Order, int]]:
        result = await self._session.execute(
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.tenant_id == tenant_id, Order.status == "completed")
            .order_by(Order.completed_at.desc())
            .limit(limit)
        )
        orders = list(result.scalars().all())
        return [(order, len(order.items)) for order in orders]

    async def list_recent_expenses(
        self, *, tenant_id: uuid.UUID, limit: int
    ) -> list[Expense]:
        result = await self._session.execute(
            select(Expense)
            .options(selectinload(Expense.category))
            .where(Expense.tenant_id == tenant_id)
            .order_by(Expense.expense_date.desc(), Expense.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
