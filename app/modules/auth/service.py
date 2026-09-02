"""Authentication business logic (ADR-003 / ADR-012).

Tenant access resolves through the tenant hierarchy: a direct membership, or the
nearest ancestor membership (downward inheritance). Tokens are always scoped to
the ACTIVE tenant node; the effective role comes from the source membership.
"""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import (
    InvalidCredentialsError,
    InvalidTokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.modules.auth.models import Membership, User
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import RegisterRequest, SessionRead, TenantSummary
from app.modules.tenant.models import Tenant


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self._session = session
        self._repo = AuthRepository(session)
        self._settings = settings or get_settings()

    async def register(self, payload: RegisterRequest) -> tuple[SessionRead, str, str]:
        existing = await self._repo.get_user_by_email(payload.email.lower())
        if existing is not None:
            raise ValueError("A user with this email already exists")

        owner_role = await self._repo.get_role_by_key("owner")
        if owner_role is None:
            raise RuntimeError("Owner role is not seeded")

        tenant = Tenant(name=payload.tenant_name, base_currency=payload.base_currency.upper())
        user = User(email=payload.email.lower(), password_hash=hash_password(payload.password))
        await self._repo.add(tenant)
        await self._repo.add(user)
        await self._repo.flush()

        # Assign the role via the relationship so it stays loaded (no re-query).
        membership = Membership(user_id=user.id, tenant_id=tenant.id, role=owner_role)
        await self._repo.add(membership)
        await self._session.commit()

        return self._session_and_tokens(user=user, source_membership=membership, tenant=tenant)

    async def login(
        self,
        *,
        email: str,
        password: str,
        tenant_id: uuid.UUID | None = None,
    ) -> tuple[SessionRead, str, str]:
        user = await self._repo.get_user_by_email(email.lower())
        if user is None or user.status != "active":
            raise InvalidCredentialsError("Invalid email or password")
        if not verify_password(password, user.password_hash):
            raise InvalidCredentialsError("Invalid email or password")

        target_tenant_id = tenant_id
        if target_tenant_id is None:
            memberships = await self._repo.list_memberships(user.id)
            if not memberships:
                raise InvalidCredentialsError("User has no tenant memberships")
            target_tenant_id = memberships[0].tenant_id

        membership, tenant = await self._authorize(user_id=user.id, tenant_id=target_tenant_id)
        return self._session_and_tokens(user=user, source_membership=membership, tenant=tenant)

    async def refresh(self, refresh_token: str) -> tuple[SessionRead, str, str]:
        payload = decode_token(refresh_token, settings=self._settings)
        if payload.token_type != "refresh":
            raise InvalidTokenError("Refresh token required")

        user = await self._active_user(payload.user_id)
        membership, tenant = await self._authorize(user_id=user.id, tenant_id=payload.tenant_id)
        return self._session_and_tokens(user=user, source_membership=membership, tenant=tenant)

    async def switch_tenant(
        self,
        *,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> tuple[SessionRead, str, str]:
        user = await self._active_user(user_id)
        membership, tenant = await self._authorize(user_id=user_id, tenant_id=tenant_id)
        return self._session_and_tokens(user=user, source_membership=membership, tenant=tenant)

    async def build_session(
        self,
        *,
        user: User,
        membership: Membership,
        active_tenant_id: uuid.UUID,
    ) -> SessionRead:
        """Build a session view for the active tenant from an already-loaded user +
        (source) membership (e.g. /me), fetching only the active tenant summary."""
        tenant = await self._repo.get_tenant(active_tenant_id)
        if tenant is None:
            raise InvalidCredentialsError("Tenant is unavailable")
        return self._build_session_read(user=user, tenant=tenant, membership=membership)

    async def _active_user(self, user_id: uuid.UUID) -> User:
        user = await self._repo.get_user_by_id(user_id)
        if user is None or user.status != "active":
            raise InvalidCredentialsError("User is unavailable")
        return user

    async def _authorize(
        self,
        *,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> tuple[Membership, Tenant]:
        """Resolve effective (direct or inherited) access to a tenant node."""
        membership = await self._repo.resolve_membership_for_tenant(
            user_id=user_id, tenant_id=tenant_id
        )
        if membership is None:
            raise InvalidCredentialsError("No access to tenant")
        tenant = await self._repo.get_tenant(tenant_id)
        if tenant is None or tenant.status != "active":
            raise InvalidCredentialsError("Tenant is unavailable")
        return membership, tenant

    def _session_and_tokens(
        self,
        *,
        user: User,
        source_membership: Membership,
        tenant: Tenant,
    ) -> tuple[SessionRead, str, str]:
        role_key = source_membership.role.key
        session = self._build_session_read(user=user, tenant=tenant, membership=source_membership)
        access = create_access_token(
            user_id=user.id, tenant_id=tenant.id, role_key=role_key, settings=self._settings
        )
        refresh = create_refresh_token(
            user_id=user.id, tenant_id=tenant.id, role_key=role_key, settings=self._settings
        )
        return session, access, refresh

    @staticmethod
    def _build_session_read(
        *,
        user: User,
        tenant: Tenant,
        membership: Membership,
    ) -> SessionRead:
        return SessionRead(
            user=user,
            tenant=TenantSummary(
                id=tenant.id,
                name=tenant.name,
                base_currency=tenant.base_currency,
            ),
            membership=membership,
        )
