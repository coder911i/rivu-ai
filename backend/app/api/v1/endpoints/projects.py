"""Projects CRUD endpoints."""

from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import structlog

from app.core.database import get_session
from app.core.security import get_current_user, require_org_role
from app.models.user import User
from app.models.organization import Membership
from app.models.project import Project
from app.models.dataset import DataSource
from app.schemas.datasets import ProjectCreate, ProjectResponse

router = APIRouter()
logger = structlog.get_logger(__name__)


async def _get_user_org(user: User, db: AsyncSession) -> UUID:
    """Get the primary organization for the current user."""
    result = await db.execute(
        select(Membership).where(Membership.user_id == user.id).limit(1)
    )
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=403, detail={"message": "No organization found", "type": "forbidden"})
    return m.organization_id


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    membership = await require_org_role(current_user, db, {"owner", "admin", "editor"})
    org_id = membership.organization_id

    project = Project(
        organization_id=org_id,
        created_by=current_user.id,
        name=body.name,
        description=body.description,
        color=body.color,
        tags=body.tags,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    logger.info("project_created", project_id=str(project.id), name=project.name)
    return _format_project(project, 0)


@router.get("/")
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    org_id = await _get_user_org(current_user, db)

    result = await db.execute(
        select(Project)
        .where(Project.organization_id == org_id, Project.archived_at.is_(None))
        .order_by(Project.created_at.desc())
    )
    projects = result.scalars().all()

    # Get dataset counts
    formatted = []
    for p in projects:
        count_result = await db.execute(
            select(func.count()).select_from(DataSource).where(DataSource.project_id == p.id)
        )
        dataset_count = count_result.scalar() or 0
        formatted.append(_format_project(p, dataset_count))

    return {"projects": formatted, "total": len(formatted)}


@router.get("/{project_id}")
async def get_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    org_id = await _get_user_org(current_user, db)
    project = await _get_project_or_404(project_id, org_id, db)

    count_result = await db.execute(
        select(func.count()).select_from(DataSource).where(DataSource.project_id == project.id)
    )
    dataset_count = count_result.scalar() or 0

    # Get datasets
    datasets_result = await db.execute(
        select(DataSource)
        .where(DataSource.project_id == project.id)
        .order_by(DataSource.created_at.desc())
    )
    datasets = datasets_result.scalars().all()

    return {
        **_format_project(project, dataset_count),
        "datasets": [_format_datasource(ds) for ds in datasets],
    }


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    membership = await require_org_role(current_user, db, {"owner", "admin"})
    org_id = membership.organization_id
    project = await _get_project_or_404(project_id, org_id, db)
    await db.delete(project)
    await db.commit()


async def _get_project_or_404(project_id: UUID, org_id: UUID, db: AsyncSession) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.organization_id == org_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail={"message": "Project not found", "type": "not_found"})
    return project


def _format_project(p: Project, dataset_count: int) -> dict:
    return {
        "id": str(p.id),
        "organization_id": str(p.organization_id),
        "name": p.name,
        "description": p.description,
        "color": p.color,
        "tags": p.tags or [],
        "created_at": p.created_at.isoformat(),
        "updated_at": p.updated_at.isoformat(),
        "dataset_count": dataset_count,
    }


def _format_datasource(ds: DataSource) -> dict:
    return {
        "id": str(ds.id),
        "name": ds.name,
        "original_filename": ds.original_filename,
        "file_format": ds.file_format,
        "status": ds.status,
        "current_version": ds.current_version,
        "created_at": ds.created_at.isoformat(),
    }
