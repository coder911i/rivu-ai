"""Merge the canonical and legacy initial-schema migration branches.

The legacy initial-schema revision is retained as a no-op for compatibility.
"""
from alembic import op

revision = "0005_merge_initial_heads"
down_revision = ("0004_align_model_types", "f5cbb61b8929")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Both parent branches are reconciled; schema changes are handled by the
    # canonical bootstrap and the linear migrations preceding this revision.
    pass


def downgrade() -> None:
    # A merge revision has no schema operations to reverse.
    pass
