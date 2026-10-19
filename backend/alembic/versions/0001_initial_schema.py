"""Initial schema bootstrap for existing and fresh Rivu databases.

The migration is idempotent for tables already created from db/schema.sql.
Future schema changes should use explicit, revisioned Alembic operations.
"""
from alembic import op

from app.core.database import Base
import app.models  # noqa: F401

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # checkfirst protects databases that were initialized from db/schema.sql.
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    # Dropping the initial schema would destroy customer data. Use a tested
    # database restore plan instead of an automated destructive downgrade.
    raise RuntimeError(
        "The initial Rivu schema migration is non-destructive and cannot be downgraded."
    )
