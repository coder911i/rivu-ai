"""API Router for Catalogue-to-Product Data Entry solution."""

import uuid
from typing import List, Optional
from urllib.parse import quote

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalogue.ai_enrich import enrich_products_ai
from app.catalogue.auth import get_current_catalogue_user, require_catalogue_role
from app.catalogue.auth_db import get_catalogue_session
from app.catalogue.auth_models import CatalogueAccount, CatalogueSessionData, CatalogueSavedTemplate
from app.catalogue.auth_router import router as catalogue_auth_router
from app.catalogue.exporter import export_catalogue, generate_export_preview
from app.catalogue.mapping import apply_field_mappings, infer_field_mappings
from app.catalogue.models import (
    AIEnrichmentRequest,
    AIEnrichmentResponse,
    ApplyMappingRequest,
    ApplyMappingResponse,
    ExportPreviewResponse,
    ExportRequest,
    IngestionUploadResponse,
    ProductRecord,
    ProductTemplate,
    ValidateProductsRequest,
)
from app.catalogue.parser import detect_catalogue_format, parse_catalogue_file
from app.catalogue.templates import (
    delete_custom_template,
    get_all_templates,
    get_template_by_id,
    save_custom_template,
)
from app.catalogue.validator import validate_product_records
from app.core.config import settings
from app.core.exceptions import ValidationError
from sqlalchemy import delete, select

router = APIRouter()
router.include_router(catalogue_auth_router, prefix="/auth", tags=["Catalogue Authentication"])
logger = structlog.get_logger(__name__)


async def _owned_catalogue_session(db: AsyncSession, catalogue_id: str, workspace_id) -> CatalogueSessionData:
    record = (await db.execute(select(CatalogueSessionData).where(
        CatalogueSessionData.id == catalogue_id,
        CatalogueSessionData.workspace_id == workspace_id,
    ))).scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail={"message": "Catalogue session not found in this workspace", "type": "not_found"})
    return record


async def _get_template(db: AsyncSession, template_id: str, workspace_id):
    built_in = get_template_by_id(template_id)
    if built_in:
        return built_in
    saved = (await db.execute(select(CatalogueSavedTemplate).where(
        CatalogueSavedTemplate.workspace_id == workspace_id,
        CatalogueSavedTemplate.template_id == template_id,
    ))).scalar_one_or_none()
    return ProductTemplate.model_validate(saved.payload) if saved else None


@router.post("/upload", response_model=IngestionUploadResponse, status_code=status.HTTP_200_OK)
async def upload_catalogue(
    file: UploadFile = File(...),
    sheet_name: Optional[str] = Form(None),
    current_user: CatalogueAccount = Depends(get_current_catalogue_user),
    db: AsyncSession = Depends(get_catalogue_session),
):
    """Upload and inspect a supplier catalogue file (.pdf, .xlsx, .xls, .csv, .json)."""
    membership = await require_catalogue_role(current_user, db, {"owner", "admin", "editor"})
    org_id = str(membership.organization_id)

    filename = file.filename or "catalogue"
    content_type = file.content_type or "application/octet-stream"

    # Enforce file format support
    try:
        fmt = detect_catalogue_format(filename, content_type)
    except ValidationError as err:
        raise HTTPException(status_code=400, detail={"message": err.message, "type": "unsupported_format"})

    # Read bytes with memory safeguard
    data = bytearray()
    while chunk := await file.read(1024 * 1024):
        data.extend(chunk)
        if len(data) > settings.MAX_UPLOAD_SIZE_BYTES:
            await file.close()
            raise HTTPException(
                status_code=413,
                detail={"message": f"File exceeds the maximum limit of {settings.MAX_UPLOAD_SIZE_MB}MB", "type": "file_too_large"},
            )
    data = bytes(data)
    if len(data) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail={"message": f"File exceeds the maximum limit of {settings.MAX_UPLOAD_SIZE_MB}MB", "type": "file_too_large"},
        )
    if len(data) == 0:
        raise HTTPException(
            status_code=400,
            detail={"message": "Uploaded file is empty (0 bytes)", "type": "empty_file"},
        )

    try:
        parsed = parse_catalogue_file(data, filename, sheet_name=sheet_name)
    except ValidationError as err:
        raise HTTPException(status_code=400, detail={"message": err.message, "type": "parsing_error"})
    except Exception as exc:
        logger.error("catalogue_parse_failed", filename=filename, error=str(exc))
        raise HTTPException(status_code=500, detail={"message": "Failed to parse catalogue file. Check that the file is valid and try again.", "type": "internal_error"})

    catalogue_id = f"cat_{uuid.uuid4().hex[:12]}"
    columns = parsed["columns"]
    sample_records = parsed["sample_records"]

    # Compute intelligent field mapping suggestions
    suggested_mappings = infer_field_mappings(columns, sample_records)
    custom = await db.execute(select(CatalogueSavedTemplate).where(CatalogueSavedTemplate.workspace_id == membership.organization_id))
    available_templates = get_all_templates() + [ProductTemplate.model_validate(item.payload) for item in custom.scalars().all()]
    db.add(CatalogueSessionData(
        id=catalogue_id,
        workspace_id=membership.organization_id,
        original_filename=filename[:500],
        file_format=parsed["file_format"],
        row_count=parsed["row_count"],
        raw_records=parsed["raw_records"],
    ))

    logger.info(
        "catalogue_uploaded",
        catalogue_id=catalogue_id,
        filename=filename,
        format=fmt,
        rows=parsed["row_count"],
        cols=parsed["column_count"],
    )

    return IngestionUploadResponse(
        catalogue_id=catalogue_id,
        original_filename=filename,
        file_format=parsed["file_format"],
        file_size_bytes=len(data),
        row_count=parsed["row_count"],
        column_count=parsed["column_count"],
        columns=columns,
        sheet_names=parsed.get("sheet_names", []),
        selected_sheet=parsed.get("selected_sheet"),
        total_pages=parsed.get("total_pages"),
        sample_records=sample_records,
        raw_records=parsed["raw_records"],
        suggested_mappings=suggested_mappings,
        available_templates=available_templates,
    )


