"""Approved transformation execution and preview endpoints."""
import io
import json
from datetime import datetime, timezone
from uuid import UUID

import polars as pl
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import get_current_user, require_org_role
from app.core.storage import get_storage, build_storage_key, compute_checksum
from app.core.exceptions import http_not_found
from app.models.user import User
from app.models.organization import Membership
from app.models.dataset import DataSource, DatasetVersion
from app.models.transformation import TransformationPlan, TransformationRun
from app.models.profile import DataProfile, ColumnProfile
from app.models.quality import QualityReport, QualityIssue
from app.profiler.engine import profile_dataframe
from app.profiler.quality import calculate_quality_report
from app.cleaning.engine import TransformationEngine, generate_transformation_preview
from app.ingestion.parser import parse_to_polars

router = APIRouter()


class ExecutePlanRequest(BaseModel):
    plan_id: UUID
    operation_indexes: list[int] | None = Field(default=None, description="Optional subset of approved plan operations")


async def _org(user: User, db: AsyncSession) -> UUID:
    result = await db.execute(
        select(Membership.organization_id).where(
            Membership.user_id == user.id
        ).limit(1)
    )
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(403, "No organization found")
    return org


async def _dataset(dataset_id: UUID, user: User, db: AsyncSession):
    org = await _org(user, db)
    result = await db.execute(select(DataSource).where(
        DataSource.id == dataset_id, DataSource.organization_id == org
    ))
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(404, "Dataset not found")
    version = (await db.execute(select(DatasetVersion).where(
        DatasetVersion.data_source_id == ds.id,
        DatasetVersion.version_number == ds.current_version,
    ))).scalar_one_or_none()
    if not version:
        raise HTTPException(404, "Dataset version not found")
    return ds, version, org


async def _load_dataframe(version: DatasetVersion) -> tuple[pl.DataFrame, bytes]:
    raw = await get_storage().download_file(version.storage_key)
    df, _ = parse_to_polars(raw, version.file_format, version.storage_key)
    return df, raw


