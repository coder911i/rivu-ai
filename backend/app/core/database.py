"""Async database engine and session management."""

from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker | None = None


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""
    pass


async def init_db() -> None:
    """Initialize the async engine and verify the connection."""
    global _engine, _session_factory

    _engine = create_async_engine(
        settings.DATABASE_URL,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        pool_pre_ping=True,
        echo=settings.DEBUG,
    )

    _session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    async with _engine.begin() as conn:
        await conn.execute(text("SELECT 1"))

    # Never log credentials; only log the host/database portion.
    safe_db_target = settings.DATABASE_URL.split("@")[-1].split("?")[0]
    logger.info("database_initialized", target=safe_db_target)


async def close_db() -> None:
    """Dispose database engine."""
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("database_closed")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a transaction-scoped session."""
    if _session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")

    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("Database not initialized.")
    return _engine
