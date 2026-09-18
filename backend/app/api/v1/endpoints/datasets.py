"""
Datasets endpoints: upload, list, get, profile, analyze, version management.
"""

import io
import uuid
import re
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import polars as pl
import structlog

from app.core.database import get_session
from app.core.security import get_current_user
from app.core.storage import get_storage, compute_checksum, build_storage_key
from app.core.exceptions import ValidationError, http_not_found
from app.models.user import User
from app.models.organization import Membership
from app.models.project import Project
from app.models.dataset import DataSource, DatasetVersion
from app.models.quality import Job
from app.ingestion.parser import validate_upload, parse_to_polars
from app.workers.processor import process_dataset_async

router = APIRouter()
logger = structlog.get_logger(__name__)


async def _get_user_org(user: User, db: AsyncSession) -> UUID:
    result = await db.execute(
        select(Membership).where(Membership.user_id == user.id).limit(1)
    )
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=403, detail={"message": "No organization found"})
    return m.organization_id


@router.post("/projects/{project_id}/upload", status_code=202)
async def upload_dataset(
    project_id: UUID,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Upload a dataset file and start processing pipeline."""
    org_id = await _get_user_org(current_user, db)

    # Verify project belongs to org
    project_result = await db.execute(
        select(Project).where(Project.id == project_id, Project.organization_id == org_id)
    )
    if not project_result.scalar_one_or_none():
        raise http_not_found("Project", str(project_id))

    # Validate metadata
    filename = file.filename or "upload"
    content_type = file.content_type or "application/octet-stream"

    # Read with a hard upper bound so an oversized multipart body cannot consume
    # unbounded application memory before validation.
    max_bytes = 500 * 1024 * 1024
    chunks = []
    total = 0
    while True:
        chunk = await file.read(min(1024 * 1024, max_bytes - total + 1))
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail={"message": "File exceeds the 500MB upload limit", "type": "file_too_large"},
            )
        chunks.append(chunk)
    raw_bytes = b"".join(chunks)
    size = len(raw_bytes)

    try:
        file_format = validate_upload(filename, size, content_type)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail={"message": e.message, "type": "validation_error"})

    # Keep client-controlled filenames safe and portable in object-storage keys.
    safe_filename = re.sub(r"[^A-Za-z0-9._-]", "_", filename).strip("._")[:200] or "upload"
    dataset_name = (name or filename.rsplit(".", 1)[0]).strip()[:300] or "Dataset"
    checksum = compute_checksum(raw_bytes)

    # Create DataSource record
    data_source = DataSource(
        organization_id=org_id,
        project_id=project_id,
        created_by=current_user.id,
        name=dataset_name,
        description=description,
        original_filename=filename,
        file_format=file_format,
        status="uploading",
        current_version=1,
    )
    db.add(data_source)
    await db.flush()

    # Build storage key for v1 (raw)
    storage_key = build_storage_key(
        str(org_id), str(project_id), str(data_source.id), 1, safe_filename
    )
    storage_bucket = get_storage().bucket

    # Upload to object storage
    try:
        storage = get_storage()
        await storage.upload_file(
            key=storage_key,
            data=raw_bytes,
            content_type=content_type,
            metadata={
                "org_id": str(org_id),
                "project_id": str(project_id),
                "dataset_id": str(data_source.id),
                "original_filename": safe_filename,
                "format": file_format,
            },
        )
    except Exception as e:
        logger.error("storage_upload_failed", error=str(e))
        raise HTTPException(status_code=500, detail={"message": "Storage upload failed", "type": "storage_error"})

    # Create version 1 record
    version = DatasetVersion(
        data_source_id=data_source.id,
        organization_id=org_id,
        version_number=1,
        version_label="raw",
        description="Original uploaded file",
        storage_key=storage_key,
        storage_bucket=storage_bucket,
        file_format=file_format,
        file_size_bytes=size,
        checksum=checksum,
    )
    db.add(version)
    await db.flush()

    # Create profiling job
    job = Job(
        organization_id=org_id,
        created_by=current_user.id,
        job_type="profile",
        status="queued",
        data_source_id=data_source.id,
        dataset_version_id=version.id,
        priority=5,
    )
    db.add(job)
    data_source.status = "uploaded"
    await db.commit()

    await db.refresh(job)
    await db.refresh(data_source)
    await db.refresh(version)

    # Launch background processing
    background_tasks.add_task(
        process_dataset_async,
        job_id=str(job.id),
        version_id=str(version.id),
        data_source_id=str(data_source.id),
        org_id=str(org_id),
        raw_bytes=raw_bytes,
        file_format=file_format,
    )

    logger.info("dataset_uploaded", dataset_id=str(data_source.id), job_id=str(job.id))

    return {
        "message": "Dataset uploaded successfully. Processing started.",
        "dataset": {
            "id": str(data_source.id),
            "name": data_source.name,
            "filename": filename,
            "format": file_format,
            "size_bytes": size,
            "status": data_source.status,
        },
        "version": {
            "id": str(version.id),
            "version_number": 1,
            "version_label": "raw",
        },
        "job": {
            "id": str(job.id),
            "status": job.status,
            "type": job.job_type,
        },
    }


@router.get("/{dataset_id}")
async def get_dataset(
    dataset_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    org_id = await _get_user_org(current_user, db)
    ds = await _get_dataset_or_404(dataset_id, org_id, db)
    return _format_datasource(ds)


@router.get("/{dataset_id}/versions")
async def get_versions(
    dataset_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    org_id = await _get_user_org(current_user, db)
    ds = await _get_dataset_or_404(dataset_id, org_id, db)

    result = await db.execute(
        select(DatasetVersion)
        .where(DatasetVersion.data_source_id == dataset_id)
        .order_by(DatasetVersion.version_number)
    )
    versions = result.scalars().all()

    return {
        "dataset_id": str(dataset_id),
        "versions": [_format_version(v) for v in versions],
    }


@router.get("/{dataset_id}/export/{version_number}")
async def export_dataset(
    dataset_id: UUID,
    version_number: int,
    format: str = "csv",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Get a presigned download URL for a dataset version."""
    org_id = await _get_user_org(current_user, db)
    ds = await _get_dataset_or_404(dataset_id, org_id, db)

    result = await db.execute(
        select(DatasetVersion).where(
            DatasetVersion.data_source_id == dataset_id,
            DatasetVersion.version_number == version_number,
        )
    )
    version = result.scalar_one_or_none()
    if not version:
        raise http_not_found("Dataset version", str(version_number))

    storage = get_storage()
    try:
        url = await storage.get_download_url(version.storage_key, expires_in=3600)
    except Exception as e:
        raise HTTPException(status_code=500, detail={"message": f"Could not generate download URL: {e}"})

    return {
        "download_url": url,
        "expires_in": 3600,
        "version": version_number,
        "format": version.file_format,
        "filename": f"{ds.name}_v{version_number}.{version.file_format}",
    }


async def _get_dataset_or_404(dataset_id: UUID, org_id: UUID, db: AsyncSession) -> DataSource:
    result = await db.execute(
        select(DataSource).where(
            DataSource.id == dataset_id, DataSource.organization_id == org_id
        )
    )
    ds = result.scalar_one_or_none()
    if not ds:
        raise http_not_found("Dataset", str(dataset_id))
    return ds


def _format_datasource(ds: DataSource) -> dict:
    return {
        "id": str(ds.id),
        "project_id": str(ds.project_id),
        "name": ds.name,
        "description": ds.description,
        "original_filename": ds.original_filename,
        "file_format": ds.file_format,
        "status": ds.status,
        "current_version": ds.current_version,
        "created_at": ds.created_at.isoformat(),
        "updated_at": ds.updated_at.isoformat(),
    }


def _format_version(v: DatasetVersion) -> dict:
    return {
        "id": str(v.id),
        "version_number": v.version_number,
        "version_label": v.version_label,
        "file_format": v.file_format,
        "file_size_bytes": v.file_size_bytes,
        "row_count": v.row_count,
        "column_count": v.column_count,
        "quality_score": float(v.quality_score) if v.quality_score else None,
        "quality_delta": float(v.quality_delta) if v.quality_delta else None,
        "created_at": v.created_at.isoformat(),
    }