@router.post("/map", response_model=ApplyMappingResponse, status_code=status.HTTP_200_OK)
async def map_catalogue_records(
    body: ApplyMappingRequest,
    current_user: CatalogueAccount = Depends(get_current_catalogue_user),
    db: AsyncSession = Depends(get_catalogue_session),
):
    """Apply field mappings and deterministic normalization rules to raw records."""
    membership = await require_catalogue_role(current_user, db, {"owner", "admin", "editor"})
    org_id = str(membership.organization_id)

    record = await _owned_catalogue_session(db, body.catalogue_id, membership.organization_id) if body.catalogue_id else None
    template = await _get_template(db, body.template_id or "standard_ecommerce", membership.organization_id)
    products = apply_field_mappings(record.raw_records if record else body.raw_records, body.mappings)
    validated_products, summary = validate_product_records(products, template)
    if record:
        record.mappings = [mapping.model_dump(mode="json") for mapping in body.mappings]
        record.products = [product.model_dump(mode="json") for product in validated_products]
        record.template_id = body.template_id or "standard_ecommerce"

    return ApplyMappingResponse(
        products=validated_products,
        validation_summary=summary,
    )


@router.post("/validate", response_model=ApplyMappingResponse, status_code=status.HTTP_200_OK)
async def validate_catalogue_products(
    body: ValidateProductsRequest,
    current_user: CatalogueAccount = Depends(get_current_catalogue_user),
    db: AsyncSession = Depends(get_catalogue_session),
):
    """Re-validate products after manual edits or template changes."""
    membership = await require_catalogue_role(current_user, db, {"owner", "admin", "editor"})
    org_id = str(membership.organization_id)

    template = await _get_template(db, body.template_id or "standard_ecommerce", membership.organization_id)
    validated_products, summary = validate_product_records(body.products, template)
    if body.catalogue_id:
        record = await _owned_catalogue_session(db, body.catalogue_id, membership.organization_id)
        record.products = [product.model_dump(mode="json") for product in validated_products]
        record.template_id = body.template_id or "standard_ecommerce"

    return ApplyMappingResponse(
        products=validated_products,
        validation_summary=summary,
    )


@router.post("/enrich", response_model=AIEnrichmentResponse, status_code=status.HTTP_200_OK)
async def enrich_catalogue_products(
    body: AIEnrichmentRequest,
    current_user: CatalogueAccount = Depends(get_current_catalogue_user),
    db: AsyncSession = Depends(get_catalogue_session),
):
    """Generate advisory AI enrichments (descriptions, categories, SEO, tags) for products."""
    await require_catalogue_role(current_user, db, {"owner", "admin", "editor"})

    result = await enrich_products_ai(body.products, body.enrichment_types)
    return result


