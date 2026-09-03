"""Tenant hierarchy management (ADR-012)."""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import apply_tenant_context
from app.modules.tenant.models import Tenant
from app.modules.tenant.repository import TenantRepository
from app.modules.tenant.schemas import SubTenantCreate


class TenantService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = TenantRepository(session)

    async def create_sub_tenant(
        self,
        *,
        active_tenant_id: uuid.UUID,
        payload: SubTenantCreate,
    ) -> Tenant:
        await apply_tenant_context(self._session, active_tenant_id)
        # Default the parent to the active tenant; otherwise it must be within the
        # active tenant's subtree so a caller can only build under what they manage.
        parent_id = payload.parent_tenant_id or active_tenant_id
        if not await self._repo.is_within_subtree(
            candidate_id=parent_id, root_id=active_tenant_id
        ):
            raise ValueError("Parent tenant is not within your tenant")

        parent = await self._repo.get(parent_id)
        if parent is None or parent.status != "active":
            raise ValueError("Parent tenant is unavailable")

        child = Tenant(
            name=payload.name,
            base_currency=payload.base_currency.upper(),
            parent_tenant_id=parent_id,
        )
        await self._repo.add(child)
        await self._session.commit()
        # Load server-generated columns (created_at/updated_at) for the response.
        await self._session.refresh(child)
        return child

    async def list_sub_tenants(self, *, parent_tenant_id: uuid.UUID) -> list[Tenant]:
        """Immediate children of the active tenant."""
        return await self._repo.list_children(parent_tenant_id)

    async def list_subtree(self, *, root_tenant_id: uuid.UUID) -> list[Tenant]:
        """All descendants of the active tenant (every level)."""
        return await self._repo.list_descendants(root_tenant_id)
