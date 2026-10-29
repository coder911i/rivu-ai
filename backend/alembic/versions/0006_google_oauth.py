"""Add google_id column and make password_hash nullable for OAuth.

Revision ID: 0006_google_oauth
Revises: 0005_merge_initial_heads
Create Date: 2026-10-29 22:15:00
"""
from alembic import context, op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0006_google_oauth"
down_revision = "0005_merge_initial_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if context.is_offline_mode():
        op.add_column("users", sa.Column("google_id", sa.String(255), nullable=True))
        op.create_index("idx_users_google_id", "users", ["google_id"], unique=True)
        op.alter_column("users", "password_hash", existing_type=sa.String(), nullable=True)
        return

    bind = op.get_bind()
    inspector = inspect(bind)
    existing_cols = {col["name"] for col in inspector.get_columns("users")}
    if "google_id" not in existing_cols:
        op.add_column("users", sa.Column("google_id", sa.String(255), nullable=True))
        op.create_index("idx_users_google_id", "users", ["google_id"], unique=True)
    op.alter_column("users", "password_hash", existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    if context.is_offline_mode():
        op.drop_index("idx_users_google_id", table_name="users")
        op.drop_column("users", "google_id")
        op.alter_column("users", "password_hash", existing_type=sa.String(), nullable=False)
        return

    bind = op.get_bind()
    inspector = inspect(bind)
    existing_cols = {col["name"] for col in inspector.get_columns("users")}
    if "google_id" in existing_cols:
        op.drop_index("idx_users_google_id", table_name="users")
        op.drop_column("users", "google_id")
    op.alter_column("users", "password_hash", existing_type=sa.String(), nullable=False)
