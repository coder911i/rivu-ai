"""SQLAlchemy Profiling models."""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey, Integer, BigInteger, Numeric, Boolean, Text, func, ARRAY
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DataProfile(Base):
    __tablename__ = "data_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dataset_versions.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    column_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_row_pct: Mapped[float | None] = mapped_column(Numeric(6, 3))
    total_null_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_null_pct: Mapped[float | None] = mapped_column(Numeric(6, 3))
    total_cell_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    encoding: Mapped[str | None] = mapped_column(String(50))
    delimiter: Mapped[str | None] = mapped_column(String(10))
    has_header: Mapped[bool] = mapped_column(Boolean, default=True)
    sample_rows: Mapped[list | None] = mapped_column(JSONB)
    profiled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    profiling_duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    dataset_version: Mapped["DatasetVersion"] = relationship(back_populates="profile")
    column_profiles: Mapped[list["ColumnProfile"]] = relationship(
        back_populates="data_profile", order_by="ColumnProfile.column_index"
    )

    def __repr__(self) -> str:
        return f"<DataProfile rows={self.row_count} cols={self.column_count}>"


class ColumnProfile(Base):
    __tablename__ = "column_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    data_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dataset_versions.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    column_index: Mapped[int] = mapped_column(Integer, nullable=False)
    column_name: Mapped[str] = mapped_column(String(300), nullable=False)
    inferred_type: Mapped[str | None] = mapped_column(String(50))
    semantic_type: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
    ai_semantic_type: Mapped[str | None] = mapped_column(String(100))
    ai_semantic_reason: Mapped[str | None] = mapped_column(Text)
    null_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    null_pct: Mapped[float | None] = mapped_column(Numeric(6, 3))
    non_null_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unique_count: Mapped[int | None] = mapped_column(Integer)
    uniqueness_pct: Mapped[float | None] = mapped_column(Numeric(6, 3))
    is_constant: Mapped[bool] = mapped_column(Boolean, default=False)
    is_unique: Mapped[bool] = mapped_column(Boolean, default=False)
    numeric_min: Mapped[float | None] = mapped_column(Numeric)
    numeric_max: Mapped[float | None] = mapped_column(Numeric)
    numeric_mean: Mapped[float | None] = mapped_column(Numeric)
    numeric_median: Mapped[float | None] = mapped_column(Numeric)
    numeric_std_dev: Mapped[float | None] = mapped_column(Numeric)
    numeric_q1: Mapped[float | None] = mapped_column(Numeric)
    numeric_q3: Mapped[float | None] = mapped_column(Numeric)
    numeric_skewness: Mapped[float | None] = mapped_column(Numeric)
    string_min_length: Mapped[int | None] = mapped_column(Integer)
    string_max_length: Mapped[int | None] = mapped_column(Integer)
    string_avg_length: Mapped[float | None] = mapped_column(Numeric)
    date_min: Mapped[str | None] = mapped_column(Text)
    date_max: Mapped[str | None] = mapped_column(Text)
    date_formats: Mapped[list | None] = mapped_column(ARRAY(String))
    value_frequency: Mapped[dict | None] = mapped_column(JSONB)
    sample_values: Mapped[list | None] = mapped_column(ARRAY(String))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    data_profile: Mapped["DataProfile"] = relationship(back_populates="column_profiles")

    def __repr__(self) -> str:
        return f"<ColumnProfile {self.column_name} ({self.semantic_type})>"
