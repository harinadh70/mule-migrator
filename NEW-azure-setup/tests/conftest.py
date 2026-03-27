"""
Shared pytest fixtures for the MuleSoft-to-SpringBoot Migrator test suite.

Provides:
- ``settings``    — A test-mode ``Settings`` instance with safe defaults.
- ``app``         — A FastAPI application wired to the test settings.
- ``client``      — An ``httpx.AsyncClient`` bound to the test app.
- ``db_session``  — An async SQLAlchemy session backed by in-memory SQLite.
- ``mock_redis``  — A ``fakeredis.aioredis.FakeRedis`` instance.
"""

from __future__ import annotations

from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

# ---------------------------------------------------------------------------
# Settings fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def settings():
    """
    Return a ``Settings`` instance configured for the test environment.

    Overrides are applied via environment variables so the nested
    Pydantic settings classes pick them up correctly.
    """
    import os

    os.environ.setdefault("ENVIRONMENT", "testing")
    os.environ.setdefault("DEBUG", "true")
    os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
    os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
    os.environ.setdefault("RAG_ENABLED", "false")
    os.environ.setdefault("CORS_ORIGINS", "*")
    os.environ.setdefault("TRUSTED_HOSTS", "*")

    from api.config import Settings

    return Settings()


# ---------------------------------------------------------------------------
# FastAPI app fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def app(settings):
    """
    Build a FastAPI test application with dependency overrides.

    The lifespan is *not* executed — external services (DB, Redis, Qdrant)
    are individually mocked or replaced by in-memory equivalents.
    """
    from api.config import get_settings

    # Clear the lru_cache so our test settings take effect
    get_settings.cache_clear()

    with patch("api.config.get_settings", return_value=settings):
        from api.main import create_app

        test_app = create_app()

    # Override the settings dependency globally
    from api.dependencies import get_app_settings

    test_app.dependency_overrides[get_app_settings] = lambda: settings

    return test_app


# ---------------------------------------------------------------------------
# Async HTTP client fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client(app) -> AsyncGenerator:
    """
    Yield an ``httpx.AsyncClient`` that sends requests directly to the
    test ASGI app (no network I/O).
    """
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as ac:
        yield ac


# ---------------------------------------------------------------------------
# Database session fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_session():
    """
    Provide an async SQLAlchemy session backed by in-memory SQLite.

    Creates tables from the application's ``Base.metadata`` on setup and
    drops them on teardown.
    """
    try:
        from sqlalchemy.ext.asyncio import (
            AsyncSession,
            async_sessionmaker,
            create_async_engine,
        )

        from api.models import Base  # assumes all models import into api.models

        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            echo=False,
        )

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False,
        )

        async with session_factory() as session:
            yield session

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

        await engine.dispose()
    except ImportError:
        # If aiosqlite or models are not available, yield a mock
        yield AsyncMock(spec=["execute", "commit", "rollback", "close"])


# ---------------------------------------------------------------------------
# Mock Redis fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def mock_redis():
    """
    Return a ``fakeredis`` async instance for tests that need Redis.

    Falls back to an ``AsyncMock`` if ``fakeredis`` is not installed.
    """
    try:
        import fakeredis.aioredis

        redis = fakeredis.aioredis.FakeRedis()
        yield redis
        await redis.aclose()
    except ImportError:
        mock = AsyncMock()
        mock.ping = AsyncMock(return_value=True)
        mock.get = AsyncMock(return_value=None)
        mock.set = AsyncMock(return_value=True)
        mock.delete = AsyncMock(return_value=1)
        mock.aclose = AsyncMock()
        yield mock
