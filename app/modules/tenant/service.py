"""Tenant hierarchy management (ADR-012)."""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

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
        parent_tenant_id: uuid.UUID,
        payload: SubTenantCreate,
    ) -> Tenant:
        parent = await self._repo.get(parent_tenant_id)
        if parent is None or parent.status != "active":
            raise ValueError("Parent tenant is unavailable")

        child = Tenant(
            name=payload.name,
            base_currency=payload.base_currency.upper(),
            parent_tenant_id=parent_tenant_id,
        )
        await self._repo.add(child)
        await self._session.commit()
        # Load server-generated columns (created_at/updated_at) for the response.
        await self._session.refresh(child)
        return child

    async def list_sub_tenants(self, *, parent_tenant_id: uuid.UUID) -> list[Tenant]:
        return await self._repo.list_children(parent_tenant_id)
