"""POS HTTP routes (ADR-006)."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Page, Pagination, page_from
from app.modules.auth.deps import TenantContext, get_tenant_session, require_permission
from app.modules.pos.permissions import POS_READ, POS_WRITE
from app.modules.pos.schemas import (
    CompleteSaleRequest,
    OrderCreateRequest,
    OrderItemCreateRequest,
    OrderItemUpdateRequest,
    OrderRead,
)
from app.modules.pos.service import PosError, PosNotFoundError, PosService

router = APIRouter()

PosReader = Annotated[TenantContext, Depends(require_permission(POS_READ))]
PosWriter = Annotated[TenantContext, Depends(require_permission(POS_WRITE))]


def _map_error(exc: PosError) -> HTTPException:
    if isinstance(exc, PosNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/orders", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: OrderCreateRequest,
    context: PosWriter,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
) -> OrderRead:
    try:
        return await PosService(session).create_order(
            tenant_id=context.tenant_id,
            cashier_user_id=context.user_id,
            payload=payload,
        )
    except PosError as exc:
        raise _map_error(exc) from exc


@router.get("/orders", response_model=Page[OrderRead])
async def list_orders(
    context: PosReader,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
    pagination: Pagination,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> Page[OrderRead]:
    items, total = await PosService(session).list_orders(
        tenant_id=context.tenant_id,
        status=status_filter,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return page_from(items, total=total, pagination=pagination)


@router.get("/orders/{order_id}", response_model=OrderRead)
async def get_order(
    order_id: uuid.UUID,
    context: PosReader,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
) -> OrderRead:
    try:
        return await PosService(session).get_order(
            tenant_id=context.tenant_id, order_id=order_id
        )
    except PosError as exc:
        raise _map_error(exc) from exc


@router.post(
    "/orders/{order_id}/items",
    response_model=OrderRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_item(
    order_id: uuid.UUID,
    payload: OrderItemCreateRequest,
    context: PosWriter,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
) -> OrderRead:
    try:
        return await PosService(session).add_item(
            tenant_id=context.tenant_id, order_id=order_id, payload=payload
        )
    except PosError as exc:
        raise _map_error(exc) from exc


@router.patch("/orders/{order_id}/items/{item_id}", response_model=OrderRead)
async def update_item(
    order_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: OrderItemUpdateRequest,
    context: PosWriter,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
) -> OrderRead:
    try:
        return await PosService(session).update_item(
            tenant_id=context.tenant_id,
            order_id=order_id,
            item_id=item_id,
            payload=payload,
        )
    except PosError as exc:
        raise _map_error(exc) from exc


@router.delete("/orders/{order_id}/items/{item_id}", response_model=OrderRead)
async def remove_item(
    order_id: uuid.UUID,
    item_id: uuid.UUID,
    context: PosWriter,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
) -> OrderRead:
    try:
        return await PosService(session).remove_item(
            tenant_id=context.tenant_id, order_id=order_id, item_id=item_id
        )
    except PosError as exc:
        raise _map_error(exc) from exc


@router.post("/orders/{order_id}/complete", response_model=OrderRead)
async def complete_sale(
    order_id: uuid.UUID,
    payload: CompleteSaleRequest,
    context: PosWriter,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
) -> OrderRead:
    try:
        return await PosService(session).complete_sale(
            tenant_id=context.tenant_id,
            order_id=order_id,
            actor_user_id=context.user_id,
            payload=payload,
        )
    except PosError as exc:
        raise _map_error(exc) from exc
