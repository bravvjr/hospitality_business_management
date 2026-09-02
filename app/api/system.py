"""System / ops endpoints: liveness and DB-backed readiness.

These are cross-cutting operational probes, not a domain module.
"""
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status as http_status
from starlette.responses import JSONResponse

from app.core.config import get_settings
from app.core.db import get_session

router = APIRouter(tags=["system"])
settings = get_settings()


class HealthStatus(BaseModel):
    status: str
    service: str
    environment: str


class ReadyStatus(BaseModel):
    status: str
    database: str


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
