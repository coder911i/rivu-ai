"""Legacy initial-schema branch compatibility.

The canonical bootstrap is 0001_initial_schema, which creates the current ORM
metadata idempotently. The older generated f5cbb61b8929 migration duplicated
that schema and conflicted with the canonical bootstrap on fresh installs.
Keep this revision as a no-op so databases that already recorded it remain
compatible, while fresh installs use 0001_initial_schema.
"""
from alembic import op

revision = "f5cbb61b8929"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Intentionally no-op. 0001_initial_schema is the canonical bootstrap.
    pass


def downgrade() -> None:
    # No schema objects are created by this compatibility revision.
    pass
