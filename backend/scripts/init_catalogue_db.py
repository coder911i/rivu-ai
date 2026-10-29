"""Create schema in the explicitly configured, separate Catalogue Portal database.

Run once after provisioning the catalogue database:
    python scripts/init_catalogue_db.py
"""

import asyncio

from sqlalchemy.ext.asyncio import create_async_engine

from app.catalogue.auth_models import CatalogueBase
from app.core.config import settings
from app.catalogue.auth_db import _validated_catalogue_database_url


async def main() -> None:
    try:
        url = _validated_catalogue_database_url()
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    engine = create_async_engine(url, pool_pre_ping=True)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(CatalogueBase.metadata.create_all)
    finally:
        await engine.dispose()
    print("Catalogue Portal tables created in the configured catalogue database.")


if __name__ == "__main__":
    asyncio.run(main())
