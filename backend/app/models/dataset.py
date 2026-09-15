"""SQLAlchemy Dataset and DatasetVersion models."""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    String, DateTime, ForeignKey, Integer, BigInteger, Numeric,
    Boolean, Text, func, ARRAY
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DataSource(Base):
    __tablename__ = "data_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_format: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="uploading"
    )
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    tags: Mapped[list] = mapped_column(ARRAY(String), default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="data_sources")
    versions: Mapped[list["DatasetVersion"]] = relationship(
        back_populates="data_source", order_by="DatasetVersion.version_number"
    )
    jobs: Mapped[list["Job"]] = relationship(back_populates="data_source")

    def __repr__(self) -> str:
        return f"<DataSource {self.name}>"


class DatasetVersion(Base):
    __tablename__ = "dataset_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    data_source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    version_label: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    storage_bucket: Mapped[str] = mapped_column(Text, nullable=False)
    file_format: Mapped[str] = mapped_column(String(20), nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    row_count: Mapped[int | None] = mapped_column(Integer)
    column_count: Mapped[int | None] = mapped_column(Integer)
    checksum: Mapped[str | None] = mapped_column(Text)
    parent_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dataset_versions.id")
    )
    transformation_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    quality_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    quality_delta: Mapped[float | None] = mapped_column(Numeric(5, 2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    data_source: Mapped["DataSource"] = relationship(back_populates="versions")
    profile: Mapped[Optional["DataProfile"]] = relationship(
        back_populates="dataset_version", uselist=False
    )
    quality_report: Mapped[Optional["QualityReport"]] = relationship(
        back_populates="dataset_version", uselist=False
    )

    def __repr__(self) -> str:
        return f"<DatasetVersion v{self.version_number} of {self.data_source_id}>"
