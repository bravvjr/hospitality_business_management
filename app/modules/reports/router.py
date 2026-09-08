"""Reports HTTP routes (Phase 2a/2b/2c)."""
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.deps import TenantContext, get_tenant_session
from app.modules.reports.deps import ReportsExportReader
from app.modules.reports.exports import ReportExportKey
from app.modules.reports.permissions import REPORTS_READ
from app.modules.reports.schemas import (
    ExpensesByCategoryRead,
    GroupBy,
    InventoryMovementSummaryRead,
    PnlRead,
    SalesByPaymentMethodRead,
    SalesByProductRead,
    SalesSortBy,
    SalesSummaryRead,
)
from app.modules.reports.service import ReportError, ReportsService
from app.modules.tenant.deps import require_module
from app.modules.tenant.entitlements import FINANCE

router = APIRouter()

ReportsReader = Annotated[TenantContext, Depends(require_module(FINANCE, REPORTS_READ))]


def _map_error(exc: ReportError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/sales/summary", response_model=SalesSummaryRead)
async def sales_summary(
    context: ReportsReader,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
    from_date: Annotated[date, Query(alias="from")],
    to_date: Annotated[date, Query(alias="to")],
    currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    group_by: Annotated[GroupBy | None, Query()] = None,
) -> SalesSummaryRead:
    try:
        return await ReportsService(session).sales_summary(
            tenant_id=context.tenant_id,
            from_date=from_date,
            to_date=to_date,
            currency=currency,
            group_by=group_by,
        )
    except ReportError as exc:
        raise _map_error(exc) from exc


@router.get("/expenses/by-category", response_model=ExpensesByCategoryRead)
async def expenses_by_category(
    context: ReportsReader,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
    from_date: Annotated[date, Query(alias="from")],
    to_date: Annotated[date, Query(alias="to")],
    currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
) -> ExpensesByCategoryRead:
    try:
        return await ReportsService(session).expenses_by_category(
            tenant_id=context.tenant_id,
            from_date=from_date,
            to_date=to_date,
            currency=currency,
        )
    except ReportError as exc:
        raise _map_error(exc) from exc


@router.get("/sales/by-product", response_model=SalesByProductRead)
async def sales_by_product(
    context: ReportsReader,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
    from_date: Annotated[date, Query(alias="from")],
    to_date: Annotated[date, Query(alias="to")],
    currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    sort: Annotated[SalesSortBy, Query()] = "revenue",
) -> SalesByProductRead:
    try:
        return await ReportsService(session).sales_by_product(
            tenant_id=context.tenant_id,
            from_date=from_date,
            to_date=to_date,
            currency=currency,
            limit=limit,
            sort_by=sort,
        )
    except ReportError as exc:
        raise _map_error(exc) from exc


@router.get("/sales/by-payment-method", response_model=SalesByPaymentMethodRead)
async def sales_by_payment_method(
    context: ReportsReader,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
    from_date: Annotated[date, Query(alias="from")],
    to_date: Annotated[date, Query(alias="to")],
    currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
) -> SalesByPaymentMethodRead:
    try:
        return await ReportsService(session).sales_by_payment_method(
            tenant_id=context.tenant_id,
            from_date=from_date,
            to_date=to_date,
            currency=currency,
        )
    except ReportError as exc:
        raise _map_error(exc) from exc


@router.get("/inventory/movements", response_model=InventoryMovementSummaryRead)
async def inventory_movements(
    context: ReportsReader,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
    from_date: Annotated[date, Query(alias="from")],
    to_date: Annotated[date, Query(alias="to")],
    movement_type: Annotated[str | None, Query(max_length=30)] = None,
) -> InventoryMovementSummaryRead:
    try:
        return await ReportsService(session).inventory_movements(
            tenant_id=context.tenant_id,
            from_date=from_date,
            to_date=to_date,
            movement_type=movement_type,
        )
    except ReportError as exc:
        raise _map_error(exc) from exc


@router.get("/exports/{report_key}.csv")
async def export_report_csv(
    report_key: ReportExportKey,
    context: ReportsExportReader,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
    from_date: Annotated[date, Query(alias="from")],
    to_date: Annotated[date, Query(alias="to")],
    currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    group_by: Annotated[GroupBy | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    sort: Annotated[SalesSortBy, Query()] = "revenue",
    movement_type: Annotated[str | None, Query(max_length=30)] = None,
) -> StreamingResponse:
    try:
        return await ReportsService(session).export_csv(
            report_key=report_key,
            tenant_id=context.tenant_id,
            from_date=from_date,
            to_date=to_date,
            currency=currency,
            group_by=group_by,
            limit=limit,
            sort_by=sort,
            movement_type=movement_type,
        )
    except ReportError as exc:
        raise _map_error(exc) from exc


@router.get("/pnl", response_model=PnlRead)
async def profit_and_loss(
    context: ReportsReader,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
    from_date: Annotated[date, Query(alias="from")],
    to_date: Annotated[date, Query(alias="to")],
    currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
) -> PnlRead:
    try:
        return await ReportsService(session).pnl(
            tenant_id=context.tenant_id,
            from_date=from_date,
            to_date=to_date,
            currency=currency,
        )
    except ReportError as exc:
        raise _map_error(exc) from exc
