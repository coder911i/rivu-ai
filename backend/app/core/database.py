"""Async database engine and session management."""

from typing import AsyncGenerator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

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


def _normalize_async_database_url(url: str) -> str:
    """Ensure a PostgreSQL URL uses an asyncpg driver for the async engine."""
    normalized = url.strip()
    if normalized.startswith("postgresql+asyncpg://"):
        return normalized
    if normalized.startswith("postgresql://"):
        return "postgresql+asyncpg://" + normalized[len("postgresql://") :]
    return normalized


def _safe_database_target(url: str) -> str:
    """Return only the non-secret host/database portion for logs."""
    try:
        parsed = urlsplit(url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query.pop("password", None)
        query.pop("user", None)
        safe_netloc = parsed.hostname or "unknown"
        if parsed.port:
            safe_netloc = f"{safe_netloc}:{parsed.port}"
        return urlunsplit((parsed.scheme, safe_netloc, parsed.path, urlencode(query), ""))
    except Exception:
        return "configured"


async def init_db() -> None:
    """Initialize the async engine and verify the connection."""
    global _engine, _session_factory

    database_url = _normalize_async_database_url(settings.DATABASE_URL)
    if not database_url.startswith("postgresql+asyncpg://"):
        raise RuntimeError(
            "DATABASE_URL must be a PostgreSQL URL using the asyncpg driver. "
            "Use postgresql+asyncpg:// for the async backend."
        )

    _engine = create_async_engine(
        database_url,
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

    logger.info("database_initialized", target=_safe_database_target(database_url))


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
