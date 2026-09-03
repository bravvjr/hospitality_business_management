"""FastAPI application factory (ADR-008).

`create_app()` is synchronous and I/O-free; resource lifecycle lives in `lifespan`.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings, validate_runtime_settings
from app.core.db import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: nothing to eagerly open (engine connects lazily).
    yield
    # Shutdown: release the connection pool.
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    validate_runtime_settings(settings)
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/", tags=["root"])
    async def root() -> dict[str, str]:
        return {
            "service": settings.app_name,
            "environment": settings.environment,
            "docs": "/docs",
            "health": f"{settings.api_v1_prefix}/health/live",
        }

    return app


app = create_app()