@router.get("/templates", response_model=List[ProductTemplate], status_code=status.HTTP_200_OK)
async def list_templates(
    current_user: CatalogueAccount = Depends(get_current_catalogue_user),
    db: AsyncSession = Depends(get_catalogue_session),
):
    """List standard and organization-custom product export templates."""
    workspace_id = current_user.active_workspace_id
    custom = await db.execute(select(CatalogueSavedTemplate).where(CatalogueSavedTemplate.workspace_id == workspace_id))
    return get_all_templates() + [ProductTemplate.model_validate(item.payload) for item in custom.scalars().all()]


@router.post("/templates", response_model=ProductTemplate, status_code=status.HTTP_201_CREATED)
async def create_custom_template(
    body: ProductTemplate,
    current_user: CatalogueAccount = Depends(get_current_catalogue_user),
    db: AsyncSession = Depends(get_catalogue_session),
):
    """Save or update a custom export template for the organization."""
    membership = await require_catalogue_role(current_user, db, {"owner", "admin", "editor"})
    org_id = str(membership.organization_id)

    saved = save_custom_template(org_id, body)
    existing = (await db.execute(select(CatalogueSavedTemplate).where(
        CatalogueSavedTemplate.workspace_id == membership.organization_id,
        CatalogueSavedTemplate.template_id == saved.id,
    ))).scalar_one_or_none()
    if existing:
        existing.payload = saved.model_dump(mode="json")
    else:
        db.add(CatalogueSavedTemplate(workspace_id=membership.organization_id, template_id=saved.id, payload=saved.model_dump(mode="json")))
    return saved


@router.delete("/templates/{template_id}", status_code=status.HTTP_200_OK)
async def delete_template(
    template_id: str,
    current_user: CatalogueAccount = Depends(get_current_catalogue_user),
    db: AsyncSession = Depends(get_catalogue_session),
):
    """Delete a custom export template."""
    membership = await require_catalogue_role(current_user, db, {"owner", "admin", "editor"})
    org_id = str(membership.organization_id)

    if template_id in ("standard_ecommerce", "shopify", "woocommerce", "erp_inventory"):
        raise HTTPException(status_code=400, detail={"message": "Built-in templates cannot be deleted"})

    result = await db.execute(delete(CatalogueSavedTemplate).where(
        CatalogueSavedTemplate.workspace_id == membership.organization_id,
        CatalogueSavedTemplate.template_id == template_id,
    ))
    delete_custom_template(org_id, template_id)
    if not result.rowcount:
        raise HTTPException(status_code=404, detail={"message": "Template not found"})
    return {"status": "deleted", "template_id": template_id}


@router.post("/export/preview", response_model=ExportPreviewResponse, status_code=status.HTTP_200_OK)
async def preview_catalogue_export(
    body: ExportRequest,
    current_user: CatalogueAccount = Depends(get_current_catalogue_user),
    db: AsyncSession = Depends(get_catalogue_session),
):
    """Preview export columns and sample mapped rows before downloading."""
    org_id = str(current_user.active_workspace_id)
    template = await _get_template(db, body.template_id, current_user.active_workspace_id)
    products = body.products
    if body.catalogue_id:
        record = await _owned_catalogue_session(db, body.catalogue_id, current_user.active_workspace_id)
        products = [ProductRecord.model_validate(product) for product in record.products]
    preview_data = generate_export_preview(
        products,
        template_id=body.template_id,
        file_format=body.format,
        org_id=org_id,
        template_override=template,
    )
    return ExportPreviewResponse(**preview_data)


@router.post("/export", status_code=status.HTTP_200_OK)
async def export_catalogue_file(
    body: ExportRequest,
    current_user: CatalogueAccount = Depends(get_current_catalogue_user),
    db: AsyncSession = Depends(get_catalogue_session),
):
    """Generate and download genuine XLSX, CSV, or JSON product export."""
    org_id = str(current_user.active_workspace_id)
    template = await _get_template(db, body.template_id, current_user.active_workspace_id)
    products = body.products
    if body.catalogue_id:
        record = await _owned_catalogue_session(db, body.catalogue_id, current_user.active_workspace_id)
        products = [ProductRecord.model_validate(product) for product in record.products]
    if not products:
        raise HTTPException(status_code=400, detail={"message": "No product records to export"})

    file_bytes, filename, media_type = export_catalogue(
        products=products,
        template_id=body.template_id,
        file_format=body.format,
        custom_filename=body.custom_filename,
        org_id=org_id,
        template_override=template,
    )

    encoded_filename = quote(filename)
    headers = {
        "Content-Disposition": f"attachment; filename=\"{filename}\"; filename*=UTF-8''{encoded_filename}",
        "Content-Length": str(len(file_bytes)),
        "X-Record-Count": str(len(products)),
    }

    return Response(
        content=file_bytes,
        media_type=media_type,
        headers=headers,
    )
