"""Expenses HTTP routes (Phase 1 finance MVP)."""
import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Page, Pagination, page_from
from app.modules.auth.deps import TenantContext, get_tenant_session
from app.modules.expenses.permissions import EXPENSES_READ, EXPENSES_WRITE
from app.modules.expenses.schemas import (
    ExpenseCategoryCreateRequest,
    ExpenseCategoryRead,
    ExpenseCategoryUpdateRequest,
    ExpenseCreateRequest,
    ExpenseRead,
    ExpenseSummaryRead,
    ExpenseUpdateRequest,
)
from app.modules.expenses.service import ExpenseError, ExpenseNotFoundError, ExpenseService
from app.modules.tenant.deps import require_module
from app.modules.tenant.entitlements import FINANCE

router = APIRouter()

ExpensesReader = Annotated[TenantContext, Depends(require_module(FINANCE, EXPENSES_READ))]
ExpensesWriter = Annotated[TenantContext, Depends(require_module(FINANCE, EXPENSES_WRITE))]


def _map_error(exc: ExpenseError) -> HTTPException:
    if isinstance(exc, ExpenseNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/categories", response_model=Page[ExpenseCategoryRead])
async def list_categories(
    _context: ExpensesReader,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
    pagination: Pagination,
) -> Page[ExpenseCategoryRead]:
    items, total = await ExpenseService(session).list_categories(
        tenant_id=_context.tenant_id,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return page_from(items, total=total, pagination=pagination)


@router.post(
    "/categories",
    response_model=ExpenseCategoryRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_category(
    payload: ExpenseCategoryCreateRequest,
    context: ExpensesWriter,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
) -> ExpenseCategoryRead:
    try:
        return await ExpenseService(session).create_category(
            tenant_id=context.tenant_id, payload=payload
        )
    except ExpenseError as exc:
        raise _map_error(exc) from exc


@router.patch("/categories/{category_id}", response_model=ExpenseCategoryRead)
async def update_category(
    category_id: uuid.UUID,
    payload: ExpenseCategoryUpdateRequest,
    context: ExpensesWriter,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
) -> ExpenseCategoryRead:
    try:
        return await ExpenseService(session).update_category(
            tenant_id=context.tenant_id,
            category_id=category_id,
            payload=payload,
        )
    except ExpenseError as exc:
        raise _map_error(exc) from exc


@router.get("/expenses", response_model=Page[ExpenseRead])
async def list_expenses(
    context: ExpensesReader,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
    pagination: Pagination,
    category_id: uuid.UUID | None = None,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
) -> Page[ExpenseRead]:
    items, total = await ExpenseService(session).list_expenses(
        tenant_id=context.tenant_id,
        limit=pagination.limit,
        offset=pagination.offset,
        category_id=category_id,
        from_date=from_date,
        to_date=to_date,
    )
    return page_from(items, total=total, pagination=pagination)


@router.post("/expenses", response_model=ExpenseRead, status_code=status.HTTP_201_CREATED)
async def create_expense(
    payload: ExpenseCreateRequest,
    context: ExpensesWriter,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
) -> ExpenseRead:
    try:
        return await ExpenseService(session).create_expense(
            tenant_id=context.tenant_id,
            actor_user_id=context.user_id,
            payload=payload,
        )
    except ExpenseError as exc:
        raise _map_error(exc) from exc


@router.get("/expenses/{expense_id}", response_model=ExpenseRead)
async def get_expense(
    expense_id: uuid.UUID,
    context: ExpensesReader,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
) -> ExpenseRead:
    try:
        return await ExpenseService(session).get_expense(
            tenant_id=context.tenant_id, expense_id=expense_id
        )
    except ExpenseError as exc:
        raise _map_error(exc) from exc


@router.patch("/expenses/{expense_id}", response_model=ExpenseRead)
async def update_expense(
    expense_id: uuid.UUID,
    payload: ExpenseUpdateRequest,
    context: ExpensesWriter,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
) -> ExpenseRead:
    try:
        return await ExpenseService(session).update_expense(
            tenant_id=context.tenant_id,
            expense_id=expense_id,
            payload=payload,
        )
    except ExpenseError as exc:
        raise _map_error(exc) from exc


@router.get("/summary", response_model=ExpenseSummaryRead)
async def expense_summary(
    context: ExpensesReader,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
    from_date: Annotated[date, Query(alias="from")],
    to_date: Annotated[date, Query(alias="to")],
    currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
) -> ExpenseSummaryRead:
    try:
        return await ExpenseService(session).summarize(
            tenant_id=context.tenant_id,
            from_date=from_date,
            to_date=to_date,
            currency=currency,
        )
    except ExpenseError as exc:
        raise _map_error(exc) from exc
