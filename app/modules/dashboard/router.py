"""Dashboard HTTP routes (Phase 1 MVP)."""
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.deps import TenantContext, get_tenant_session, require_permission
from app.modules.dashboard.permissions import DASHBOARD_READ
from app.modules.dashboard.schemas import (
    DashboardLowStockRead,
    DashboardRecentRead,
    DashboardSummaryRead,
)
from app.modules.dashboard.service import DashboardService

router = APIRouter()

DashboardReader = Annotated[TenantContext, Depends(require_permission(DASHBOARD_READ))]


@router.get("/summary", response_model=DashboardSummaryRead)
async def dashboard_summary(
    context: DashboardReader,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
    target_date: Annotated[date | None, Query(alias="date")] = None,
    currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
) -> DashboardSummaryRead:
    try:
        return await DashboardService(session).summary(
            tenant_id=context.tenant_id,
            target_date=target_date or date.today(),
            currency=currency,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/recent", response_model=DashboardRecentRead)
async def dashboard_recent(
    context: DashboardReader,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> DashboardRecentRead:
    return await DashboardService(session).recent(tenant_id=context.tenant_id, limit=limit)


@router.get("/low-stock", response_model=list[DashboardLowStockRead])
async def dashboard_low_stock(
    context: DashboardReader,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[DashboardLowStockRead]:
    return await DashboardService(session).low_stock(tenant_id=context.tenant_id, limit=limit)
