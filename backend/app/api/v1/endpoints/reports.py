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
from app.models.transformation import TransformationRun
from app.ai.factory import get_ai_provider
from app.ai.base import AIMessage
from app.ingestion.parser import parse_to_polars

router=APIRouter()

@router.get("/{dataset_id}/json")
async def report_json(dataset_id: UUID, current_user: User=Depends(get_current_user), db: AsyncSession=Depends(get_session)):
    org=(await db.execute(select(Membership.organization_id).where(Membership.user_id==current_user.id).limit(1))).scalar_one_or_none()
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


@router.get("/{dataset_id}/dashboard")
async def report_dashboard(dataset_id: UUID, current_user: User=Depends(get_current_user), db: AsyncSession=Depends(get_session)):
    """Return the live Power BI-style report payload plus an AI executive summary."""
    org=(await db.execute(select(Membership.organization_id).where(Membership.user_id==current_user.id).limit(1))).scalar_one_or_none()
    ds=(await db.execute(select(DataSource).where(DataSource.id==dataset_id,DataSource.organization_id==org))).scalar_one_or_none()
    if not ds: raise HTTPException(404,"Dataset not found")
    version=(await db.execute(select(DatasetVersion).where(DataSource.id==dataset_id, DatasetVersion.version_number==ds.current_version))).scalar_one_or_none()
    if not version: raise HTTPException(404,"Dataset version not found")
    profile=(await db.execute(select(DataProfile).where(DataProfile.dataset_version_id==version.id))).scalar_one_or_none()
    quality=(await db.execute(select(QualityReport).where(QualityReport.dataset_version_id==version.id))).scalar_one_or_none()
    if not profile or not quality: raise HTTPException(202,"Dataset intelligence is still processing")
    issues=(await db.execute(select(QualityIssue).where(QualityIssue.quality_report_id==quality.id))).scalars().all()
    latest_run=(await db.execute(select(TransformationRun).where(TransformationRun.output_version_id==version.id).order_by(TransformationRun.completed_at.desc()))).scalars().first()
    columns=[]
    for c in (await db.execute(select(__import__("app.models.profile",fromlist=["ColumnProfile"]).ColumnProfile).where(__import__("app.models.profile",fromlist=["ColumnProfile"]).ColumnProfile.data_profile_id==profile.id).order_by(__import__("app.models.profile",fromlist=["ColumnProfile"]).ColumnProfile.column_index))).scalars().all():
        columns.append({"name":c.column_name,"type":c.inferred_type,"semantic_type":c.semantic_type,"null_pct":float(c.null_pct or 0),"unique_pct":float(c.uniqueness_pct or 0),"samples":(c.sample_values or [])[:5]})
    sample_rows=profile.sample_rows or []
    payload={
        "dataset":{"id":str(ds.id),"name":ds.name,"source":ds.original_filename,"format":ds.file_format,"version":ds.current_version},
        "profile":{"rows":profile.row_count,"columns":profile.column_count,"duplicates":profile.duplicate_row_count,"duplicate_pct":float(profile.duplicate_row_pct or 0),"nulls":profile.total_null_count,"null_pct":float(profile.total_null_pct or 0)},
        "quality":{"overall":float(quality.overall_score),"completeness":float(quality.completeness_score or 0),"validity":float(quality.validity_score or 0),"consistency":float(quality.consistency_score or 0),"uniqueness":float(quality.uniqueness_score or 0),"integrity":float(quality.integrity_score or 0)},
        "issues":[{"severity":i.severity,"title":i.title,"column":i.affected_column,"rows":i.affected_row_count,"suggested_fix":i.suggested_fix} for i in issues[:100]],
        "columns":columns,"sample_rows":sample_rows[:25],
        "refinement":None,
    }
    if latest_run:
        payload["refinement"]={"status":latest_run.status,"applied":latest_run.operations_applied,"skipped":latest_run.operations_skipped,"failed":latest_run.operations_failed,"rows":latest_run.rows_modified,"quality_before":float(latest_run.quality_before or 0),"quality_after":float(latest_run.quality_after or 0),"quality_delta":float(latest_run.quality_delta or 0),"duration_ms":latest_run.duration_ms}
    ai_prompt = f"""Create an executive data intelligence summary for this Rivu report. Use ONLY the supplied facts. Do not invent numbers. Return JSON with keys: headline, summary, strengths (array of strings), risks (array of strings), actions (array of strings), data_readiness (number 0-100). Keep each item concise.
FACTS:
{json.dumps({"dataset":payload["dataset"],"profile":payload["profile"],"quality":payload["quality"],"issues":payload["issues"][:20],"refinement":payload["refinement"],"columns":payload["columns"][:40]},default=str)}"""
    try:
        response=await get_ai_provider().complete_json([
            AIMessage("system","You are Rivu's senior data intelligence analyst. Be precise, factual and concise."),
            AIMessage("user",ai_prompt),
        ],temperature=0.1,max_tokens=1800)
        try: ai=json.loads(response.content)
        except Exception:
            ai={"headline":"Dataset intelligence generated","summary":response.content[:1200],"strengths":[],"risks":[],"actions":[],"data_readiness":float(quality.overall_score)}
        payload["ai"]={**ai,"model":response.model,"provider":response.provider,"latency_ms":response.latency_ms}
    except Exception as exc:
        payload["ai"]={"headline":"Dataset intelligence","summary":"AI executive summary is temporarily unavailable. The measured quality report below remains authoritative.","strengths":[],"risks":[],"actions":[],"data_readiness":float(quality.overall_score),"error":str(exc)}
    return payload


