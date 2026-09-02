"""Sub-tenant (branch) HTTP routes (ADR-012).

A parent-tenant admin manages child tenants; downward RBAC inheritance means no
separate membership at the child is required to administer it.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.modules.auth.deps import TenantContext, require_permission
from app.modules.auth.permissions import TENANT_READ, TENANT_WRITE
from app.modules.tenant.schemas import SubTenantCreate, TenantRead
from app.modules.tenant.service import TenantService

router = APIRouter()

TenantReader = Annotated[TenantContext, Depends(require_permission(TENANT_READ))]
TenantWriter = Annotated[TenantContext, Depends(require_permission(TENANT_WRITE))]


@router.get("", response_model=list[TenantRead])
async def list_sub_tenants(
    context: TenantReader,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[TenantRead]:
    """Immediate children of the active tenant."""
    service = TenantService(session)
    return await service.list_sub_tenants(parent_tenant_id=context.tenant_id)


@router.get("/tree", response_model=list[TenantRead])
async def list_sub_tenant_tree(
    context: TenantReader,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[TenantRead]:
    """All descendants of the active tenant (every level); build the tree client-side
    from each node's parent_tenant_id."""
    service = TenantService(session)
    return await service.list_subtree(root_tenant_id=context.tenant_id)


@router.post("", response_model=TenantRead, status_code=status.HTTP_201_CREATED)
async def create_sub_tenant(
    payload: SubTenantCreate,
    context: TenantWriter,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TenantRead:
    service = TenantService(session)
    try:
        return await service.create_sub_tenant(
            active_tenant_id=context.tenant_id, payload=payload
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
