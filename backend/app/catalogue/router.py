"""API Router for Catalogue-to-Product Data Entry solution."""

import uuid
from typing import List, Optional
from urllib.parse import quote

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalogue.ai_enrich import enrich_products_ai
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
from app.core.database import get_session
from app.core.exceptions import ValidationError
from app.core.security import get_current_user, require_org_role
from app.models.user import User

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.post("/upload", response_model=IngestionUploadResponse, status_code=status.HTTP_200_OK)
async def upload_catalogue(
    file: UploadFile = File(...),
    sheet_name: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Upload and inspect a supplier catalogue file (.pdf, .xlsx, .xls, .csv, .json)."""
    membership = await require_org_role(current_user, db, {"owner", "admin", "editor"})
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
    available_templates = get_all_templates(org_id=org_id)

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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Apply field mappings and deterministic normalization rules to raw records."""
    membership = await require_org_role(current_user, db, {"owner", "admin", "editor"})
    org_id = str(membership.organization_id)

    template = get_template_by_id(body.template_id or "standard_ecommerce", org_id=org_id)
    products = apply_field_mappings(body.raw_records, body.mappings)
    validated_products, summary = validate_product_records(products, template)

    return ApplyMappingResponse(
        products=validated_products,
        validation_summary=summary,
    )


@router.post("/validate", response_model=ApplyMappingResponse, status_code=status.HTTP_200_OK)
async def validate_catalogue_products(
    body: ValidateProductsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Re-validate products after manual edits or template changes."""
    membership = await require_org_role(current_user, db, {"owner", "admin", "editor"})
    org_id = str(membership.organization_id)

    template = get_template_by_id(body.template_id or "standard_ecommerce", org_id=org_id)
    validated_products, summary = validate_product_records(body.products, template)

    return ApplyMappingResponse(
        products=validated_products,
        validation_summary=summary,
    )


@router.post("/enrich", response_model=AIEnrichmentResponse, status_code=status.HTTP_200_OK)
async def enrich_catalogue_products(
    body: AIEnrichmentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Generate advisory AI enrichments (descriptions, categories, SEO, tags) for products."""
    await require_org_role(current_user, db, {"owner", "admin", "editor"})

    result = await enrich_products_ai(body.products, body.enrichment_types)
    return result


@router.get("/templates", response_model=List[ProductTemplate], status_code=status.HTTP_200_OK)
async def list_templates(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """List standard and organization-custom product export templates."""
    org_id = str(getattr(current_user, "active_org_id", "default"))
    return get_all_templates(org_id=org_id)


@router.post("/templates", response_model=ProductTemplate, status_code=status.HTTP_201_CREATED)
async def create_custom_template(
    body: ProductTemplate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Save or update a custom export template for the organization."""
    membership = await require_org_role(current_user, db, {"owner", "admin", "editor"})
    org_id = str(membership.organization_id)

    saved = save_custom_template(org_id, body)
    return saved


@router.delete("/templates/{template_id}", status_code=status.HTTP_200_OK)
async def delete_template(
    template_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Delete a custom export template."""
    membership = await require_org_role(current_user, db, {"owner", "admin", "editor"})
    org_id = str(membership.organization_id)

    if template_id in ("standard_ecommerce", "shopify", "woocommerce", "erp_inventory"):
        raise HTTPException(status_code=400, detail={"message": "Built-in templates cannot be deleted"})

    deleted = delete_custom_template(org_id, template_id)
    if not deleted:
        raise HTTPException(status_code=404, detail={"message": "Template not found"})
    return {"status": "deleted", "template_id": template_id}


@router.post("/export/preview", response_model=ExportPreviewResponse, status_code=status.HTTP_200_OK)
async def preview_catalogue_export(
    body: ExportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Preview export columns and sample mapped rows before downloading."""
    org_id = str(getattr(current_user, "active_org_id", "default"))
    preview_data = generate_export_preview(
        body.products,
        template_id=body.template_id,
        file_format=body.format,
        org_id=org_id,
    )
    return ExportPreviewResponse(**preview_data)


@router.post("/export", status_code=status.HTTP_200_OK)
async def export_catalogue_file(
    body: ExportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Generate and download genuine XLSX, CSV, or JSON product export."""
    org_id = str(getattr(current_user, "active_org_id", "default"))
    if not body.products:
        raise HTTPException(status_code=400, detail={"message": "No product records to export"})

    file_bytes, filename, media_type = export_catalogue(
        products=body.products,
        template_id=body.template_id,
        file_format=body.format,
        custom_filename=body.custom_filename,
        org_id=org_id,
    )

    encoded_filename = quote(filename)
    headers = {
        "Content-Disposition": f"attachment; filename=\"{filename}\"; filename*=UTF-8''{encoded_filename}",
        "Content-Length": str(len(file_bytes)),
        "X-Record-Count": str(len(body.products)),
    }

    return Response(
        content=file_bytes,
        media_type=media_type,
        headers=headers,
    )
