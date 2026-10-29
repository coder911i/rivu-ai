"""SQLAlchemy User model."""

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Enum as SAEnum, Boolean, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    full_name: Mapped[str | None] = mapped_column(String(200))
    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    google_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)
    token_version: Mapped[int] = mapped_column(default=0, nullable=False, server_default="0")
    refresh_token_version: Mapped[int] = mapped_column(default=0, nullable=False, server_default="0")
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    email_verification_token_hash: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    email_verification_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_reset_token_hash: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    password_reset_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(
        SAEnum("active", "inactive", "suspended", "pending_verification", name="user_status"),
        nullable=False,
        default="active",
    )
    avatar_url: Mapped[str | None] = mapped_column(String)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Membership has another FK to users (invited_by), so explicitly bind
    # this relationship to the member's user_id foreign key.
    memberships: Mapped[list["Membership"]] = relationship(
        "Membership",
        foreign_keys="Membership.user_id",
        back_populates="user",
    )
    owned_orgs: Mapped[list["Organization"]] = relationship(
        "Organization", foreign_keys="Organization.owner_id", back_populates="owner"
    )

    def __repr__(self) -> str:
        return f"<User {self.email}>"
