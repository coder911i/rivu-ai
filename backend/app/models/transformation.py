"""SQLAlchemy Transformation models."""

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Integer, Numeric, Boolean, Text, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TransformationPlan(Base):
    __tablename__ = "transformation_plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dataset_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ai_analysis_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    plan_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="planned")
    operations: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    total_operations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_quality_gain: Mapped[float | None] = mapped_column(Numeric(5, 2))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    runs: Mapped[list["TransformationRun"]] = relationship(back_populates="plan")

    def __repr__(self) -> str:
        return f"<TransformationPlan status={self.status} ops={self.total_operations}>"


class TransformationRun(Base):
    __tablename__ = "transformation_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transformation_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transformation_plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dataset_versions.id", ondelete="CASCADE"), nullable=False
    )
    output_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dataset_versions.id")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    executed_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="running")
    operations_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    operations_applied: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    operations_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    operations_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_modified: Mapped[int | None] = mapped_column(Integer)
    quality_before: Mapped[float | None] = mapped_column(Numeric(5, 2))
    quality_after: Mapped[float | None] = mapped_column(Numeric(5, 2))
    quality_delta: Mapped[float | None] = mapped_column(Numeric(5, 2))
    execution_log: Mapped[list] = mapped_column(JSONB, default=list)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    plan: Mapped["TransformationPlan"] = relationship(back_populates="runs")

    def __repr__(self) -> str:
        return f"<TransformationRun status={self.status}>"
