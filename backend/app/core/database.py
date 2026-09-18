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
    """Ensure a PostgreSQL URL uses asyncpg and remove unsupported driver query args."""
    normalized = url.strip()
    if normalized.startswith("postgresql+asyncpg://"):
        pass
    elif normalized.startswith("postgresql://"):
        normalized = "postgresql+asyncpg://" + normalized[len("postgresql://") :]
    else:
        return normalized

    parsed = urlsplit(normalized)
    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    # asyncpg does not accept SQLAlchemy/psycopg query parameters such as
    # sslmode/channel_binding. TLS is configured below via connect_args.
    unsupported = {"sslmode", "channel_binding"}
    query = [(key, value) for key, value in pairs if key not in unsupported]
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), ""))


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
    """Initialize the engine and create any missing SQLAlchemy tables."""
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
        connect_args={"ssl": "require"},
        echo=settings.DEBUG,
    )

    _session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    # Import every model so Alembic/metadata can see all tables.
    import app.models  # noqa: F401

    async with _engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
        if settings.AUTO_CREATE_SCHEMA:
            # Development-only bootstrap. Production must use Alembic migrations.
            await conn.run_sync(Base.metadata.create_all)
        else:
            logger.info("database_schema_migrations_required", mode="production")

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
