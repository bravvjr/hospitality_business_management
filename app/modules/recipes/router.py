"""Recipes / BOM HTTP routes (Phase 2a)."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Page, Pagination, page_from
from app.modules.auth.deps import TenantContext, get_tenant_session
from app.modules.recipes.permissions import RECIPES_READ, RECIPES_WRITE
from app.modules.recipes.schemas import (
    RecipeCostRead,
    RecipeCreateRequest,
    RecipeItemCreateRequest,
    RecipeItemRead,
    RecipeItemUpdateRequest,
    RecipeRead,
    RecipeSummaryRead,
    RecipeUpdateRequest,
)
from app.modules.recipes.service import RecipeError, RecipeNotFoundError, RecipeService
from app.modules.tenant.deps import require_module
from app.modules.tenant.entitlements import INVENTORY

router = APIRouter()

RecipesReader = Annotated[TenantContext, Depends(require_module(INVENTORY, RECIPES_READ))]
RecipesWriter = Annotated[TenantContext, Depends(require_module(INVENTORY, RECIPES_WRITE))]


def _map_error(exc: RecipeError) -> HTTPException:
    if isinstance(exc, RecipeNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("", response_model=Page[RecipeSummaryRead])
async def list_recipes(
    context: RecipesReader,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
    pagination: Pagination,
    product_id: Annotated[uuid.UUID | None, Query()] = None,
) -> Page[RecipeSummaryRead]:
    items, total = await RecipeService(session).list_recipes(
        tenant_id=context.tenant_id,
        product_id=product_id,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return page_from(items, total=total, pagination=pagination)


@router.post("", response_model=RecipeRead, status_code=status.HTTP_201_CREATED)
async def create_recipe(
    payload: RecipeCreateRequest,
    context: RecipesWriter,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
) -> RecipeRead:
    try:
        return await RecipeService(session).create_recipe(
            tenant_id=context.tenant_id, payload=payload
        )
    except RecipeError as exc:
        raise _map_error(exc) from exc


@router.get("/{recipe_id}/cost", response_model=RecipeCostRead)
async def get_recipe_cost(
    recipe_id: uuid.UUID,
    context: RecipesReader,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
) -> RecipeCostRead:
    try:
        return await RecipeService(session).get_recipe_cost(
            tenant_id=context.tenant_id, recipe_id=recipe_id
        )
    except RecipeError as exc:
        raise _map_error(exc) from exc


@router.get("/{recipe_id}", response_model=RecipeRead)
async def get_recipe(
    recipe_id: uuid.UUID,
    context: RecipesReader,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
) -> RecipeRead:
    try:
        return await RecipeService(session).get_recipe(
            tenant_id=context.tenant_id, recipe_id=recipe_id
        )
    except RecipeError as exc:
        raise _map_error(exc) from exc


@router.patch("/{recipe_id}", response_model=RecipeRead)
async def update_recipe(
    recipe_id: uuid.UUID,
    payload: RecipeUpdateRequest,
    context: RecipesWriter,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
) -> RecipeRead:
    try:
        return await RecipeService(session).update_recipe(
            tenant_id=context.tenant_id,
            recipe_id=recipe_id,
            payload=payload,
        )
    except RecipeError as exc:
        raise _map_error(exc) from exc


@router.delete("/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recipe(
    recipe_id: uuid.UUID,
    context: RecipesWriter,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
) -> None:
    try:
        await RecipeService(session).delete_recipe(
            tenant_id=context.tenant_id, recipe_id=recipe_id
        )
    except RecipeError as exc:
        raise _map_error(exc) from exc


@router.post(
    "/{recipe_id}/items",
    response_model=RecipeItemRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_recipe_item(
    recipe_id: uuid.UUID,
    payload: RecipeItemCreateRequest,
    context: RecipesWriter,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
) -> RecipeItemRead:
    try:
        return await RecipeService(session).add_item(
            tenant_id=context.tenant_id,
            recipe_id=recipe_id,
            payload=payload,
        )
    except RecipeError as exc:
        raise _map_error(exc) from exc


@router.patch("/{recipe_id}/items/{item_id}", response_model=RecipeItemRead)
async def update_recipe_item(
    recipe_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: RecipeItemUpdateRequest,
    context: RecipesWriter,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
) -> RecipeItemRead:
    try:
        return await RecipeService(session).update_item(
            tenant_id=context.tenant_id,
            recipe_id=recipe_id,
            item_id=item_id,
            payload=payload,
        )
    except RecipeError as exc:
        raise _map_error(exc) from exc


@router.delete("/{recipe_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recipe_item(
    recipe_id: uuid.UUID,
    item_id: uuid.UUID,
    context: RecipesWriter,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
) -> None:
    try:
        await RecipeService(session).delete_item(
            tenant_id=context.tenant_id,
            recipe_id=recipe_id,
            item_id=item_id,
        )
    except RecipeError as exc:
        raise _map_error(exc) from exc
