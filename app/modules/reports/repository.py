"""Read-only SQL aggregations for period reports."""
import uuid
from datetime import UTC, date, datetime, time
from decimal import Decimal

from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.expenses.models import Expense, ExpenseCategory
from app.modules.inventory.models import StockMovement
from app.modules.pos.models import Order, OrderItem, Payment


class ReportsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _range_bounds(from_date: date, to_date: date) -> tuple[datetime, datetime]:
        start = datetime.combine(from_date, time.min, tzinfo=UTC)
        end = datetime.combine(to_date, time.max, tzinfo=UTC)
        return start, end

    @staticmethod
    def _completed_order_filters(
        *,
        tenant_id: uuid.UUID,
        currency: str,
        from_date: date,
        to_date: date,
    ) -> tuple:
        start, end = ReportsRepository._range_bounds(from_date, to_date)
        return (
            Order.tenant_id == tenant_id,
            Order.status == "completed",
            Order.currency == currency,
            Order.completed_at.is_not(None),
            Order.completed_at >= start,
            Order.completed_at <= end,
        )

    async def summarize_sales(
        self,
        *,
        tenant_id: uuid.UUID,
        currency: str,
        from_date: date,
        to_date: date,
    ) -> tuple[int, int]:
        filters = self._completed_order_filters(
            tenant_id=tenant_id,
            currency=currency,
            from_date=from_date,
            to_date=to_date,
        )
        result = await self._session.execute(
            select(
                func.coalesce(func.sum(Order.total_minor), 0),
                func.count(),
            ).where(*filters)
        )
        total_minor, count = result.one()
        return int(total_minor), int(count)

    async def summarize_sales_by_period(
        self,
        *,
        tenant_id: uuid.UUID,
        currency: str,
        from_date: date,
        to_date: date,
        group_by: str,
    ) -> list[tuple[date, int, int]]:
        filters = self._completed_order_filters(
            tenant_id=tenant_id,
            currency=currency,
            from_date=from_date,
            to_date=to_date,
        )
        bucket = cast(func.date_trunc(group_by, Order.completed_at), Date)
        result = await self._session.execute(
            select(
                bucket,
                func.coalesce(func.sum(Order.total_minor), 0),
                func.count(),
            )
            .where(*filters)
            .group_by(bucket)
            .order_by(bucket)
        )
        return [(row[0], int(row[1]), int(row[2])) for row in result.all()]

    async def summarize_expenses(
        self,
        *,
        tenant_id: uuid.UUID,
        currency: str,
        from_date: date,
        to_date: date,
    ) -> tuple[int, int]:
        result = await self._session.execute(
            select(
                func.coalesce(func.sum(Expense.amount_minor), 0),
                func.count(),
            ).where(
                Expense.tenant_id == tenant_id,
                Expense.currency == currency,
                Expense.expense_date >= from_date,
                Expense.expense_date <= to_date,
            )
        )
        total_minor, count = result.one()
        return int(total_minor), int(count)

    async def summarize_expenses_by_category(
        self,
        *,
        tenant_id: uuid.UUID,
        currency: str,
        from_date: date,
        to_date: date,
    ) -> list[tuple[uuid.UUID, str, int, int]]:
        result = await self._session.execute(
            select(
                Expense.category_id,
                ExpenseCategory.name,
                func.coalesce(func.sum(Expense.amount_minor), 0),
                func.count(),
            )
            .join(ExpenseCategory, ExpenseCategory.id == Expense.category_id)
            .where(
                Expense.tenant_id == tenant_id,
                Expense.currency == currency,
                Expense.expense_date >= from_date,
                Expense.expense_date <= to_date,
            )
            .group_by(Expense.category_id, ExpenseCategory.name)
            .order_by(func.sum(Expense.amount_minor).desc())
        )
        return [
            (row[0], row[1], int(row[2]), int(row[3]))
            for row in result.all()
        ]

    async def summarize_sales_by_product(
        self,
        *,
        tenant_id: uuid.UUID,
        currency: str,
        from_date: date,
        to_date: date,
        limit: int,
        sort_by: str,
    ) -> list[tuple[uuid.UUID, str, int, Decimal, int]]:
        filters = self._completed_order_filters(
            tenant_id=tenant_id,
            currency=currency,
            from_date=from_date,
            to_date=to_date,
        )
        total_minor = func.coalesce(func.sum(OrderItem.line_total_minor), 0)
        quantity = func.coalesce(func.sum(OrderItem.quantity), 0)
        order_by = total_minor.desc() if sort_by == "revenue" else quantity.desc()
        result = await self._session.execute(
            select(
                OrderItem.product_id,
                OrderItem.product_name,
                total_minor,
                quantity,
                func.count(),
            )
            .join(Order, Order.id == OrderItem.order_id)
            .where(*filters)
            .group_by(OrderItem.product_id, OrderItem.product_name)
            .order_by(order_by)
            .limit(limit)
        )
        return [
            (row[0], row[1], int(row[2]), row[3], int(row[4]))
            for row in result.all()
        ]

    async def summarize_sales_by_payment_method(
        self,
        *,
        tenant_id: uuid.UUID,
        currency: str,
        from_date: date,
        to_date: date,
    ) -> list[tuple[str, int, int]]:
        filters = self._completed_order_filters(
            tenant_id=tenant_id,
            currency=currency,
            from_date=from_date,
            to_date=to_date,
        )
        result = await self._session.execute(
            select(
                Payment.method,
                func.coalesce(func.sum(Order.total_minor), 0),
                func.count(),
            )
            .join(Order, Order.id == Payment.order_id)
            .where(
                *filters,
                Payment.status == "completed",
            )
            .group_by(Payment.method)
            .order_by(func.sum(Order.total_minor).desc())
        )
        return [(row[0], int(row[1]), int(row[2])) for row in result.all()]

    async def summarize_inventory_movements(
        self,
        *,
        tenant_id: uuid.UUID,
        from_date: date,
        to_date: date,
        movement_type: str | None,
    ) -> list[tuple[str, int, Decimal]]:
        start, end = self._range_bounds(from_date, to_date)
        filters = [
            StockMovement.tenant_id == tenant_id,
            StockMovement.created_at >= start,
            StockMovement.created_at <= end,
        ]
        if movement_type is not None:
            filters.append(StockMovement.movement_type == movement_type)

        quantity_delta = func.coalesce(func.sum(StockMovement.quantity_delta_base), 0)
        result = await self._session.execute(
            select(
                StockMovement.movement_type,
                func.count(),
                quantity_delta,
            )
            .where(*filters)
            .group_by(StockMovement.movement_type)
            .order_by(StockMovement.movement_type)
        )
        return [(row[0], int(row[1]), row[2]) for row in result.all()]
