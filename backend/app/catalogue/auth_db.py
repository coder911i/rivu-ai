"""Database engine isolated from Rivu Data Refinery data."""

from typing import AsyncGenerator
from urllib.parse import parse_qsl, urlsplit

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
import structlog

from app.catalogue.auth_models import CatalogueBase
from app.core.config import settings
from app.core.database import _normalize_async_database_url, _safe_database_target

logger = structlog.get_logger(__name__)
_catalogue_engine = None
_catalogue_sessions = None


def _validated_catalogue_database_url() -> str:
    if not settings.CATALOGUE_DATABASE_URL:
        raise RuntimeError("CATALOGUE_DATABASE_URL must point to a dedicated Catalogue database")
    database_url = _normalize_async_database_url(settings.CATALOGUE_DATABASE_URL)
    if not database_url.startswith("postgresql+asyncpg://"):
        raise RuntimeError("CATALOGUE_DATABASE_URL must use PostgreSQL with asyncpg")
    parsed = urlsplit(database_url)
    primary = urlsplit(_normalize_async_database_url(settings.DATABASE_URL))
    if (parsed.hostname, parsed.port, parsed.path) == (primary.hostname, primary.port, primary.path):
        raise RuntimeError("CATALOGUE_DATABASE_URL must point to a different database from DATABASE_URL")
    return database_url


async def init_catalogue_db() -> None:
    """Connect only to the explicitly configured catalogue database."""
    global _catalogue_engine, _catalogue_sessions
    if not settings.CATALOGUE_DATABASE_URL:
        logger.warning("catalogue_database_not_configured")
        return
    if not settings.CATALOGUE_JWT_SECRET or len(settings.CATALOGUE_JWT_SECRET) < 32:
        raise RuntimeError("CATALOGUE_JWT_SECRET must be configured and at least 32 characters")

    database_url = _validated_catalogue_database_url()
    parsed = urlsplit(database_url)
    raw_query = dict(parse_qsl(urlsplit(settings.CATALOGUE_DATABASE_URL).query))
    connect_args = {}
    if raw_query.get("sslmode") != "disable" and parsed.hostname not in {"localhost", "127.0.0.1", "postgres", "catalogue-postgres"}:
        connect_args["ssl"] = "require"

    _catalogue_engine = create_async_engine(
        database_url,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        pool_pre_ping=True,
        connect_args=connect_args,
        echo=settings.DEBUG,
    )
    _catalogue_sessions = async_sessionmaker(_catalogue_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)
    async with _catalogue_engine.begin() as connection:
        await connection.execute(text("SELECT 1"))
        if settings.CATALOGUE_AUTO_CREATE_SCHEMA:
            await connection.run_sync(CatalogueBase.metadata.create_all)
        else:
            logger.info("catalogue_schema_migrations_required")
    logger.info("catalogue_database_initialized", target=_safe_database_target(database_url))


async def close_catalogue_db() -> None:
    global _catalogue_engine, _catalogue_sessions
    if _catalogue_engine:
        await _catalogue_engine.dispose()
    _catalogue_engine = None
    _catalogue_sessions = None


async def get_catalogue_session() -> AsyncGenerator[AsyncSession, None]:
    if _catalogue_sessions is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"message": "Catalogue Portal is not configured yet. Set its separate database and signing key.", "type": "catalogue_not_configured"},
        )
    async with _catalogue_sessions() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
