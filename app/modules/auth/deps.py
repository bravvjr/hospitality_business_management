"""FastAPI dependencies for auth and tenant context (ADR-003)."""
import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import apply_tenant_context, get_session
from app.core.security import InvalidTokenError, TokenPayload, decode_token
from app.modules.auth.models import Membership, User
from app.modules.auth.repository import AuthRepository


@dataclass(frozen=True, slots=True)
class TenantContext:
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    role_key: str
    user: User
    membership: Membership


def _extract_bearer_token(request: Request) -> str | None:
    authorization = request.headers.get("Authorization")
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def _decode_access_token(
    *,
    request: Request,
    settings: Settings,
    access_token: str | None,
) -> TokenPayload:
    token = access_token or _extract_bearer_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    try:
        payload = decode_token(token, settings=settings)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
    if payload.token_type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token required",
        )
    return payload


async def get_token_payload(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    access_token: Annotated[str | None, Cookie(alias="access_token")] = None,
) -> TokenPayload:
    token = request.cookies.get(settings.access_token_cookie_name, access_token)
    return _decode_access_token(request=request, settings=settings, access_token=token)


async def get_tenant_context(
    payload: Annotated[TokenPayload, Depends(get_token_payload)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TenantContext:
    repo = AuthRepository(session)
    user = await repo.get_user_by_id(payload.user_id)
    if user is None or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is unavailable",
        )

    membership = await repo.get_membership(user_id=payload.user_id, tenant_id=payload.tenant_id)
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant membership not found",
        )

    return TenantContext(
        user_id=user.id,
        tenant_id=membership.tenant_id,
        role_key=membership.role.key,
        user=user,
        membership=membership,
    )


async def get_tenant_session(
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AsyncGenerator[AsyncSession]:
    await apply_tenant_context(session, context.tenant_id)
    yield session


def require_permission(*required_permissions: str):
    required = frozenset(required_permissions)

    async def _require_permission(
        context: Annotated[TenantContext, Depends(get_tenant_context)],
        session: Annotated[AsyncSession, Depends(get_session)],
    ) -> TenantContext:
        repo = AuthRepository(session)
        granted = await repo.get_permission_keys_for_role(context.role_key)
        if not required.issubset(granted):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return context

    return _require_permission
