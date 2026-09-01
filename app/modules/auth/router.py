"""Auth HTTP routes (ADR-003)."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.core.security import InvalidCredentialsError, InvalidTokenError
from app.modules.auth.deps import TenantContext, get_tenant_context
from app.modules.auth.schemas import (
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    SessionRead,
    SwitchTenantRequest,
)
from app.modules.auth.service import AuthService

router = APIRouter()


def _set_auth_cookies(
    *,
    response: Response,
    settings: Settings,
    access_token: str,
    refresh_token: str,
) -> None:
    response.set_cookie(
        key=settings.access_token_cookie_name,
        value=access_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )
    response.set_cookie(
        key=settings.refresh_token_cookie_name,
        value=refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path="/",
    )


def _clear_auth_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(settings.access_token_cookie_name, path="/")
    response.delete_cookie(settings.refresh_token_cookie_name, path="/")


@router.post("/register", response_model=SessionRead, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SessionRead:
    service = AuthService(session, settings)
    try:
        session_read, access_token, refresh_token = await service.register(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    _set_auth_cookies(
        response=response,
        settings=settings,
        access_token=access_token,
        refresh_token=refresh_token,
    )
    return session_read


@router.post("/login", response_model=SessionRead)
async def login(
    payload: LoginRequest,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SessionRead:
    service = AuthService(session, settings)
    try:
        session_read, access_token, refresh_token = await service.login(
            email=payload.email,
            password=payload.password,
            tenant_id=payload.tenant_id,
        )
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    _set_auth_cookies(
        response=response,
        settings=settings,
        access_token=access_token,
        refresh_token=refresh_token,
    )
    return session_read


@router.post("/refresh", response_model=SessionRead)
async def refresh_session(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SessionRead:
    refresh_token = request.cookies.get(settings.refresh_token_cookie_name)
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing",
        )

    service = AuthService(session, settings)
    try:
        session_read, access_token, new_refresh = await service.refresh(refresh_token)
    except (InvalidCredentialsError, InvalidTokenError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    _set_auth_cookies(
        response=response,
        settings=settings,
        access_token=access_token,
        refresh_token=new_refresh,
    )
    return session_read


@router.post("/switch-tenant", response_model=SessionRead)
async def switch_tenant(
    payload: SwitchTenantRequest,
    response: Response,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SessionRead:
    service = AuthService(session, settings)
    try:
        session_read, access_token, refresh_token = await service.switch_tenant(
            user_id=context.user_id,
            tenant_id=payload.tenant_id,
        )
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    _set_auth_cookies(
        response=response,
        settings=settings,
        access_token=access_token,
        refresh_token=refresh_token,
    )
    return session_read


@router.get("/me", response_model=SessionRead)
async def me(
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SessionRead:
    service = AuthService(session, settings)
    try:
        return await service.get_session_for_user(
            user_id=context.user_id,
            tenant_id=context.tenant_id,
        )
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.post("/logout", response_model=MessageResponse)
async def logout(
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
) -> MessageResponse:
    _clear_auth_cookies(response, settings)
    return MessageResponse(message="Logged out")
