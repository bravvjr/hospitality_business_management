"""Reports HTTP routes (Phase 2a)."""
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.deps import TenantContext, get_tenant_session
from app.modules.reports.permissions import REPORTS_READ
from app.modules.reports.schemas import (
    ExpensesByCategoryRead,
    GroupBy,
    PnlRead,
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
