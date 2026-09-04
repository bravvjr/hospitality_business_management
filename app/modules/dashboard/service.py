"""Dashboard business logic — aggregates POS, expenses, and inventory KPIs."""
import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.dashboard.repository import DashboardRepository
from app.modules.dashboard.schemas import (
    DashboardLowStockRead,
    DashboardRecentExpenseRead,
    DashboardRecentRead,
    DashboardRecentSaleRead,
    DashboardSummaryRead,
)
from app.modules.tenant.repository import TenantRepository


class DashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = DashboardRepository(session)

    async def summary(
        self,
        *,
        tenant_id: uuid.UUID,
        target_date: date,
        currency: str | None = None,
    ) -> DashboardSummaryRead:
        tenant = await TenantRepository(self._session).get(tenant_id)
        if tenant is None:
            raise ValueError("Tenant is unavailable")

        resolved_currency = (currency or tenant.base_currency).upper()
        sales_total, sales_count = await self._repo.summarize_sales(
            tenant_id=tenant_id,
            currency=resolved_currency,
            target_date=target_date,
        )
        expenses_total, expenses_count = await self._repo.summarize_expenses(
            tenant_id=tenant_id,
            currency=resolved_currency,
            target_date=target_date,
        )
        low_stock_count = await self._repo.count_low_stock(tenant_id=tenant_id)

        return DashboardSummaryRead(
            date=target_date,
            currency=resolved_currency,
            sales_total_minor=sales_total,
            sales_count=sales_count,
            expenses_total_minor=expenses_total,
            expenses_count=expenses_count,
            net_position_minor=sales_total - expenses_total,
            low_stock_count=low_stock_count,
        )

    async def recent(self, *, tenant_id: uuid.UUID, limit: int) -> DashboardRecentRead:
        sales = [
            DashboardRecentSaleRead(
                id=order.id,
                total_minor=order.total_minor,
                currency=order.currency,
                completed_at=order.completed_at,  # type: ignore[arg-type]
                item_count=item_count,
            )
            for order, item_count in await self._repo.list_recent_sales(
                tenant_id=tenant_id, limit=limit
            )
            if order.completed_at is not None
        ]
        expenses = [
            DashboardRecentExpenseRead(
                id=expense.id,
                amount_minor=expense.amount_minor,
                currency=expense.currency,
                description=expense.description,
                expense_date=expense.expense_date,
                category_name=expense.category.name,
            )
            for expense in await self._repo.list_recent_expenses(
                tenant_id=tenant_id, limit=limit
            )
        ]
        return DashboardRecentRead(sales=sales, expenses=expenses)

    async def low_stock(self, *, tenant_id: uuid.UUID, limit: int) -> list[DashboardLowStockRead]:
        levels = await self._repo.list_low_stock(tenant_id=tenant_id, limit=limit)
        return [
            DashboardLowStockRead(
                product_id=level.product_id,
                product_name=level.product.name,
                quantity_base=str(level.quantity_base),
                reorder_level_base=(
                    str(level.product.reorder_level_base)
                    if level.product.reorder_level_base is not None
                    else None
                ),
                unit_symbol=level.product.base_unit.symbol,
            )
            for level in levels
        ]
