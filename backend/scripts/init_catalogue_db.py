"""Create schema in the explicitly configured, separate Catalogue Portal database.

Run once after provisioning the catalogue database:
    python scripts/init_catalogue_db.py
"""

import asyncio
import sys
from pathlib import Path

# Allow `python scripts/init_catalogue_db.py` from the backend directory to
# import the sibling `app` package, as documented for local setup.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

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
