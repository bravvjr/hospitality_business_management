"""Inventory HTTP routes (ADR-005)."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Page, Pagination, page_from
from app.modules.auth.deps import TenantContext, get_tenant_session, require_permission
from app.modules.inventory.permissions import INVENTORY_READ, INVENTORY_WRITE
from app.modules.inventory.schemas import (
    ProductCreateRequest,
    ProductRead,
    ProductUnitCreateRequest,
    ProductUnitRead,
    ProductUpdateRequest,
    StockAdjustmentRequest,
    StockLevelRead,
    StockMovementCreateRequest,
    StockMovementRead,
    UnitRead,
)
from app.modules.inventory.service import (
    InventoryError,
    InventoryNotFoundError,
    InventoryService,
)

router = APIRouter()

InventoryReader = Annotated[TenantContext, Depends(require_permission(INVENTORY_READ))]
InventoryWriter = Annotated[TenantContext, Depends(require_permission(INVENTORY_WRITE))]


def _map_error(exc: InventoryError) -> HTTPException:
    if isinstance(exc, InventoryNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/units", response_model=list[UnitRead])
async def list_units(
    _context: InventoryReader,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
) -> list[UnitRead]:
    return await InventoryService(session).list_units()


@router.get("/products", response_model=Page[ProductRead])
async def list_products(
    context: InventoryReader,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
    pagination: Pagination,
) -> Page[ProductRead]:
    items, total = await InventoryService(session).list_products(
        tenant_id=context.tenant_id,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return page_from(items, total=total, pagination=pagination)


@router.post("/products", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreateRequest,
    context: InventoryWriter,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
) -> ProductRead:
    try:
        return await InventoryService(session).create_product(
            tenant_id=context.tenant_id, payload=payload
        )
    except InventoryError as exc:
        raise _map_error(exc) from exc


@router.get("/products/{product_id}", response_model=ProductRead)
async def get_product(
    product_id: uuid.UUID,
    context: InventoryReader,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
) -> ProductRead:
    try:
        return await InventoryService(session).get_product(
            tenant_id=context.tenant_id, product_id=product_id
        )
    except InventoryError as exc:
        raise _map_error(exc) from exc


@router.patch("/products/{product_id}", response_model=ProductRead)
async def update_product(
    product_id: uuid.UUID,
    payload: ProductUpdateRequest,
    context: InventoryWriter,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
) -> ProductRead:
    try:
        return await InventoryService(session).update_product(
            tenant_id=context.tenant_id, product_id=product_id, payload=payload
        )
    except InventoryError as exc:
        raise _map_error(exc) from exc


@router.get("/products/{product_id}/units", response_model=list[ProductUnitRead])
async def list_product_units(
    product_id: uuid.UUID,
    context: InventoryReader,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
) -> list[ProductUnitRead]:
    try:
        return await InventoryService(session).list_product_units(
            tenant_id=context.tenant_id, product_id=product_id
        )
    except InventoryError as exc:
        raise _map_error(exc) from exc


@router.post(
    "/products/{product_id}/units",
    response_model=ProductUnitRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_product_unit(
    product_id: uuid.UUID,
    payload: ProductUnitCreateRequest,
    context: InventoryWriter,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
) -> ProductUnitRead:
    try:
        return await InventoryService(session).add_product_unit(
            tenant_id=context.tenant_id, product_id=product_id, payload=payload
        )
    except InventoryError as exc:
        raise _map_error(exc) from exc


@router.post(
    "/stock/receipts",
    response_model=StockMovementRead,
    status_code=status.HTTP_201_CREATED,
)
async def stock_receipt(
    payload: StockMovementCreateRequest,
    context: InventoryWriter,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
) -> StockMovementRead:
    try:
        return await InventoryService(session).record_receipt(
            tenant_id=context.tenant_id,
            actor_user_id=context.user_id,
            payload=payload,
        )
    except InventoryError as exc:
        raise _map_error(exc) from exc


@router.post(
    "/stock/usages",
    response_model=StockMovementRead,
    status_code=status.HTTP_201_CREATED,
)
async def stock_usage(
    payload: StockMovementCreateRequest,
    context: InventoryWriter,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
) -> StockMovementRead:
    try:
        return await InventoryService(session).record_usage(
            tenant_id=context.tenant_id,
            actor_user_id=context.user_id,
            payload=payload,
        )
    except InventoryError as exc:
        raise _map_error(exc) from exc


@router.post(
    "/stock/adjustments",
    response_model=StockMovementRead,
    status_code=status.HTTP_201_CREATED,
)
async def stock_adjustment(
    payload: StockAdjustmentRequest,
    context: InventoryWriter,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
) -> StockMovementRead:
    try:
        return await InventoryService(session).record_adjustment(
            tenant_id=context.tenant_id,
            actor_user_id=context.user_id,
            payload=payload,
        )
    except InventoryError as exc:
        raise _map_error(exc) from exc


@router.get("/stock/levels", response_model=Page[StockLevelRead])
async def stock_levels(
    context: InventoryReader,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
    pagination: Pagination,
) -> Page[StockLevelRead]:
    items, total = await InventoryService(session).list_stock_levels(
        tenant_id=context.tenant_id,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return page_from(items, total=total, pagination=pagination)


@router.get("/stock/levels/low", response_model=Page[StockLevelRead])
async def low_stock_levels(
    context: InventoryReader,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
    pagination: Pagination,
) -> Page[StockLevelRead]:
    items, total = await InventoryService(session).list_low_stock(
        tenant_id=context.tenant_id,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return page_from(items, total=total, pagination=pagination)


@router.get("/stock/movements", response_model=Page[StockMovementRead])
async def stock_movements(
    context: InventoryReader,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
    pagination: Pagination,
    product_id: uuid.UUID | None = None,
) -> Page[StockMovementRead]:
    try:
        items, total = await InventoryService(session).list_movements(
            tenant_id=context.tenant_id,
            product_id=product_id,
            limit=pagination.limit,
            offset=pagination.offset,
        )
    except InventoryError as exc:
        raise _map_error(exc) from exc
    return page_from(items, total=total, pagination=pagination)
