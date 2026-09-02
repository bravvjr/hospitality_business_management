"""Data access for auth entities."""
import uuid
from datetime import datetime

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.auth.models import Membership, Permission, RefreshSession, Role, User
from app.modules.tenant.models import Tenant


class AuthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_user_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self._session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_role_by_key(self, key: str) -> Role | None:
        result = await self._session.execute(select(Role).where(Role.key == key))
        return result.scalar_one_or_none()

    async def get_membership(
        self,
        *,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> Membership | None:
        result = await self._session.execute(
            select(Membership)
            .options(selectinload(Membership.role))
            .where(Membership.user_id == user_id, Membership.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def list_memberships(self, user_id: uuid.UUID) -> list[Membership]:
        result = await self._session.execute(
            select(Membership)
            .options(selectinload(Membership.role))
            .where(Membership.user_id == user_id)
            .order_by(Membership.created_at.asc())
        )
        return list(result.scalars().all())

    async def list_tenant_memberships(self, tenant_id: uuid.UUID) -> list[Membership]:
        result = await self._session.execute(
            select(Membership)
            .options(selectinload(Membership.role), selectinload(Membership.user))
            .where(Membership.tenant_id == tenant_id)
            .order_by(Membership.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_membership_by_id(self, membership_id: uuid.UUID) -> Membership | None:
        result = await self._session.execute(
            select(Membership)
            .options(selectinload(Membership.role), selectinload(Membership.user))
            .where(Membership.id == membership_id)
        )
        return result.scalar_one_or_none()

    async def count_memberships_with_role(self, *, tenant_id: uuid.UUID, role_key: str) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(Membership)
            .join(Role)
            .where(Membership.tenant_id == tenant_id, Role.key == role_key)
        )
        return int(result.scalar_one())

    async def list_roles(self) -> list[Role]:
        result = await self._session.execute(select(Role).order_by(Role.name.asc()))
        return list(result.scalars().all())

    async def get_permission_keys_for_role(self, role_key: str) -> set[str]:
        result = await self._session.execute(
            select(Permission.key)
            .join(Role.permissions)
            .where(Role.key == role_key)
        )
        return set(result.scalars().all())

    async def delete(self, entity: Membership) -> None:
        await self._session.delete(entity)

    async def get_tenant(self, tenant_id: uuid.UUID) -> Tenant | None:
        result = await self._session.execute(select(Tenant).where(Tenant.id == tenant_id))
        return result.scalar_one_or_none()

    async def get_ancestor_tenant_ids(self, tenant_id: uuid.UUID) -> list[uuid.UUID]:
        """Ancestors of a tenant (excluding itself), nearest parent first (ADR-012)."""
        result = await self._session.execute(
            text(
                """
                WITH RECURSIVE ancestors AS (
                    SELECT id, parent_tenant_id, 0 AS depth
                    FROM tenants WHERE id = :tid
                    UNION ALL
                    SELECT t.id, t.parent_tenant_id, a.depth + 1
                    FROM tenants t JOIN ancestors a ON t.id = a.parent_tenant_id
                )
                SELECT id FROM ancestors WHERE depth > 0 ORDER BY depth
                """
            ),
            {"tid": str(tenant_id)},
        )
        return [row[0] for row in result.all()]

    async def resolve_membership_for_tenant(
        self,
        *,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> Membership | None:
        """Effective membership for a tenant node: a direct membership if present,
        otherwise the nearest ancestor membership (downward RBAC inheritance, ADR-012).
        Returns the source membership; its role is the effective role.
        """
        direct = await self.get_membership(user_id=user_id, tenant_id=tenant_id)
        if direct is not None:
            return direct
        for ancestor_id in await self.get_ancestor_tenant_ids(tenant_id):
            inherited = await self.get_membership(user_id=user_id, tenant_id=ancestor_id)
            if inherited is not None:
                return inherited
        return None

    async def list_child_tenants(self, parent_tenant_id: uuid.UUID) -> list[Tenant]:
        result = await self._session.execute(
            select(Tenant)
            .where(Tenant.parent_tenant_id == parent_tenant_id)
            .order_by(Tenant.created_at.asc())
        )
        return list(result.scalars().all())

    async def add(self, entity: User | Tenant | Membership) -> None:
        self._session.add(entity)

    async def flush(self) -> None:
        await self._session.flush()

    async def create_refresh_session(
        self,
        *,
        jti: uuid.UUID,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        expires_at: datetime,
    ) -> None:
        self._session.add(
            RefreshSession(id=jti, user_id=user_id, tenant_id=tenant_id, expires_at=expires_at)
        )

    async def get_refresh_session(self, jti: uuid.UUID) -> RefreshSession | None:
        result = await self._session.execute(
            select(RefreshSession).where(RefreshSession.id == jti)
        )
        return result.scalar_one_or_none()

    async def revoke_refresh_session(self, jti: uuid.UUID) -> None:
        await self._session.execute(
            update(RefreshSession)
            .where(RefreshSession.id == jti, RefreshSession.revoked_at.is_(None))
            .values(revoked_at=func.now())
        )