@router.post("/{dataset_id}/transform/preview")
async def preview_plan(
    dataset_id: UUID,
    body: ExecutePlanRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    _, version, _ = await _dataset(dataset_id, current_user, db)
    await require_org_role(current_user, db, {"owner", "admin", "editor"})
    plan = (await db.execute(select(TransformationPlan).where(
        TransformationPlan.id == body.plan_id,
        TransformationPlan.dataset_version_id == version.id,
    ))).scalar_one_or_none()
    if not plan:
        raise HTTPException(404, "Transformation plan not found")

    df, _ = await _load_dataframe(version)
    operations = plan.operations
    if body.operation_indexes is not None:
        operations = [operations[i] for i in body.operation_indexes if 0 <= i < len(operations)]
    return {"plan_id": str(plan.id), "rows": df.head(10).to_dicts(),
            "previews": generate_transformation_preview(df, operations, preview_rows=5)}




@router.post("/{dataset_id}/transform/approve")
async def approve_plan(
    dataset_id: UUID,
    body: ExecutePlanRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Explicitly approve a generated plan before execution."""
    _, version, org = await _dataset(dataset_id, current_user, db)
    await require_org_role(current_user, db, {"owner", "admin", "editor"})
    plan = (await db.execute(select(TransformationPlan).where(
        TransformationPlan.id == body.plan_id,
        TransformationPlan.dataset_version_id == version.id,
        TransformationPlan.organization_id == org,
    ))).scalar_one_or_none()
    if not plan:
        raise HTTPException(404, "Transformation plan not found")
    if plan.status == "executed":
        raise HTTPException(409, "Transformation plan has already been executed")
    plan.status = "approved"
    plan.approved_by = current_user.id
    plan.approved_at = datetime.now(timezone.utc)
    await db.commit()
    return {"plan_id": str(plan.id), "status": plan.status, "approved_at": plan.approved_at.isoformat()}

@router.post("/{dataset_id}/transform/execute", status_code=201)
async def execute_plan(
    dataset_id: UUID,
    body: ExecutePlanRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    ds, source_version, org = await _dataset(dataset_id, current_user, db)
    await require_org_role(current_user, db, {"owner", "admin", "editor"})
    plan = (await db.execute(select(TransformationPlan).where(
        TransformationPlan.id == body.plan_id,
        TransformationPlan.dataset_version_id == source_version.id,
        TransformationPlan.organization_id == org,
    ))).scalar_one_or_none()
    if not plan:
        raise HTTPException(404, "Transformation plan not found")

    if plan.status != "approved":
        raise HTTPException(409, "Transformation plan is not executable in its current state")

    if plan.status == "executed":
        raise HTTPException(409, "Transformation plan has already been executed")

    df, _ = await _load_dataframe(source_version)
    operations = plan.operations
    if body.operation_indexes is not None:
        operations = [operations[i] for i in body.operation_indexes if 0 <= i < len(operations)]
    if not operations:
        raise HTTPException(400, "No transformation operations selected")

    run = TransformationRun(
        transformation_plan_id=plan.id,
        dataset_version_id=source_version.id,
        organization_id=org,
        executed_by=current_user.id,
        status="running",
        operations_total=len(operations),
        quality_before=source_version.quality_score,
    )
    db.add(run)
    await db.flush()

    result = TransformationEngine(df).execute_operations(operations)
    output_df: pl.DataFrame = result["df"]

    # Write a new immutable version; never overwrite the raw/source version.
    next_version = source_version.version_number + 1
    artifact_root = f"orgs/{org}/projects/{ds.project_id}/datasets/{ds.id}/v{next_version}"
    metadata = {"org_id": str(org), "dataset_id": str(ds.id), "parent_version": str(source_version.version_number), "transformation_run": str(run.id)}

    def make_csv():
        buf = io.BytesIO(); output_df.write_csv(buf); return buf.getvalue()
    def make_json():
        return output_df.write_json().encode("utf-8")
    def make_parquet():
        buf = io.BytesIO(); output_df.write_parquet(buf); return buf.getvalue()
    def make_xlsx():
        import pandas as pd
        buf = io.BytesIO(); output_df.to_pandas().to_excel(buf, index=False, engine="openpyxl"); return buf.getvalue()

    schema_payload = {
        "version": next_version,
        "row_count": output_df.height,
        "column_count": output_df.width,
        "columns": [{"name": n, "dtype": str(d), "nullable": bool(output_df[n].null_count() > 0)} for n, d in output_df.schema.items()],
    }
    artifact_builders = {
        "csv": (make_csv, "text/csv"),
        "json": (make_json, "application/json"),
        "parquet": (make_parquet, "application/octet-stream"),
        "xlsx": (make_xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        "schema.json": (lambda: json.dumps(schema_payload, indent=2).encode("utf-8"), "application/json"),
    }
    artifacts = {}
    for ext, (builder, content_type) in artifact_builders.items():
        filename = f"{ds.name}_v{next_version}.{ext}"
        key = f"{artifact_root}/{filename}"
        artifact_data = builder()
        await get_storage().upload_file(key, artifact_data, content_type, metadata)
        artifacts[ext] = {"filename": filename, "storage_key": key, "download_url": await get_storage().get_download_url(key, expires_in=900), "size_bytes": len(artifact_data)}

    output_format = source_version.file_format if source_version.file_format in {"csv", "json", "parquet"} else "xlsx"
    canonical = artifacts[output_format]
    storage_key = canonical["storage_key"]
    data = await get_storage().download_file(storage_key)
    filename = canonical["filename"]
    content_type = {"csv": "text/csv", "json": "application/json", "parquet": "application/octet-stream", "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}[output_format]

    new_version = DatasetVersion(
        data_source_id=ds.id, organization_id=org, version_number=next_version,
        version_label=f"refined-v{next_version}", description="Output from approved Rivu transformation plan",
        storage_key=storage_key, storage_bucket=get_storage().bucket, file_format=output_format,
        file_size_bytes=len(data), row_count=output_df.height, column_count=output_df.width,
        checksum=compute_checksum(data), parent_version_id=source_version.id,
        transformation_run_id=run.id, quality_score=source_version.quality_score,
        quality_delta=0,
    )
    db.add(new_version)
    await db.flush()

    # Re-profile and re-score the refined output for trustworthy version history.
    profile_data = profile_dataframe(output_df, str(org))
    new_profile = DataProfile(
        dataset_version_id=new_version.id, organization_id=org,
        row_count=profile_data["row_count"], column_count=profile_data["column_count"],
        duplicate_row_count=profile_data["duplicate_row_count"],
        duplicate_row_pct=profile_data["duplicate_row_pct"],
        total_null_count=profile_data["total_null_count"],
        total_null_pct=profile_data["total_null_pct"],
        total_cell_count=profile_data["total_cell_count"],
        has_header=True, sample_rows=profile_data["sample_rows"],
        profiling_duration_ms=profile_data["profiling_duration_ms"],
    )
    db.add(new_profile)
    await db.flush()
    for col_data in profile_data["columns"]:
        db.add(ColumnProfile(
            data_profile_id=new_profile.id, dataset_version_id=new_version.id,
            organization_id=org, column_index=col_data["column_index"],
            column_name=col_data["column_name"], inferred_type=col_data["inferred_type"],
            semantic_type=col_data["semantic_type"], null_count=col_data["null_count"],
            null_pct=col_data["null_pct"], non_null_count=col_data["non_null_count"],
            unique_count=col_data["unique_count"], uniqueness_pct=col_data["uniqueness_pct"],
            is_constant=col_data["is_constant"], is_unique=col_data["is_unique"],
            numeric_min=col_data.get("numeric_min"), numeric_max=col_data.get("numeric_max"),
            numeric_mean=col_data.get("numeric_mean"), numeric_median=col_data.get("numeric_median"),
            numeric_std_dev=col_data.get("numeric_std_dev"), numeric_q1=col_data.get("numeric_q1"),
            numeric_q3=col_data.get("numeric_q3"), numeric_skewness=col_data.get("numeric_skewness"),
            string_min_length=col_data.get("string_min_length"), string_max_length=col_data.get("string_max_length"),
            string_avg_length=col_data.get("string_avg_length"), date_min=col_data.get("date_min"),
            date_max=col_data.get("date_max"), date_formats=col_data.get("date_formats"),
            value_frequency=col_data.get("value_frequency"), sample_values=col_data.get("sample_values"),
        ))

    quality_data = calculate_quality_report(profile_data, profile_data["columns"])
    new_quality = QualityReport(
        dataset_version_id=new_version.id, organization_id=org,
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
    db.add(new_quality)
    await db.flush()
    for issue in quality_data.get("issues", []):
        db.add(QualityIssue(
            quality_report_id=new_quality.id, dataset_version_id=new_version.id,
            organization_id=org, issue_type=issue["issue_type"], severity=issue["severity"],
            title=issue["title"], description=issue.get("description"),
            affected_column=issue.get("affected_column"),
            affected_row_count=issue.get("affected_row_count"),
            affected_row_pct=issue.get("affected_row_pct"), evidence=issue.get("evidence"),
            suggested_fix=issue.get("suggested_fix"), auto_fixable=issue.get("auto_fixable", False),
        ))
    new_version.quality_score = quality_data["overall_score"]
    new_version.quality_delta = float(quality_data["overall_score"]) - float(source_version.quality_score or 0)
    run.quality_after = quality_data["overall_score"]
    run.quality_delta = new_version.quality_delta

    ds.current_version = next_version
    ds.status = "transformed"

    run.output_version_id = new_version.id
    run.status = "completed" if result["ops_failed"] == 0 else "completed_with_errors"
    run.operations_applied = result["ops_applied"]
    run.operations_skipped = result["ops_skipped"]
    run.operations_failed = result["ops_failed"]
    run.rows_modified = output_df.height
    run.execution_log = result["log"]
    run.completed_at = datetime.now(timezone.utc)
    run.duration_ms = result["duration_ms"]
    plan.status = "executed"
    plan.approved_by = current_user.id
    plan.approved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(new_version)
    return {
        "message": "Transformation executed and a new immutable dataset version was created.",
        "run": {"id": str(run.id), "status": run.status, "applied": run.operations_applied,
                "skipped": run.operations_skipped, "failed": run.operations_failed,
                "duration_ms": run.duration_ms},
        "version": {"id": str(new_version.id), "number": next_version,
                    "format": output_format, "rows": output_df.height, "columns": output_df.width},
        "artifacts": artifacts,
        "schema": schema_payload,
    }
