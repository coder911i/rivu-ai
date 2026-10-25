"""Add revocable token version counters to users."""
from alembic import context, op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0002_token_versions"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if context.is_offline_mode():
        return
    # The bootstrap migration may have created these columns from current metadata.
    existing = {column["name"] for column in inspect(op.get_bind()).get_columns("users")}
    if "token_version" not in existing:
        op.add_column("users", sa.Column("token_version", sa.Integer(), server_default="0", nullable=False))
    if "refresh_token_version" not in existing:
        op.add_column("users", sa.Column("refresh_token_version", sa.Integer(), server_default="0", nullable=False))


def downgrade() -> None:
    if context.is_offline_mode():
        return
    existing = {column["name"] for column in inspect(op.get_bind()).get_columns("users")}
    if "refresh_token_version" in existing:
        op.drop_column("users", "refresh_token_version")
    if "token_version" in existing:
        op.drop_column("users", "token_version")
