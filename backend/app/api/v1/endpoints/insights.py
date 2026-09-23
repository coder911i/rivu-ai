"""Dataset intelligence endpoints: profile, quality, jobs and AI plans."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import get_current_user
from app.models.user import User
from app.models.organization import Membership
from app.models.dataset import DataSource, DatasetVersion
from app.models.profile import DataProfile, ColumnProfile
from app.models.quality import QualityReport, QualityIssue, Job
from app.models.transformation import TransformationPlan
from app.ai.factory import get_ai_provider
from app.ai.planner import generate_transformation_plan
from app.core.storage import get_storage
from app.ingestion.parser import parse_to_polars
import polars as pl

router = APIRouter()

async def org_id_for(user: User, db: AsyncSession) -> UUID:
    result = await db.execute(select(Membership.organization_id).where(
        Membership.user_id == user.id
    ).limit(1))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(403, "No organization found")
    return org

async def dataset_for(dataset_id: UUID, user: User, db: AsyncSession):
    org = await org_id_for(user, db)
    result = await db.execute(select(DataSource).where(
        DataSource.id == dataset_id, DataSource.organization_id == org
    ))
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(404, "Dataset not found")
    return ds, org

@router.get("/{dataset_id}/profile")
async def profile(dataset_id: UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    ds, org = await dataset_for(dataset_id, current_user, db)
    version = (await db.execute(select(DatasetVersion).where(
        DatasetVersion.data_source_id == ds.id,
        DatasetVersion.version_number == ds.current_version
    ))).scalar_one_or_none()
    if not version:
        raise HTTPException(404, "Dataset version not found")
    p = (await db.execute(select(DataProfile).where(DataProfile.dataset_version_id == version.id))).scalar_one_or_none()
    if not p:
        raise HTTPException(202, "Dataset is still processing")
    cols = (await db.execute(select(ColumnProfile).where(ColumnProfile.data_profile_id == p.id).order_by(ColumnProfile.column_index))).scalars().all()
    return {
        "dataset": {"id": str(ds.id), "name": ds.name, "status": ds.status},
        "version": {"id": str(version.id), "number": version.version_number, "quality_score": float(version.quality_score) if version.quality_score is not None else None},
        "profile": {
            "id": str(p.id), "row_count": p.row_count, "column_count": p.column_count,
            "duplicate_row_count": p.duplicate_row_count, "duplicate_row_pct": float(p.duplicate_row_pct or 0),
            "total_null_count": p.total_null_count, "total_null_pct": float(p.total_null_pct or 0),
            "sample_rows": p.sample_rows or [],
        },
        "columns": [{
            "name": c.column_name, "type": c.inferred_type, "semantic_type": c.semantic_type,
            "null_count": c.null_count, "null_pct": float(c.null_pct or 0),
            "unique_count": c.unique_count, "uniqueness_pct": float(c.uniqueness_pct or 0),
            "sample_values": c.sample_values or [],
        } for c in cols],
    }

@router.get("/{dataset_id}/quality")
async def quality(dataset_id: UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    ds, _ = await dataset_for(dataset_id, current_user, db)
    version = (await db.execute(select(DatasetVersion).where(
        DatasetVersion.data_source_id == ds.id, DatasetVersion.version_number == ds.current_version
    ))).scalar_one_or_none()
    if not version:
        raise HTTPException(404, "Dataset version not found")
    report = (await db.execute(select(QualityReport).where(QualityReport.dataset_version_id == version.id))).scalar_one_or_none()
    if not report:
        raise HTTPException(202, "Quality report is still processing")
    issues = (await db.execute(select(QualityIssue).where(QualityIssue.quality_report_id == report.id).order_by(QualityIssue.severity, QualityIssue.created_at))).scalars().all()
    return {
        "id": str(report.id), "overall_score": float(report.overall_score),
        "scores": {
            "completeness": float(report.completeness_score or 0),
            "validity": float(report.validity_score or 0),
            "consistency": float(report.consistency_score or 0),
            "uniqueness": float(report.uniqueness_score or 0),
            "integrity": float(report.integrity_score or 0),
        },
        "counts": {"total": report.total_issues, "critical": report.critical_issues, "high": report.high_issues, "medium": report.medium_issues, "low": report.low_issues},
        "issues": [{
            "id": str(i.id), "type": i.issue_type, "severity": i.severity, "title": i.title,
            "description": i.description, "column": i.affected_column,
            "rows": i.affected_row_count, "pct": float(i.affected_row_pct or 0),
            "suggested_fix": i.suggested_fix, "auto_fixable": i.auto_fixable,
        } for i in issues],
    }

@router.get("/{dataset_id}/jobs")
async def jobs(dataset_id: UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    ds, _ = await dataset_for(dataset_id, current_user, db)
    rows = (await db.execute(select(Job).where(Job.data_source_id == ds.id).order_by(Job.queued_at.desc()))).scalars().all()
    return {"jobs": [{
        "id": str(j.id), "type": j.job_type, "status": j.status, "progress": j.progress_pct or 0,
        "message": j.progress_message, "error": j.error_message,
        "result": j.result, "queued_at": j.queued_at.isoformat() if j.queued_at else None,
        "completed_at": j.completed_at.isoformat() if j.completed_at else None,
    } for j in rows]}

@router.post("/{dataset_id}/ai-plan")
async def ai_plan(dataset_id: UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    ds, org = await dataset_for(dataset_id, current_user, db)
    version = (await db.execute(select(DatasetVersion).where(
        DatasetVersion.data_source_id == ds.id, DatasetVersion.version_number == ds.current_version
    ))).scalar_one_or_none()
    if not version:
        raise HTTPException(404, "Dataset version not found")
    p = (await db.execute(select(DataProfile).where(DataProfile.dataset_version_id == version.id))).scalar_one_or_none()
    q = (await db.execute(select(QualityReport).where(QualityReport.dataset_version_id == version.id))).scalar_one_or_none()
    if not p or not q:
        raise HTTPException(409, "Profile and quality report must finish first")
    cols = (await db.execute(select(ColumnProfile).where(ColumnProfile.data_profile_id == p.id).order_by(ColumnProfile.column_index))).scalars().all()
    issues = (await db.execute(select(QualityIssue).where(QualityIssue.quality_report_id == q.id))).scalars().all()
    try:
        plan = await generate_transformation_plan(
        get_ai_provider(),
        {"row_count": p.row_count, "column_count": p.column_count, "duplicate_row_count": p.duplicate_row_count, "duplicate_row_pct": float(p.duplicate_row_pct or 0), "total_null_pct": float(p.total_null_pct or 0), "filename": ds.original_filename, "file_format": ds.file_format},
        {"overall_score": float(q.overall_score), "completeness_score": float(q.completeness_score or 0), "validity_score": float(q.validity_score or 0), "consistency_score": float(q.consistency_score or 0), "uniqueness_score": float(q.uniqueness_score or 0), "issues": [{"issue_type": i.issue_type, "severity": i.severity, "affected_column": i.affected_column, "title": i.title} for i in issues]},
        [{"column_name": c.column_name, "semantic_type": c.semantic_type, "null_pct": float(c.null_pct or 0), "uniqueness_pct": float(c.uniqueness_pct or 0), "is_constant": c.is_constant, "sample_values": c.sample_values or [], "date_formats": c.date_formats or []} for c in cols],
    )
    except Exception as exc:
        raise HTTPException(502, detail={"message": "The AI refinement service could not generate a plan.", "type": "ai_provider_error", "cause": str(exc)[:300]})
    record = TransformationPlan(
        dataset_version_id=version.id, organization_id=org, created_by=current_user.id,
        status="planned", operations=plan.get("operations", []),
        total_operations=len(plan.get("operations", [])),
        estimated_quality_gain=plan.get("estimated_quality_gain"),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return {"id": str(record.id), **plan, "status": record.status}


@router.get("/{dataset_id}/preview")
async def preview_rows(
    dataset_id: UUID,
    offset: int = Query(0, ge=0, le=1_000_000),
    limit: int = Query(50, ge=1, le=100),
    search: str = Query("", max_length=200),
    sort: str = Query("", max_length=300),
    desc: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Return a bounded, real-data table preview for the current dataset version."""
    ds, _ = await dataset_for(dataset_id, current_user, db)
    version = (await db.execute(select(DatasetVersion).where(
        DatasetVersion.data_source_id == ds.id,
        DatasetVersion.version_number == ds.current_version,
    ))).scalar_one_or_none()
    if not version:
        raise HTTPException(404, "Dataset version not found")
    try:
        raw = await get_storage().download_file(version.storage_key)
        frame, _ = parse_to_polars(raw, version.file_format, ds.original_filename)
    except Exception as exc:
        raise HTTPException(502, detail={"message": "Dataset preview could not be loaded.", "type": "preview_error", "cause": str(exc)[:300]})
    if search.strip():
        needle = search.strip().lower()
        expressions = [
            pl.col(name).cast(pl.String).str.to_lowercase().str.contains(needle, literal=True)
            for name in frame.columns
        ]
        if expressions:
            frame = frame.filter(pl.any_horizontal(expressions))
    if sort and sort in frame.columns:
        frame = frame.sort(sort, descending=desc, nulls_last=True)
    total = frame.height
    return {
        "dataset_id": str(dataset_id),
        "version": version.version_number,
        "offset": offset,
        "limit": limit,
        "total": total,
        "columns": frame.columns,
        "rows": frame.slice(offset, limit).to_dicts(),
    }
