"""Initial ORM-backed database baseline.

The previous project used Base.metadata.create_all() during application startup.
This revision captures that same ORM schema behind an explicit Alembic revision,
so production startup can be migration-driven without relying on application
startup to mutate the database schema.
"""

from alembic import op
from app.core.database import Base
import app.models  # noqa: F401

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, checkfirst=True)


def downgrade() -> None:
    # Deliberately non-destructive. Production data must never be dropped by
    # an accidental migration rollback.
    pass
