"""
Async SQLAlchemy engine + session factory. SQLite by default (zero infra),
swaps to Postgres via Settings.database_url with no code changes - both
speak the same async engine interface.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import Settings


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_db(settings: Settings) -> AsyncEngine:
    """Create the engine + session factory once, at app startup."""
    global _engine, _session_factory

    # SQLite needs this connect_arg for use with FastAPI's async/multi-task
    # access pattern; Postgres (asyncpg) ignores it harmlessly if present -
    # actually only pass it for sqlite URLs to avoid asyncpg rejecting an
    # unknown kwarg.
    connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

    _engine = create_async_engine(settings.database_url, echo=False, connect_args=connect_args)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


async def create_all_tables() -> None:
    """Dev/hackathon-speed table creation - no Alembic yet. Safe to call
    on every startup (CREATE TABLE IF NOT EXISTS semantics)."""
    assert _engine is not None, "init_db() must be called before create_all_tables()"
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields a session, closes it after the request."""
    assert _session_factory is not None, "init_db() must be called before get_session()"
    async with _session_factory() as session:
        yield session


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """For code that isn't inside a FastAPI request (e.g. the background
    scheduler jobs in core/scheduler.py), which can't use the
    Depends(get_session) generator pattern and needs to open/close its
    own session per job run."""
    assert _session_factory is not None, "init_db() must be called before get_session_factory()"
    return _session_factory
