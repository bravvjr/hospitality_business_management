"""Data access for tenants (ADR-012 hierarchy)."""
import uuid

from sqlalchemy import select, text
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

    async def _descendant_ids(self, root_id: uuid.UUID) -> list[uuid.UUID]:
        """All descendant tenant ids (excluding the root), ordered by depth."""
        result = await self._session.execute(
            text(
                """
                WITH RECURSIVE descendants AS (
                    SELECT id, parent_tenant_id, 0 AS depth
                    FROM tenants WHERE id = :rid
                    UNION ALL
                    SELECT t.id, t.parent_tenant_id, d.depth + 1
                    FROM tenants t JOIN descendants d ON t.parent_tenant_id = d.id
                )
                SELECT id FROM descendants WHERE depth > 0 ORDER BY depth
                """
            ),
            {"rid": str(root_id)},
        )
        return [row[0] for row in result.all()]

    async def list_descendants(self, root_id: uuid.UUID) -> list[Tenant]:
        ids = await self._descendant_ids(root_id)
        if not ids:
            return []
        result = await self._session.execute(select(Tenant).where(Tenant.id.in_(ids)))
        by_id = {t.id: t for t in result.scalars().all()}
        return [by_id[i] for i in ids if i in by_id]

    async def is_within_subtree(self, *, candidate_id: uuid.UUID, root_id: uuid.UUID) -> bool:
        """Whether candidate_id is root_id itself or one of its descendants."""
        if candidate_id == root_id:
            return True
        return candidate_id in set(await self._descendant_ids(root_id))
