"""FastAPI dependencies for tenant module entitlements (ADR-012)."""
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.deps import TenantContext, get_tenant_context, get_tenant_session
from app.modules.auth.repository import AuthRepository
from app.modules.tenant.repository import TenantRepository


def require_entitlement(module_key: str):
    """Reject requests when the active tenant does not have the module enabled."""

    async def _require_entitlement(
        context: Annotated[TenantContext, Depends(get_tenant_context)],
        session: Annotated[AsyncSession, Depends(get_tenant_session)],
    ) -> TenantContext:
        repo = TenantRepository(session)
        if not await repo.is_module_enabled(tenant_id=context.tenant_id, module_key=module_key):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Module not enabled for this tenant",
            )
        return context

    return _require_entitlement


def require_module(module_key: str, *required_permissions: str):
    """Require an enabled module and one or more RBAC permissions."""

    required = frozenset(required_permissions)

    async def _require_module(
        context: Annotated[TenantContext, Depends(get_tenant_context)],
        session: Annotated[AsyncSession, Depends(get_tenant_session)],
    ) -> TenantContext:
        tenant_repo = TenantRepository(session)
        if not await tenant_repo.is_module_enabled(
            tenant_id=context.tenant_id, module_key=module_key
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Module not enabled for this tenant",
            )
        auth_repo = AuthRepository(session)
        granted = await auth_repo.get_permission_keys_for_role(context.role_key)
        if not required.issubset(granted):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return context

    return _require_module
