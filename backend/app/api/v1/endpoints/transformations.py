"""Approved transformation execution and preview endpoints."""
import io
from datetime import datetime, timezone
from uuid import UUID

import polars as pl
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import get_current_user
from app.core.storage import get_storage, build_storage_key, compute_checksum
from app.core.exceptions import http_not_found
from app.models.user import User
from app.models.organization import Membership
from app.models.dataset import DataSource, DatasetVersion
from app.models.transformation import TransformationPlan, TransformationRun
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


@router.post("/{dataset_id}/transform/execute", status_code=201)
async def execute_plan(
    dataset_id: UUID,
    body: ExecutePlanRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    ds, source_version, org = await _dataset(dataset_id, current_user, db)
    plan = (await db.execute(select(TransformationPlan).where(
        TransformationPlan.id == body.plan_id,
        TransformationPlan.dataset_version_id == source_version.id,
        TransformationPlan.organization_id == org,
    ))).scalar_one_or_none()
    if not plan:
        raise HTTPException(404, "Transformation plan not found")

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

    # Write a new immutable version; the raw/source version is never overwritten.
    out = io.BytesIO()
    output_format = source_version.file_format
    filename = f"{ds.name}_v{source_version.version_number + 1}.{output_format}"
    if output_format == "csv":
        output_df.write_csv(out)
        content_type = "text/csv"
    elif output_format == "json":
        out.write(output_df.write_json().encode("utf-8"))
        content_type = "application/json"
    elif output_format == "parquet":
        output_df.write_parquet(out)
        content_type = "application/octet-stream"
    else:
        # Excel transformations are exported as CSV to keep the pipeline deterministic.
        output_format = "csv"
        filename = f"{ds.name}_v{source_version.version_number + 1}.csv"
        output_df.write_csv(out)
        content_type = "text/csv"

    data = out.getvalue()
    next_version = source_version.version_number + 1
    storage_key = build_storage_key(str(org), str(ds.project_id), str(ds.id), next_version, filename)
    await get_storage().upload_file(storage_key, data, content_type, {
        "org_id": str(org), "dataset_id": str(ds.id),
        "parent_version": str(source_version.version_number), "transformation_run": str(run.id),
    })

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
    }
