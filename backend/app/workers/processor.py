"""
Background worker for dataset processing pipeline.
Runs: profile → quality → AI analysis (async).
"""

import io
import traceback
from datetime import datetime, timezone
from uuid import UUID

import polars as pl
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


async def process_dataset_async(
    job_id: str,
    version_id: str,
    data_source_id: str,
    org_id: str,
    raw_bytes: bytes,
    file_format: str,
):
    """Full processing pipeline run in background."""
    from app.core.database import _session_factory
    from app.models.quality import Job, JobLog, QualityReport, QualityIssue
    from app.models.profile import DataProfile, ColumnProfile
    from app.models.dataset import DataSource, DatasetVersion
    from app.profiler.engine import profile_dataframe
    from app.profiler.quality import calculate_quality_report
    from app.ingestion.parser import parse_to_polars

    async with _session_factory() as db:
        try:
            # ── Update job to processing ──────────────
            from sqlalchemy import select
            job_result = await db.execute(select(Job).where(Job.id == job_id))
            job = job_result.scalar_one()
            job.status = "processing"
            job.started_at = datetime.now(timezone.utc)
            job.progress_pct = 5
            job.progress_message = "Parsing file..."
            await db.commit()

            # ── Parse file ────────────────────────────
            try:
                df, parse_meta = parse_to_polars(raw_bytes, file_format, "upload")
            except Exception as e:
                await _fail_job(db, job, f"Failed to parse file: {e}")
                return

            job.progress_pct = 20
            job.progress_message = "Profiling dataset..."
            await db.commit()

            # ── Profile ───────────────────────────────
            try:
                profile_data = profile_dataframe(df, org_id)
            except Exception as e:
                await _fail_job(db, job, f"Profiling failed: {e}")
                return

            # Persist DataProfile
            profile = DataProfile(
                dataset_version_id=version_id,
                organization_id=org_id,
                row_count=profile_data["row_count"],
                column_count=profile_data["column_count"],
                duplicate_row_count=profile_data["duplicate_row_count"],
                duplicate_row_pct=profile_data["duplicate_row_pct"],
                total_null_count=profile_data["total_null_count"],
                total_null_pct=profile_data["total_null_pct"],
                total_cell_count=profile_data["total_cell_count"],
                encoding=parse_meta.get("encoding"),
                delimiter=parse_meta.get("delimiter"),
                has_header=True,
                sample_rows=profile_data["sample_rows"],
                profiling_duration_ms=profile_data["profiling_duration_ms"],
            )
            db.add(profile)
            await db.flush()

            # Persist ColumnProfiles
            for col_data in profile_data["columns"]:
                cp = ColumnProfile(
                    data_profile_id=profile.id,
                    dataset_version_id=version_id,
                    organization_id=org_id,
                    column_index=col_data["column_index"],
                    column_name=col_data["column_name"],
                    inferred_type=col_data["inferred_type"],
                    semantic_type=col_data["semantic_type"],
                    null_count=col_data["null_count"],
                    null_pct=col_data["null_pct"],
                    non_null_count=col_data["non_null_count"],
                    unique_count=col_data["unique_count"],
                    uniqueness_pct=col_data["uniqueness_pct"],
                    is_constant=col_data["is_constant"],
                    is_unique=col_data["is_unique"],
                    numeric_min=col_data.get("numeric_min"),
                    numeric_max=col_data.get("numeric_max"),
                    numeric_mean=col_data.get("numeric_mean"),
                    numeric_median=col_data.get("numeric_median"),
                    numeric_std_dev=col_data.get("numeric_std_dev"),
                    numeric_q1=col_data.get("numeric_q1"),
                    numeric_q3=col_data.get("numeric_q3"),
                    numeric_skewness=col_data.get("numeric_skewness"),
                    string_min_length=col_data.get("string_min_length"),
                    string_max_length=col_data.get("string_max_length"),
                    string_avg_length=col_data.get("string_avg_length"),
                    date_min=col_data.get("date_min"),
                    date_max=col_data.get("date_max"),
                    date_formats=col_data.get("date_formats"),
                    value_frequency=col_data.get("value_frequency"),
                    sample_values=col_data.get("sample_values"),
                )
                db.add(cp)

            job.progress_pct = 60
            job.progress_message = "Calculating quality score..."
            await db.commit()

            # ── Quality report ────────────────────────
            try:
                quality_data = calculate_quality_report(profile_data, profile_data["columns"])
            except Exception as e:
                logger.error("quality_calc_failed", error=str(e))
                quality_data = {"overall_score": 0, "issues": [], "total_issues": 0}

            qr = QualityReport(
                dataset_version_id=version_id,
                organization_id=org_id,
                overall_score=quality_data["overall_score"],
                completeness_score=quality_data.get("completeness_score"),
                validity_score=quality_data.get("validity_score"),
                consistency_score=quality_data.get("consistency_score"),
                uniqueness_score=quality_data.get("uniqueness_score"),
                integrity_score=quality_data.get("integrity_score"),
                total_issues=quality_data["total_issues"],
                critical_issues=quality_data.get("critical_issues", 0),
                high_issues=quality_data.get("high_issues", 0),
                medium_issues=quality_data.get("medium_issues", 0),
                low_issues=quality_data.get("low_issues", 0),
            )
            db.add(qr)
            await db.flush()

            # Persist issues
            for issue in quality_data.get("issues", []):
                qi = QualityIssue(
                    quality_report_id=qr.id,
                    dataset_version_id=version_id,
                    organization_id=org_id,
                    issue_type=issue["issue_type"],
                    severity=issue["severity"],
                    title=issue["title"],
                    description=issue.get("description"),
                    affected_column=issue.get("affected_column"),
                    affected_row_count=issue.get("affected_row_count"),
                    affected_row_pct=issue.get("affected_row_pct"),
                    evidence=issue.get("evidence"),
                    suggested_fix=issue.get("suggested_fix"),
                    auto_fixable=issue.get("auto_fixable", False),
                )
                db.add(qi)

            # ── Update version with stats ─────────────
            version_result = await db.execute(
                select(DatasetVersion).where(DatasetVersion.id == version_id)
            )
            version = version_result.scalar_one()
            version.row_count = profile_data["row_count"]
            version.column_count = profile_data["column_count"]
            version.quality_score = quality_data["overall_score"]

            # ── Update DataSource status ──────────────
            ds_result = await db.execute(
                select(DataSource).where(DataSource.id == data_source_id)
            )
            ds = ds_result.scalar_one()
            ds.status = "profiled"

            # ── Complete job ──────────────────────────
            job.status = "completed"
            job.progress_pct = 100
            job.progress_message = "Profiling complete"
            job.completed_at = datetime.now(timezone.utc)
            if job.started_at:
                job.duration_ms = int(
                    (job.completed_at - job.started_at).total_seconds() * 1000
                )
            job.result = {
                "rows": profile_data["row_count"],
                "columns": profile_data["column_count"],
                "quality_score": quality_data["overall_score"],
                "issues_found": quality_data["total_issues"],
                "profile_id": str(profile.id),
                "quality_report_id": str(qr.id),
            }

            await db.commit()
            logger.info(
                "processing_complete",
                job_id=job_id,
                rows=profile_data["row_count"],
                quality=quality_data["overall_score"],
            )

        except Exception as e:
            logger.error("processing_pipeline_error", job_id=job_id, error=str(e), traceback=traceback.format_exc())
            try:
                await _fail_job(db, job, str(e))
            except Exception:
                pass


async def _fail_job(db, job, error_message: str):
    job.status = "failed"
    job.error_message = error_message
    job.completed_at = datetime.now(timezone.utc)
    if job.started_at:
        job.duration_ms = int(
            (job.completed_at - job.started_at).total_seconds() * 1000
        )
    await db.commit()
    logger.error("job_failed", job_id=str(job.id), error=error_message)
