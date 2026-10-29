"""Independent persistence models for the Catalogue Portal."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class CatalogueBase(DeclarativeBase):
    """Metadata belongs only to the separate catalogue database."""


class CatalogueAccount(CatalogueBase):
    __tablename__ = "catalogue_accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CatalogueWorkspace(CatalogueBase):
    __tablename__ = "catalogue_workspaces"
    __table_args__ = (UniqueConstraint("owner_id", name="uq_catalogue_workspace_owner"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("catalogue_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CatalogueSessionData(CatalogueBase):
    __tablename__ = "catalogue_sessions"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("catalogue_workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_format: Mapped[str] = mapped_column(String(20), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_records: Mapped[list] = mapped_column(JSONB, nullable=False)
    mappings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    products: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    template_id: Mapped[str] = mapped_column(String(100), nullable=False, default="standard_ecommerce")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class CatalogueSavedTemplate(CatalogueBase):
    __tablename__ = "catalogue_saved_templates"
    __table_args__ = (UniqueConstraint("workspace_id", "template_id", name="uq_catalogue_workspace_template"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("catalogue_workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    template_id: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
