"""Staff management for the current tenant (ADR-003)."""
import secrets
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.modules.auth.models import Membership, User
from app.modules.auth.repository import AuthRepository
from app.modules.auth.roles import OWNER, assert_assignable_role
from app.modules.auth.schemas import (
    StaffCreateRequest,
    StaffMemberRead,
    StaffStatusUpdateRequest,
    StaffUpdateRequest,
)


class StaffError(Exception):
    """Business rule violation for staff operations."""


class StaffService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = AuthRepository(session)

    async def list_staff(self, *, tenant_id: uuid.UUID) -> list[StaffMemberRead]:
        memberships = await self._repo.list_tenant_memberships(tenant_id)
        return [self._to_staff_read(m) for m in memberships]

    async def list_roles(self):
        return await self._repo.list_roles()

    async def add_staff(
        self,
        *,
        tenant_id: uuid.UUID,
        actor_role: str,
        payload: StaffCreateRequest,
    ) -> StaffMemberRead:
        try:
            assert_assignable_role(actor_role=actor_role, role_key=payload.role_key)
        except ValueError as exc:
            raise StaffError(str(exc)) from exc

        role = await self._repo.get_role_by_key(payload.role_key)
        if role is None:
            raise StaffError(f"Unknown role: {payload.role_key}")

        email = payload.email.lower()
        user = await self._repo.get_user_by_email(email)

        if user is None:
            if not payload.password:
                raise StaffError("Password is required when creating a new user")
            user = User(email=email, password_hash=hash_password(payload.password))
            await self._repo.add(user)
            await self._repo.flush()
        else:
            existing = await self._repo.get_membership(user_id=user.id, tenant_id=tenant_id)
            if existing is not None:
                raise StaffError("User is already a member of this tenant")
            if user.status != "active":
                raise StaffError("User account is not active")

        membership = Membership(user_id=user.id, tenant_id=tenant_id, role_id=role.id)
        await self._repo.add(membership)
        await self._session.commit()

        membership = await self._repo.get_membership_by_id(membership.id)
        if membership is None:
            raise RuntimeError("Membership missing after creation")
        return self._to_staff_read(membership)

    async def update_staff_role(
        self,
        *,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        actor_role: str,
        membership_id: uuid.UUID,
        payload: StaffUpdateRequest,
    ) -> StaffMemberRead:
        membership = await self._get_tenant_membership(
            tenant_id=tenant_id, membership_id=membership_id
        )

        try:
            assert_assignable_role(actor_role=actor_role, role_key=payload.role_key)
        except ValueError as exc:
            raise StaffError(str(exc)) from exc

        new_role = await self._repo.get_role_by_key(payload.role_key)
        if new_role is None:
            raise StaffError(f"Unknown role: {payload.role_key}")

        if membership.role.key == OWNER and payload.role_key != OWNER:
            await self._ensure_not_last_owner(tenant_id=tenant_id, membership_id=membership.id)

        if (
            membership.user_id == actor_user_id
            and membership.role.key == OWNER
            and payload.role_key != OWNER
        ):
            raise StaffError("Owners cannot demote themselves; transfer ownership first")

        membership.role_id = new_role.id
        await self._session.commit()
        await self._session.refresh(membership, attribute_names=["role"])

        return self._to_staff_read(membership)

    async def remove_staff(
        self,
        *,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        membership_id: uuid.UUID,
    ) -> None:
        membership = await self._get_tenant_membership(
            tenant_id=tenant_id, membership_id=membership_id
        )

        if membership.user_id == actor_user_id:
            raise StaffError("You cannot remove your own membership")

        if membership.role.key == OWNER:
            await self._ensure_not_last_owner(tenant_id=tenant_id, membership_id=membership.id)

        await self._repo.delete(membership)
        await self._session.commit()

    async def update_staff_status(
        self,
        *,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        membership_id: uuid.UUID,
        payload: StaffStatusUpdateRequest,
    ) -> StaffMemberRead:
        membership = await self._get_tenant_membership(
            tenant_id=tenant_id, membership_id=membership_id
        )
        user = membership.user

        if user.id == actor_user_id:
            raise StaffError("You cannot change your own account status")

        if payload.status == "inactive" and membership.role.key == OWNER:
            await self._ensure_not_last_owner(tenant_id=tenant_id, membership_id=membership.id)

        if user.status == payload.status:
            return self._to_staff_read(membership)

        user.status = payload.status
        await self._session.commit()
        await self._session.refresh(membership, attribute_names=["user"])

        return self._to_staff_read(membership)

    async def _get_tenant_membership(
        self,
        *,
        tenant_id: uuid.UUID,
        membership_id: uuid.UUID,
    ) -> Membership:
        membership = await self._repo.get_membership_by_id(membership_id)
        if membership is None or membership.tenant_id != tenant_id:
            raise StaffError("Staff member not found")
        return membership

    async def _ensure_not_last_owner(
        self, *, tenant_id: uuid.UUID, membership_id: uuid.UUID
    ) -> None:
        owner_count = await self._repo.count_memberships_with_role(
            tenant_id=tenant_id, role_key=OWNER
        )
        if owner_count <= 1:
            membership = await self._repo.get_membership_by_id(membership_id)
            if membership is not None and membership.role.key == OWNER:
                raise StaffError("Cannot remove or demote the last owner")

    @staticmethod
    def _to_staff_read(membership: Membership) -> StaffMemberRead:
        return StaffMemberRead(membership=membership, user=membership.user)


def generate_temporary_password() -> str:
    """Generate a one-time password for staff onboarding (caller delivers out-of-band)."""
    return secrets.token_urlsafe(12)
