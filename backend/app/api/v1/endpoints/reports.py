"""Downloadable dataset reports."""
import io, json
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_session
from app.core.security import get_current_user
from app.models.user import User
from app.models.organization import Membership
from app.models.dataset import DataSource, DatasetVersion
from app.models.profile import DataProfile
from app.models.quality import QualityReport, QualityIssue

router=APIRouter()

@router.get("/{dataset_id}/json")
async def report_json(dataset_id: UUID, current_user: User=Depends(get_current_user), db: AsyncSession=Depends(get_session)):
    org=(await db.execute(select(Membership.organization_id).where(Membership.user_id==current_user.id,Membership.role=="owner").limit(1))).scalar_one_or_none()
    ds=(await db.execute(select(DataSource).where(DataSource.id==dataset_id,DataSource.organization_id==org))).scalar_one_or_none()
    if not ds: raise HTTPException(404,"Dataset not found")
    version=(await db.execute(select(DatasetVersion).where(DatasetVersion.data_source_id==ds.id,DatasetVersion.version_number==ds.current_version))).scalar_one_or_none()
    profile=(await db.execute(select(DataProfile).where(DataProfile.dataset_version_id==version.id))).scalar_one_or_none() if version else None
    quality=(await db.execute(select(QualityReport).where(QualityReport.dataset_version_id==version.id))).scalar_one_or_none() if version else None
    issues=(await db.execute(select(QualityIssue).where(QualityIssue.quality_report_id==quality.id))).scalars().all() if quality else []
    payload={"product":"Rivu AI","dataset":{"id":str(ds.id),"name":ds.name,"filename":ds.original_filename,"format":ds.file_format,"version":ds.current_version},"profile":None,"quality":None,"issues":[]}
    if profile: payload["profile"]={"rows":profile.row_count,"columns":profile.column_count,"duplicates":profile.duplicate_row_count,"duplicate_pct":float(profile.duplicate_row_pct or 0),"nulls":profile.total_null_count,"null_pct":float(profile.total_null_pct or 0)}
    if quality: payload["quality"]={"overall":float(quality.overall_score),"completeness":float(quality.completeness_score or 0),"validity":float(quality.validity_score or 0),"consistency":float(quality.consistency_score or 0),"uniqueness":float(quality.uniqueness_score or 0),"integrity":float(quality.integrity_score or 0)}
    payload["issues"]=[{"type":i.issue_type,"severity":i.severity,"title":i.title,"column":i.affected_column,"rows":i.affected_row_count,"suggested_fix":i.suggested_fix} for i in issues]
    raw=json.dumps(payload,indent=2).encode()
    return StreamingResponse(io.BytesIO(raw),media_type="application/json",headers={"Content-Disposition":f'attachment; filename="{ds.name}-rivu-report.json"'})
