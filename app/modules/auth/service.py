"""Authentication business logic (ADR-003)."""
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

        tenant = Tenant(
            name=payload.tenant_name,
            base_currency=payload.base_currency.upper(),
        )
        user = User(
            email=payload.email.lower(),
            password_hash=hash_password(payload.password),
        )
        await self._repo.add(tenant)
        await self._repo.add(user)
        await self._repo.flush()

        membership = Membership(
            user_id=user.id,
            tenant_id=tenant.id,
            role_id=owner_role.id,
        )
        await self._repo.add(membership)
        await self._session.commit()

        membership = await self._repo.get_membership(user_id=user.id, tenant_id=tenant.id)
        if membership is None:
            raise RuntimeError("Membership missing after registration")

        session = self._build_session_read(user=user, tenant=tenant, membership=membership)
        tokens = self._issue_tokens(user_id=user.id, membership=membership)
        return session, tokens[0], tokens[1]

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

        memberships = await self._repo.list_memberships(user.id)
        if not memberships:
            raise InvalidCredentialsError("User has no tenant memberships")

        membership = self._select_membership(memberships, tenant_id)
        tenant = await self._repo.get_tenant(membership.tenant_id)
        if tenant is None or tenant.status != "active":
            raise InvalidCredentialsError("Tenant is unavailable")

        session = self._build_session_read(user=user, tenant=tenant, membership=membership)
        tokens = self._issue_tokens(user_id=user.id, membership=membership)
        return session, tokens[0], tokens[1]

    async def refresh(self, refresh_token: str) -> tuple[SessionRead, str, str]:
        payload = decode_token(refresh_token, settings=self._settings)
        if payload.token_type != "refresh":
            raise InvalidTokenError("Refresh token required")

        user = await self._repo.get_user_by_id(payload.user_id)
        if user is None or user.status != "active":
            raise InvalidCredentialsError("User is unavailable")

        membership = await self._repo.get_membership(
            user_id=payload.user_id,
            tenant_id=payload.tenant_id,
        )
        if membership is None:
            raise InvalidCredentialsError("Membership is unavailable")

        tenant = await self._repo.get_tenant(membership.tenant_id)
        if tenant is None or tenant.status != "active":
            raise InvalidCredentialsError("Tenant is unavailable")

        session = self._build_session_read(user=user, tenant=tenant, membership=membership)
        tokens = self._issue_tokens(user_id=user.id, membership=membership)
        return session, tokens[0], tokens[1]

    async def switch_tenant(
        self,
        *,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> tuple[SessionRead, str, str]:
        user = await self._repo.get_user_by_id(user_id)
        if user is None or user.status != "active":
            raise InvalidCredentialsError("User is unavailable")

        membership = await self._repo.get_membership(user_id=user_id, tenant_id=tenant_id)
        if membership is None:
            raise InvalidCredentialsError("Membership not found for tenant")

        tenant = await self._repo.get_tenant(tenant_id)
        if tenant is None or tenant.status != "active":
            raise InvalidCredentialsError("Tenant is unavailable")

        session = self._build_session_read(user=user, tenant=tenant, membership=membership)
        tokens = self._issue_tokens(user_id=user.id, membership=membership)
        return session, tokens[0], tokens[1]

    async def get_session_for_user(
        self,
        *,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> SessionRead:
        user = await self._repo.get_user_by_id(user_id)
        if user is None or user.status != "active":
            raise InvalidCredentialsError("User is unavailable")

        membership = await self._repo.get_membership(user_id=user_id, tenant_id=tenant_id)
        if membership is None:
            raise InvalidCredentialsError("Membership not found for tenant")

        tenant = await self._repo.get_tenant(tenant_id)
        if tenant is None:
            raise InvalidCredentialsError("Tenant is unavailable")

        return self._build_session_read(user=user, tenant=tenant, membership=membership)

    def _issue_tokens(self, *, user_id: uuid.UUID, membership: Membership) -> tuple[str, str]:
        role_key = membership.role.key
        access = create_access_token(
            user_id=user_id,
            tenant_id=membership.tenant_id,
            role_key=role_key,
            settings=self._settings,
        )
        refresh = create_refresh_token(
            user_id=user_id,
            tenant_id=membership.tenant_id,
            role_key=role_key,
            settings=self._settings,
        )
        return access, refresh

    @staticmethod
    def _select_membership(
        memberships: list[Membership],
        tenant_id: uuid.UUID | None,
    ) -> Membership:
        if tenant_id is None:
            return memberships[0]
        for membership in memberships:
            if membership.tenant_id == tenant_id:
                return membership
        raise InvalidCredentialsError("Membership not found for tenant")

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
