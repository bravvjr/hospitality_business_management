"""Reports business logic (Phase 2a)."""
import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.reports.repository import ReportsRepository
from app.modules.reports.schemas import (
    CategoryExpenseRead,
    ExpensesByCategoryRead,
    GroupBy,
    PnlRead,
    SalesBucketRead,
    SalesSummaryRead,
)
from app.modules.tenant.repository import TenantRepository

MAX_REPORT_DAYS = 366


class ReportError(Exception):
    """Business rule violation for report operations."""


class ReportsService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = ReportsRepository(session)

    async def _resolve_currency(
        self, *, tenant_id: uuid.UUID, currency: str | None
    ) -> str:
        if currency is not None:
            return currency.upper()
        tenant = await TenantRepository(self._session).get(tenant_id)
        if tenant is None:
            raise ReportError("Tenant is unavailable")
        return tenant.base_currency.upper()

    @staticmethod
    def _validate_date_range(from_date: date, to_date: date) -> None:
        if from_date > to_date:
            raise ReportError("from_date must be on or before to_date")
        span_days = (to_date - from_date).days + 1
        if span_days > MAX_REPORT_DAYS:
            raise ReportError(f"Date range cannot exceed {MAX_REPORT_DAYS} days")

    async def sales_summary(
        self,
        *,
        tenant_id: uuid.UUID,
        from_date: date,
        to_date: date,
        currency: str | None = None,
        group_by: GroupBy | None = None,
    ) -> SalesSummaryRead:
        self._validate_date_range(from_date, to_date)
        resolved_currency = await self._resolve_currency(
            tenant_id=tenant_id, currency=currency
        )
        total_minor, order_count = await self._repo.summarize_sales(
            tenant_id=tenant_id,
            currency=resolved_currency,
            from_date=from_date,
            to_date=to_date,
        )
        average_ticket_minor = total_minor // order_count if order_count else 0

        buckets: list[SalesBucketRead] = []
        if group_by is not None:
            period_rows = await self._repo.summarize_sales_by_period(
                tenant_id=tenant_id,
                currency=resolved_currency,
                from_date=from_date,
                to_date=to_date,
                group_by=group_by,
            )
            buckets = [
                SalesBucketRead(
                    period_start=period_start,
                    total_minor=period_total,
                    order_count=period_count,
                )
                for period_start, period_total, period_count in period_rows
            ]

        return SalesSummaryRead(
            currency=resolved_currency,
            from_date=from_date,
            to_date=to_date,
            total_minor=total_minor,
            order_count=order_count,
            average_ticket_minor=average_ticket_minor,
            buckets=buckets,
        )

    async def expenses_by_category(
        self,
        *,
        tenant_id: uuid.UUID,
        from_date: date,
        to_date: date,
        currency: str | None = None,
    ) -> ExpensesByCategoryRead:
        self._validate_date_range(from_date, to_date)
        resolved_currency = await self._resolve_currency(
            tenant_id=tenant_id, currency=currency
        )
        rows = await self._repo.summarize_expenses_by_category(
            tenant_id=tenant_id,
            currency=resolved_currency,
            from_date=from_date,
            to_date=to_date,
        )
        categories = [
            CategoryExpenseRead(
                category_id=category_id,
                category_name=category_name,
                total_minor=total_minor,
                expense_count=expense_count,
            )
            for category_id, category_name, total_minor, expense_count in rows
        ]
        return ExpensesByCategoryRead(
            currency=resolved_currency,
            from_date=from_date,
            to_date=to_date,
            categories=categories,
        )

    async def pnl(
        self,
        *,
        tenant_id: uuid.UUID,
        from_date: date,
        to_date: date,
        currency: str | None = None,
    ) -> PnlRead:
        self._validate_date_range(from_date, to_date)
        resolved_currency = await self._resolve_currency(
            tenant_id=tenant_id, currency=currency
        )
        revenue_minor, order_count = await self._repo.summarize_sales(
            tenant_id=tenant_id,
            currency=resolved_currency,
            from_date=from_date,
            to_date=to_date,
        )
        expense_minor, expense_count = await self._repo.summarize_expenses(
            tenant_id=tenant_id,
            currency=resolved_currency,
            from_date=from_date,
            to_date=to_date,
        )
        return PnlRead(
            currency=resolved_currency,
            from_date=from_date,
            to_date=to_date,
            revenue_minor=revenue_minor,
            expense_minor=expense_minor,
            net_minor=revenue_minor - expense_minor,
            order_count=order_count,
            expense_count=expense_count,
        )
