"""
Async SQLAlchemy 2.0 database engine, session management, and base model.

Uses asyncpg as the PostgreSQL driver with a connection pool sized
between 5 and 20 connections by default.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import AsyncGenerator
from uuid import uuid4

from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import DateTime, String

from api.config import get_settings

# ── Naming convention for constraints (Alembic-friendly) ──────────

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)

# ── Engine & Session Factory (lazily created) ─────────────────────

_engine = None
_async_session_factory = None


def _get_engine():
    """Create or return the cached async engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database.url,
            echo=settings.database.echo,
            pool_size=settings.database.pool_min_size,
            max_overflow=settings.database.pool_max_size - settings.database.pool_min_size,
            pool_recycle=settings.database.pool_recycle_seconds,
            pool_pre_ping=True,
            pool_timeout=30,
        )
    return _engine


def _get_session_factory():
    """Create or return the cached async session factory."""
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            bind=_get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _async_session_factory


# ── FastAPI Dependency ────────────────────────────────────────────


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield an async database session and ensure it is closed afterward.

    Usage as a FastAPI dependency:
        @router.get("/items")
        async def list_items(db: AsyncSession = Depends(get_db_session)):
            ...
    """
    session_factory = _get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Lifecycle Helpers ─────────────────────────────────────────────


async def init_db() -> None:
    """
    Initialize the database: verify connectivity and create tables
    if they do not exist (development convenience; use Alembic in prod).
    """
    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Dispose the engine connection pool."""
    global _engine, _async_session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _async_session_factory = None


# ── Base Model ────────────────────────────────────────────────────


class Base(AsyncAttrs, DeclarativeBase):
    """
    Base class for all ORM models.

    Provides:
      - id: UUID primary key
      - created_at: timestamp with timezone
      - updated_at: auto-updating timestamp
    """

    metadata = metadata

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
