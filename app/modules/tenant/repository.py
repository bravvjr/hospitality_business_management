"""Data access for tenants (ADR-012 hierarchy)."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tenant.models import Tenant


class TenantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, tenant_id: uuid.UUID) -> Tenant | None:
        result = await self._session.execute(select(Tenant).where(Tenant.id == tenant_id))
        return result.scalar_one_or_none()

    async def add(self, tenant: Tenant) -> None:
        self._session.add(tenant)

    async def list_children(self, parent_tenant_id: uuid.UUID) -> list[Tenant]:
        result = await self._session.execute(
            select(Tenant)
            .where(Tenant.parent_tenant_id == parent_tenant_id)
            .order_by(Tenant.created_at.asc())
        )
        return list(result.scalars().all())
