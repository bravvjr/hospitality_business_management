"""Shared pytest fixtures (ADR-010)."""
import contextlib

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import engine
from app.main import create_app


@pytest.fixture
def app():
    return create_app()


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
