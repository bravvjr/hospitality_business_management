"""Reports business logic (Phase 2a/2b/2c)."""
import uuid
from datetime import date

from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.reports.exports import (
    REPORT_EXPORT_KEYS,
    ReportExportKey,
    export_expenses_by_category_csv,
    export_inventory_movements_csv,
    export_pnl_csv,
    export_sales_by_payment_method_csv,
    export_sales_by_product_csv,
    export_sales_summary_csv,
)
from app.modules.reports.repository import ReportsRepository
from app.modules.reports.schemas import (
    CategoryExpenseRead,
    ExpensesByCategoryRead,
    GroupBy,
    InventoryMovementSummaryRead,
    MovementTypeSummaryRead,
    PaymentMethodSalesRead,
    PnlRead,
    ProductSalesRead,
    SalesBucketRead,
    SalesByPaymentMethodRead,
    SalesByProductRead,
    SalesSortBy,
    SalesSummaryRead,
)
from app.modules.tenant.repository import TenantRepository

MAX_REPORT_DAYS = 366
MAX_REPORT_LIMIT = 50


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

    async def sales_by_product(
        self,
        *,
        tenant_id: uuid.UUID,
        from_date: date,
        to_date: date,
        currency: str | None = None,
        limit: int = 10,
        sort_by: SalesSortBy = "revenue",
    ) -> SalesByProductRead:
        self._validate_date_range(from_date, to_date)
        if limit < 1 or limit > MAX_REPORT_LIMIT:
            raise ReportError(f"limit must be between 1 and {MAX_REPORT_LIMIT}")
        resolved_currency = await self._resolve_currency(
            tenant_id=tenant_id, currency=currency
        )
        rows = await self._repo.summarize_sales_by_product(
            tenant_id=tenant_id,
            currency=resolved_currency,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
            sort_by=sort_by,
        )
        products = [
            ProductSalesRead(
                product_id=product_id,
                product_name=product_name,
                total_minor=total_minor,
                quantity=quantity,
                line_count=line_count,
            )
            for product_id, product_name, total_minor, quantity, line_count in rows
        ]
        return SalesByProductRead(
            currency=resolved_currency,
            from_date=from_date,
            to_date=to_date,
            products=products,
        )

    async def sales_by_payment_method(
        self,
        *,
        tenant_id: uuid.UUID,
        from_date: date,
        to_date: date,
        currency: str | None = None,
    ) -> SalesByPaymentMethodRead:
        self._validate_date_range(from_date, to_date)
        resolved_currency = await self._resolve_currency(
            tenant_id=tenant_id, currency=currency
        )
        rows = await self._repo.summarize_sales_by_payment_method(
            tenant_id=tenant_id,
            currency=resolved_currency,
            from_date=from_date,
            to_date=to_date,
        )
        methods = [
            PaymentMethodSalesRead(
                method=method,
                total_minor=total_minor,
                payment_count=payment_count,
            )
            for method, total_minor, payment_count in rows
        ]
        return SalesByPaymentMethodRead(
            currency=resolved_currency,
            from_date=from_date,
            to_date=to_date,
            methods=methods,
        )

    async def inventory_movements(
        self,
        *,
        tenant_id: uuid.UUID,
        from_date: date,
        to_date: date,
        movement_type: str | None = None,
    ) -> InventoryMovementSummaryRead:
        self._validate_date_range(from_date, to_date)
        rows = await self._repo.summarize_inventory_movements(
            tenant_id=tenant_id,
            from_date=from_date,
            to_date=to_date,
            movement_type=movement_type,
        )
        types = [
            MovementTypeSummaryRead(
                movement_type=row_type,
                movement_count=movement_count,
                total_quantity_delta_base=total_delta,
            )
            for row_type, movement_count, total_delta in rows
        ]
        return InventoryMovementSummaryRead(
            from_date=from_date,
            to_date=to_date,
            movement_type=movement_type,
            types=types,
        )

    async def export_csv(
        self,
        *,
        report_key: ReportExportKey,
        tenant_id: uuid.UUID,
        from_date: date,
        to_date: date,
        currency: str | None = None,
        group_by: GroupBy | None = None,
        limit: int = 10,
        sort_by: SalesSortBy = "revenue",
        movement_type: str | None = None,
    ) -> StreamingResponse:
        if report_key not in REPORT_EXPORT_KEYS:
            raise ReportError(f"Unknown report export key: {report_key}")

        if report_key == "sales-summary":
            report = await self.sales_summary(
                tenant_id=tenant_id,
                from_date=from_date,
                to_date=to_date,
                currency=currency,
                group_by=group_by,
            )
            return export_sales_summary_csv(report)
        if report_key == "sales-by-product":
            report = await self.sales_by_product(
                tenant_id=tenant_id,
                from_date=from_date,
                to_date=to_date,
                currency=currency,
                limit=limit,
                sort_by=sort_by,
            )
            return export_sales_by_product_csv(report)
        if report_key == "sales-by-payment-method":
            report = await self.sales_by_payment_method(
                tenant_id=tenant_id,
                from_date=from_date,
                to_date=to_date,
                currency=currency,
            )
            return export_sales_by_payment_method_csv(report)
        if report_key == "expenses-by-category":
            report = await self.expenses_by_category(
                tenant_id=tenant_id,
                from_date=from_date,
                to_date=to_date,
                currency=currency,
            )
            return export_expenses_by_category_csv(report)
        if report_key == "pnl":
            report = await self.pnl(
                tenant_id=tenant_id,
                from_date=from_date,
                to_date=to_date,
                currency=currency,
            )
            return export_pnl_csv(report)
        report = await self.inventory_movements(
            tenant_id=tenant_id,
            from_date=from_date,
            to_date=to_date,
            movement_type=movement_type,
        )
        return export_inventory_movements_csv(report)
