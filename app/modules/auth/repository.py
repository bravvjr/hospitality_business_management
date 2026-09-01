"""Data access for auth entities."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.auth.models import Membership, Role, User
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

    async def get_tenant(self, tenant_id: uuid.UUID) -> Tenant | None:
        result = await self._session.execute(select(Tenant).where(Tenant.id == tenant_id))
        return result.scalar_one_or_none()

    async def add(self, entity: User | Tenant | Membership) -> None:
        self._session.add(entity)

    async def flush(self) -> None:
        await self._session.flush()
