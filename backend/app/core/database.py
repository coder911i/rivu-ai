"""Async database engine and session management."""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import event, text
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker | None = None


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""
    pass


async def init_db() -> None:
    """Initialize database engine and verify connection."""
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

    # Verify connection
    async with _engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info("database_initialized", url=settings.DATABASE_URL.split("@")[-1])


async def close_db() -> None:
    """Dispose database engine."""
    global _engine
    if _engine:
        await _engine.dispose()
        logger.info("database_closed")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session."""
    if _session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("Database not initialized.")
    return _engine
