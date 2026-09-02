"""Shared pytest fixtures (ADR-010)."""
import contextlib

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings, get_settings
from app.core.db import engine
from app.core.rate_limit import get_limiter
from app.main import create_app


def _settings_override(**overrides):
    return lambda: Settings(**overrides)


@pytest.fixture
def app():
    application = create_app()
    # Rate limiting is disabled by default in tests so the shared client IP does
    # not accumulate hits across unrelated tests; see rate_limited_client.
    application.dependency_overrides[get_settings] = _settings_override(rate_limit_enabled=False)
    return application


@contextlib.asynccontextmanager
async def _make_client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def client(app):
    async with _make_client(app) as ac:
        yield ac
    await engine.dispose()


@pytest.fixture
async def anonymous_client(app):
    """An independent client with its own cookie jar (for unauthenticated checks)."""
    async with _make_client(app) as ac:
        yield ac


@pytest.fixture
async def rate_limited_client():
    """A client whose app has rate limiting enabled with a small window."""
    application = create_app()
    application.dependency_overrides[get_settings] = _settings_override(
        rate_limit_enabled=True,
        auth_rate_limit_max=3,
        auth_rate_limit_window_seconds=60,
    )
    get_limiter().reset()
    async with _make_client(application) as ac:
        yield ac
    get_limiter().reset()
    await engine.dispose()
