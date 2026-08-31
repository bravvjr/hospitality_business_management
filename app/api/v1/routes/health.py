"""Health endpoints: liveness (no dependencies) and readiness (checks the DB)."""
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status as http_status
from starlette.responses import JSONResponse

from app.core.config import get_settings
from app.core.db import get_session
from app.schemas.health import HealthStatus, ReadyStatus

router = APIRouter(tags=["health"])
settings = get_settings()


@router.get("/health/live", response_model=HealthStatus)
async def liveness() -> HealthStatus:
    """Liveness probe — process is up. No external dependencies touched."""
    return HealthStatus(
        status="ok",
        service=settings.app_name,
        environment=settings.environment,
    )


@router.get("/health/ready")
async def readiness(session: Annotated[AsyncSession, Depends(get_session)]):
    """Readiness probe — verifies database connectivity."""
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unavailable", "database": "disconnected"},
        )
    return ReadyStatus(status="ok", database="connected")
