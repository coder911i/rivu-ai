"""Downloadable dataset reports."""
import io, json
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_session
from app.core.storage import get_storage
from app.core.security import get_current_user
from app.models.user import User
from app.models.organization import Membership
from app.models.dataset import DataSource, DatasetVersion
from app.models.profile import DataProfile, ColumnProfile
from app.models.quality import QualityReport, QualityIssue
from app.models.transformation import TransformationRun
from app.ai.factory import get_ai_provider
from app.ai.base import AIMessage
from app.ingestion.parser import parse_to_polars

router=APIRouter()
async def build_ai_report(facts: dict, fallback_score: float) -> dict:
    """Build a fact-grounded Rivu executive intelligence report."""
    prompt = """You are Rivu AI's senior data intelligence analyst.
Create a professional executive report from the supplied measured dataset facts only.
Never invent, estimate, or imply numbers that are not present. Separate measured facts from interpretation.
Return ONLY valid JSON with exactly these keys:
headline (string), executive_summary (string, 2-4 sentences), data_story (string, 2-4 sentences),
key_findings (array of 4-6 concise strings), risk_analysis (array of 3-5 concise strings),
recommended_actions (array of 4-6 concrete strings), strengths (array of 3-5 strings),
risks (array of 3-5 strings), actions (array of 3-5 strings), data_readiness (number 0-100),
confidence_note (string).
Use measured quality dimensions, issue severities, affected columns, null/duplicate rates and refinement history when available.
Do not praise the product. The report is about the dataset.
FACTS:
""" + json.dumps(facts, default=str)
    try:
        response = await get_ai_provider().complete_json([
            AIMessage("system", "You are Rivu's senior data intelligence analyst. Be rigorous, factual and decision-useful."),
            AIMessage("user", prompt),
        ], temperature=0.1, max_tokens=2800)
        try:
            ai = json.loads(response.content)
        except Exception:
            ai = {"headline":"Dataset intelligence","executive_summary":response.content[:1800],"data_story":"Measured dataset facts are shown below.","key_findings":[],"risk_analysis":[],"recommended_actions":[],"strengths":[],"risks":[],"actions":[],"data_readiness":fallback_score,"confidence_note":"Generated from measured profile and quality data."}
        return {**ai, "model":response.model, "provider":response.provider, "latency_ms":response.latency_ms}
    except Exception as exc:
        return {"headline":"Dataset intelligence","executive_summary":"The measured dataset profile and quality scores remain authoritative. AI narrative generation is temporarily unavailable.","data_story":"Use the measured quality dimensions and issue register below as the source of truth.","key_findings":[],"risk_analysis":[],"recommended_actions":[],"strengths":[],"risks":[],"actions":[],"data_readiness":fallback_score,"confidence_note":"AI narrative unavailable; measured metrics remain authoritative.","error":str(exc)[:300]}

