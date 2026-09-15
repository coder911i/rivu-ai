"""SQLAlchemy Quality and Job models."""

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Integer, BigInteger, Numeric, Boolean, Text, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class QualityReport(Base):
    __tablename__ = "quality_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dataset_versions.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    overall_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    completeness_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    validity_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    consistency_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    uniqueness_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    integrity_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    completeness_weight: Mapped[float] = mapped_column(Numeric(4, 2), default=0.25)
    validity_weight: Mapped[float] = mapped_column(Numeric(4, 2), default=0.25)
    consistency_weight: Mapped[float] = mapped_column(Numeric(4, 2), default=0.20)
    uniqueness_weight: Mapped[float] = mapped_column(Numeric(4, 2), default=0.15)
    integrity_weight: Mapped[float] = mapped_column(Numeric(4, 2), default=0.15)
    total_issues: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    critical_issues: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    high_issues: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    medium_issues: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    low_issues: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    dataset_version: Mapped["DatasetVersion"] = relationship(back_populates="quality_report")
    issues: Mapped[list["QualityIssue"]] = relationship(back_populates="quality_report")

    def __repr__(self) -> str:
        return f"<QualityReport score={self.overall_score}>"


class QualityIssue(Base):
    __tablename__ = "quality_issues"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quality_report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quality_reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dataset_versions.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    issue_type: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    affected_column: Mapped[str | None] = mapped_column(String(300))
    affected_row_count: Mapped[int | None] = mapped_column(Integer)
    affected_row_pct: Mapped[float | None] = mapped_column(Numeric(6, 3))
    evidence: Mapped[dict | None] = mapped_column(JSONB)
    suggested_fix: Mapped[str | None] = mapped_column(Text)
    auto_fixable: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    quality_report: Mapped["QualityReport"] = relationship(back_populates="issues")

    def __repr__(self) -> str:
        return f"<QualityIssue {self.issue_type} severity={self.severity}>"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="queued", index=True)
    data_source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_sources.id", ondelete="SET NULL"), index=True
    )
    dataset_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dataset_versions.id", ondelete="SET NULL")
    )
    transformation_plan_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    progress_pct: Mapped[int | None] = mapped_column(Integer, default=0)
    progress_message: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    error_traceback: Mapped[str | None] = mapped_column(Text)
    queued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    data_source: Mapped["DataSource"] = relationship(back_populates="jobs")
    logs: Mapped[list["JobLog"]] = relationship(back_populates="job")

    def __repr__(self) -> str:
        return f"<Job {self.job_type} status={self.status}>"


class JobLog(Base):
    __tablename__ = "job_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    level: Mapped[str] = mapped_column(String(10), nullable=False, default="INFO")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    job: Mapped["Job"] = relationship(back_populates="logs")