@router.get("/{dataset_id}/pdf")
async def report_pdf(
    dataset_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Generate a branded, downloadable PDF data-quality report."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    from reportlab.lib.units import mm

    org = (await db.execute(
        select(Membership.organization_id).where(Membership.user_id == current_user.id).limit(1)
    )).scalar_one_or_none()
    ds = (await db.execute(
        select(DataSource).where(DataSource.id == dataset_id, DataSource.organization_id == org)
    )).scalar_one_or_none()
    if not ds:
        raise HTTPException(404, "Dataset not found")
    version = (await db.execute(
        select(DatasetVersion).where(
            DatasetVersion.data_source_id == ds.id,
            DatasetVersion.version_number == ds.current_version,
        )
    )).scalar_one_or_none()
    profile = (await db.execute(
        select(DataProfile).where(DataProfile.dataset_version_id == version.id)
    )).scalar_one_or_none() if version else None
    quality = (await db.execute(
        select(QualityReport).where(QualityReport.dataset_version_id == version.id)
    )).scalar_one_or_none() if version else None
    issues = (await db.execute(
        select(QualityIssue).where(QualityIssue.quality_report_id == quality.id)
    )).scalars().all() if quality else []
    latest_run = (await db.execute(
        select(TransformationRun).where(
            TransformationRun.output_version_id == version.id
        ).order_by(TransformationRun.completed_at.desc())
    )).scalars().first() if version else None

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=16*mm, leftMargin=16*mm, topMargin=16*mm, bottomMargin=16*mm)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("RivuTitle", parent=styles["Title"], fontSize=22, textColor=colors.HexColor("#172033"))
    body = ParagraphStyle("RivuBody", parent=styles["BodyText"], fontSize=9, leading=13)
    story = [
        Paragraph("RIVU AI", title),
        Paragraph("Data Quality & Intelligence Report", styles["Heading2"]),
        Spacer(1, 8),
        Paragraph(f"<b>Dataset:</b> {ds.name}", body),
        Paragraph(f"<b>Source:</b> {ds.original_filename}", body),
        Paragraph(f"<b>Version:</b> {ds.current_version}", body),
        Spacer(1, 10),
    ]
    if profile:
        story.append(Paragraph("Dataset profile", styles["Heading2"]))
        profile_rows = [
            ["Rows", str(profile.row_count or 0)],
            ["Columns", str(profile.column_count or 0)],
            ["Duplicate rows", str(profile.duplicate_row_count or 0)],
            ["Duplicate %", f"{float(profile.duplicate_row_pct or 0):.2f}%"],
            ["Null cells", str(profile.total_null_count or 0)],
            ["Null %", f"{float(profile.total_null_pct or 0):.2f}%"],
        ]
        table = Table(profile_rows, colWidths=[55*mm, 55*mm])
        table.setStyle(TableStyle([("GRID",(0,0),(-1,-1),0.4,colors.HexColor("#cbd5e1")),("FONTNAME",(0,0),(-1,-1),"Helvetica"),("FONTSIZE",(0,0),(-1,-1),9)]))
        story += [table, Spacer(1,10)]
    if latest_run:
        story.append(Paragraph("Refinement summary", styles["Heading2"]))
        run_rows = [
            ["Status", str(latest_run.status)],
            ["Operations applied", str(latest_run.operations_applied)],
            ["Operations skipped", str(latest_run.operations_skipped)],
            ["Operations failed", str(latest_run.operations_failed)],
            ["Rows in refined output", str(latest_run.rows_modified or 0)],
            ["Quality change", f"{float(latest_run.quality_delta or 0):+.1f} points"],
            ["Duration", f"{int(latest_run.duration_ms or 0)} ms"],
        ]
        table = Table(run_rows, colWidths=[55*mm, 55*mm])
        table.setStyle(TableStyle([("GRID",(0,0),(-1,-1),0.4,colors.HexColor("#cbd5e1")),("FONTSIZE",(0,0),(-1,-1),9)]))
        story += [table, Spacer(1,10)]

    if quality:
        story.append(Paragraph("Quality score", styles["Heading2"]))
        score_rows = [
            ["Overall", f"{float(quality.overall_score):.1f}/100"],
            ["Completeness", f"{float(quality.completeness_score or 0):.1f}"],
            ["Validity", f"{float(quality.validity_score or 0):.1f}"],
            ["Consistency", f"{float(quality.consistency_score or 0):.1f}"],
            ["Uniqueness", f"{float(quality.uniqueness_score or 0):.1f}"],
            ["Integrity", f"{float(quality.integrity_score or 0):.1f}"],
        ]
        table = Table(score_rows, colWidths=[55*mm, 55*mm])
        table.setStyle(TableStyle([("GRID",(0,0),(-1,-1),0.4,colors.HexColor("#cbd5e1")),("FONTSIZE",(0,0),(-1,-1),9)]))
        story += [table, Spacer(1,10)]
    story.append(Paragraph(f"Issues detected: {len(issues)}", styles["Heading2"]))
    issue_rows = [["Severity", "Issue", "Column"]]
    for issue in issues[:100]:
        issue_rows.append([str(issue.severity), str(issue.title), str(issue.affected_column or "—")])
    table = Table(issue_rows, colWidths=[25*mm, 95*mm, 45*mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#172033")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#cbd5e1")),
        ("FONTSIZE",(0,0),(-1,-1),7.5),
    ]))
    story.append(table)
    doc.build(story)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{ds.name}-rivu-report.pdf"'},
    )