def draw_rivu_brand(canvas, doc):
    """Draw the Rivu AI mark on every generated report page."""
    canvas.saveState()
    from reportlab.lib.units import mm
    x, y = 18*mm, 282*mm
    canvas.setFillColorRGB(0.12, 0.08, 0.16)
    canvas.rect(x, y, 7*mm, 7*mm, fill=1, stroke=0)
    canvas.setFillColorRGB(0.55, 0.34, 0.95)
    canvas.rect(x+8*mm, y, 7*mm, 7*mm, fill=1, stroke=0)
    canvas.rect(x, y-8*mm, 7*mm, 7*mm, fill=1, stroke=0)
    canvas.setFillColorRGB(0.12, 0.08, 0.16)
    canvas.rect(x+8*mm, y-8*mm, 7*mm, 7*mm, fill=1, stroke=0)
    canvas.setFillColorRGB(0.10,0.08,0.13); canvas.setFont("Helvetica-Bold",15); canvas.drawString(x+18*mm,y-2*mm,"rivu")
    canvas.setFillColorRGB(0.55,0.34,0.95); canvas.setFont("Helvetica",15); canvas.drawString(x+43*mm,y-2*mm,"ai")
    canvas.setStrokeColorRGB(0.86,0.85,0.90); canvas.line(18*mm,13*mm,192*mm,13*mm)
    canvas.setFillColorRGB(0.42,0.41,0.48); canvas.setFont("Helvetica",7); canvas.drawRightString(192*mm,8*mm,"Rivu AI · Confidential data intelligence · Page %d" % doc.page)
    canvas.restoreState()

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
    version=(await db.execute(select(DatasetVersion).where(DatasetVersion.data_source_id==ds.id, DatasetVersion.version_number==ds.current_version))).scalar_one_or_none()
    if not version: raise HTTPException(404,"Dataset version not found")
    profile=(await db.execute(select(DataProfile).where(DataProfile.dataset_version_id==version.id))).scalar_one_or_none()
    quality=(await db.execute(select(QualityReport).where(QualityReport.dataset_version_id==version.id))).scalar_one_or_none()
    if not profile or not quality: raise HTTPException(202,"Dataset intelligence is still processing")
    issues=(await db.execute(select(QualityIssue).where(QualityIssue.quality_report_id==quality.id))).scalars().all()
    latest_run=(await db.execute(select(TransformationRun).where(TransformationRun.output_version_id==version.id).order_by(TransformationRun.completed_at.desc()))).scalars().first()
    columns=[]
    for c in (await db.execute(select(ColumnProfile).where(ColumnProfile.data_profile_id==profile.id).order_by(ColumnProfile.column_index))).scalars().all():
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
    payload["artifacts"]={}
    if latest_run and version.version_number > 1:
        root=f"orgs/{org}/projects/{ds.project_id}/datasets/{ds.id}/v{version.version_number}"
        for ext in ("csv","xlsx","xls","json","parquet","schema.json"):
            key=f"{root}/{ds.name}_v{version.version_number}.{ext}"
            try:
                payload["artifacts"][ext]={"filename":key.rsplit("/",1)[-1],"download_url":await get_storage().get_download_url(key,expires_in=900)}
            except Exception:
                pass
    payload["ai"] = await build_ai_report(
        {"dataset":payload["dataset"],"profile":payload["profile"],"quality":payload["quality"],"issues":payload["issues"][:50],"refinement":payload["refinement"],"columns":payload["columns"][:60]},
        float(quality.overall_score),
    )
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

    ai_summary="Rivu measured the dataset quality and refinement history from the current version."
    refinement_summary = (
        f"applied={latest_run.operations_applied}, "
        f"quality_delta={float(latest_run.quality_delta or 0)}"
        if latest_run
        else "not available"
    )
    try:
        ai_prompt=f"""Write a concise executive summary for a data quality PDF. Use only these facts. Mention the current quality score, key risks, and refinement result if present. Do not invent facts.
Dataset: {ds.name}
Rows: {profile.row_count if profile else 0}
Columns: {profile.column_count if profile else 0}
Quality: {float(quality.overall_score) if quality else 0}
Completeness: {float(quality.completeness_score or 0) if quality else 0}
Validity: {float(quality.validity_score or 0) if quality else 0}
Consistency: {float(quality.consistency_score or 0) if quality else 0}
Uniqueness: {float(quality.uniqueness_score or 0) if quality else 0}
Issues: {len(issues)}
Refinement: {refinement_summary}"""
        ai_resp=await get_ai_provider().complete([AIMessage("system","You are Rivu's senior data analyst. Return one professional paragraph."),AIMessage("user",ai_prompt)],temperature=0.1,max_tokens=500)
        ai_summary=ai_resp.content.strip()
    except Exception:
        pass

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=16*mm, leftMargin=16*mm, topMargin=25*mm, bottomMargin=18*mm, onFirstPage=draw_rivu_brand, onLaterPages=draw_rivu_brand)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("RivuTitle", parent=styles["Title"], fontSize=22, textColor=colors.HexColor("#172033"))
    body = ParagraphStyle("RivuBody", parent=styles["BodyText"], fontSize=9, leading=13)
    ai_report = await build_ai_report(
        {"dataset":{"name":ds.name,"source":ds.original_filename,"version":ds.current_version},
         "profile":{"rows":profile.row_count if profile else 0,"columns":profile.column_count if profile else 0,"duplicates":profile.duplicate_row_count if profile else 0,"null_pct":float(profile.total_null_pct or 0) if profile else 0},
         "quality":{"overall":float(quality.overall_score) if quality else 0,"completeness":float(quality.completeness_score or 0),"validity":float(quality.validity_score or 0),"consistency":float(quality.consistency_score or 0),"uniqueness":float(quality.uniqueness_score or 0),"integrity":float(quality.integrity_score or 0)},
         "issues":[{"severity":i.severity,"title":i.title,"column":i.affected_column,"rows":i.affected_row_count} for i in issues[:50]],
         "refinement":refinement_summary},
        float(quality.overall_score) if quality else 0,
    )
    story = [
        Paragraph("RIVU AI", title),
        Paragraph("Data Quality & Intelligence Report", styles["Heading2"]),
        Spacer(1, 8),
        Paragraph(f"<b>Dataset:</b> {ds.name}", body),
        Paragraph(f"<b>Source:</b> {ds.original_filename}", body),
        Paragraph(f"<b>Version:</b> {ds.current_version}", body),
        Spacer(1, 8),
        Paragraph("<b>AI executive summary</b>", styles["Heading2"]),
        Paragraph(ai_report.get("executive_summary") or ai_summary, body),
        Spacer(1, 7),
        Paragraph("<b>Key findings</b>", styles["Heading2"]),
        *[Paragraph("• "+str(x), body) for x in (ai_report.get("key_findings") or [])[:6]],
        Paragraph("<b>Risk analysis</b>", styles["Heading2"]),
        *[Paragraph("• "+str(x), body) for x in (ai_report.get("risk_analysis") or [])[:5]],
        Paragraph("<b>Recommended actions</b>", styles["Heading2"]),
        *[Paragraph("• "+str(x), body) for x in (ai_report.get("recommended_actions") or [])[:6]],
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

    
@router.get("/{dataset_id}/executive-pdf")
async def executive_pdf(dataset_id: UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    """Generate a compact executive intelligence PDF from measured dataset facts."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    from reportlab.lib.units import mm

    org=(await db.execute(select(Membership.organization_id).where(Membership.user_id==current_user.id).limit(1))).scalar_one_or_none()
    ds=(await db.execute(select(DataSource).where(DataSource.id==dataset_id,DataSource.organization_id==org))).scalar_one_or_none()
    if not ds: raise HTTPException(404,"Dataset not found")
    version=(await db.execute(select(DatasetVersion).where(DatasetVersion.data_source_id==ds.id,DatasetVersion.version_number==ds.current_version))).scalar_one_or_none()
    if not version: raise HTTPException(404,"Dataset version not found")
    profile=(await db.execute(select(DataProfile).where(DataProfile.dataset_version_id==version.id))).scalar_one_or_none()
    quality=(await db.execute(select(QualityReport).where(QualityReport.dataset_version_id==version.id))).scalar_one_or_none()
    issues=(await db.execute(select(QualityIssue).where(QualityIssue.quality_report_id==quality.id))).scalars().all() if quality else []
    if not profile or not quality: raise HTTPException(409,"Dataset intelligence is still processing")

    top_issues=sorted(issues,key=lambda x: {"critical":0,"high":1,"medium":2,"low":3}.get(str(x.severity).lower(),4))[:8]
    buf=io.BytesIO()
    doc=SimpleDocTemplate(buf,pagesize=A4,rightMargin=18*mm,leftMargin=18*mm,topMargin=25*mm,bottomMargin=18*mm,onFirstPage=draw_rivu_brand,onLaterPages=draw_rivu_brand)
    styles=getSampleStyleSheet()
    title=ParagraphStyle("ExecTitle",parent=styles["Title"],fontSize=24,textColor=colors.HexColor("#172033"))
    body=ParagraphStyle("ExecBody",parent=styles["BodyText"],fontSize=9,leading=13)
    story=[Paragraph("RIVU AI — EXECUTIVE INTELLIGENCE",title),Spacer(1,8),
      Paragraph(f"<b>{ds.name}</b> · version {version.version_number}",styles["Heading2"]),
      Paragraph(f"Source: {ds.original_filename} · {profile.row_count:,} rows · {profile.column_count} columns",body),Spacer(1,12),
      Paragraph("Data Quality Snapshot",styles["Heading2"])]
    rows=[["Overall",f"{float(quality.overall_score):.1f}/100"],["Completeness",f"{float(quality.completeness_score or 0):.1f}"],["Validity",f"{float(quality.validity_score or 0):.1f}"],["Consistency",f"{float(quality.consistency_score or 0):.1f}"],["Uniqueness",f"{float(quality.uniqueness_score or 0):.1f}"],["Integrity",f"{float(quality.integrity_score or 0):.1f}"],["Issues",str(len(issues))]]
    t=Table(rows,colWidths=[55*mm,55*mm]);t.setStyle(TableStyle([("GRID",(0,0),(-1,-1),.35,colors.HexColor("#cbd5e1")),("FONTSIZE",(0,0),(-1,-1),9)]));story += [t,Spacer(1,12),Paragraph("Priority Risks",styles["Heading2"])]
    if top_issues:
      ir=[["Severity","Issue","Column"]]+[[str(i.severity),str(i.title),str(i.affected_column or "—")] for i in top_issues]
      it=Table(ir,colWidths=[25*mm,95*mm,45*mm],repeatRows=1);it.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#172033")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.3,colors.HexColor("#cbd5e1")),("FONTSIZE",(0,0),(-1,-1),7.5)]));story.append(it)
    story += [Spacer(1,12),Paragraph("Recommended Actions",styles["Heading2"])]
    for issue in top_issues[:5]:
      story.append(Paragraph(f"• {issue.suggested_fix or issue.title}",body))
    doc.build(story);buf.seek(0)
    return StreamingResponse(buf,media_type="application/pdf",headers={"Content-Disposition":f'attachment; filename="{ds.name}-executive-rivu-report.pdf"'})
