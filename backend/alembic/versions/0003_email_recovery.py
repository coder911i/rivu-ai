"""Add email verification and password recovery state."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0003_email_recovery"
down_revision = "0002_token_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing = {column["name"] for column in inspect(op.get_bind()).get_columns("users")}
    if "email_verified" not in existing:
        op.add_column("users", sa.Column("email_verified", sa.Boolean(), server_default=sa.false(), nullable=False))
    if "email_verification_token_hash" not in existing:
        op.add_column("users", sa.Column("email_verification_token_hash", sa.String(64), nullable=True))
        op.create_index("ix_users_email_verification_token_hash", "users", ["email_verification_token_hash"], unique=True)
    if "email_verification_expires_at" not in existing:
        op.add_column("users", sa.Column("email_verification_expires_at", sa.DateTime(timezone=True), nullable=True))
    if "password_reset_token_hash" not in existing:
        op.add_column("users", sa.Column("password_reset_token_hash", sa.String(64), nullable=True))
        op.create_index("ix_users_password_reset_token_hash", "users", ["password_reset_token_hash"], unique=True)
    if "password_reset_expires_at" not in existing:
        op.add_column("users", sa.Column("password_reset_expires_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    existing = {column["name"] for column in inspect(op.get_bind()).get_columns("users")}
    for name in ("email_verification_token_hash", "password_reset_token_hash"):
        if name in existing:
            op.drop_index(f"ix_users_{name}", table_name="users")
    for name in ("password_reset_expires_at", "password_reset_token_hash", "email_verification_expires_at", "email_verification_token_hash", "email_verified"):
        if name in existing:
            op.drop_column("users", name)
