"""Data quality and validation engine for product catalogues."""

import re
from collections import Counter
from typing import Dict, List, Optional, Tuple

from app.catalogue.models import ProductRecord, ProductValidationSummary, ValidationIssue
from app.catalogue.templates import ProductTemplate


def validate_product_records(
    products: List[ProductRecord],
    template: Optional[ProductTemplate] = None,
) -> Tuple[List[ProductRecord], ProductValidationSummary]:
    """Execute validation rules on product records, attaching issues and computing dataset-level quality metrics."""
    validated_products: List[ProductRecord] = []
    issues_by_field: Dict[str, int] = {}
    issue_counts_by_severity: Dict[str, int] = {"error": 0, "warning": 0, "info": 0}

    # Step 1: Detect duplicate SKUs across the dataset
    sku_counts = Counter()
    for p in products:
        sku_clean = (p.sku or "").strip().upper()
        if sku_clean:
            sku_counts[sku_clean] += 1

    total_valid = 0
    total_warning = 0
    total_error = 0
    total_fields_checked = 0
    total_fields_populated = 0

    # Fields expected by the active template or standard model
    expected_field_names: set[str] = {"name", "sku", "price", "description", "category", "brand", "image_url", "stock_quantity"}
    if template and template.fields:
        expected_field_names = {f.mapped_to or f.name for f in template.fields if not f.mapped_to or not f.mapped_to.startswith("_")}

    for p in products:
        issues: List[ValidationIssue] = []
        reported_required: set[str] = set()

        # Rule 1: Product Name required & non-empty
        name_clean = (p.name or "").strip()
        if not name_clean or name_clean.lower() in ("nan", "none", "null", "untitled"):
            issues.append(ValidationIssue(
                field="name",
                issue_type="missing_required_field",
                severity="error",
                message="Product name is required and cannot be empty",
                suggested_fix="Enter a descriptive product name",
            ))
            reported_required.add("name")

        # Rule 2: SKU required & uniqueness
        sku_clean = (p.sku or "").strip().upper()
        if not sku_clean or sku_clean.lower() in ("nan", "none", "null"):
            issues.append(ValidationIssue(
                field="sku",
                issue_type="missing_required_field",
                severity="error",
                message="SKU is required for catalog identification",
                suggested_fix="Provide a unique product SKU or part number",
            ))
            reported_required.add("sku")
        elif sku_counts[sku_clean] > 1:
            issues.append(ValidationIssue(
                field="sku",
                issue_type="duplicate_sku",
                severity="error",
                message=f"Duplicate SKU '{p.sku}' detected ({sku_counts[sku_clean]} products share this SKU)",
                suggested_fix="Modify SKU to ensure uniqueness across the catalog",
            ))

        # Rule 3: Price checks
        try:
            price_val = float(p.price)
            if price_val < 0:
                issues.append(ValidationIssue(
                    field="price",
                    issue_type="negative_price",
                    severity="error",
                    message=f"Price cannot be negative ({price_val})",
                    suggested_fix="Set a positive non-zero retail price",
                ))
            elif price_val == 0.0:
                issues.append(ValidationIssue(
                    field="price",
                    issue_type="zero_price",
                    severity="warning",
                    message="Price is 0.00 — verify if this product is intended to be free or requires price assignment",
                    suggested_fix="Enter regular retail price",
                ))
        except (ValueError, TypeError):
            issues.append(ValidationIssue(
                field="price",
                issue_type="invalid_price_format",
                severity="error",
                message=f"Invalid numeric price format: '{p.price}'",
                suggested_fix="Enter a valid decimal number (e.g. 19.99)",
            ))
            reported_required.add("price")

        # Apply additional required fields from organization target templates.
        if template:
            product_values = p.model_dump()
            for target_field in template.fields:
                if not target_field.required:
                    continue
                mapped = target_field.mapped_to or target_field.name
                if mapped in reported_required:
                    continue
                if mapped.startswith("_"):
                    continue
                value = product_values.get(mapped)
                if mapped.startswith("custom:"):
                    value = p.custom_attributes.get(mapped.split(":", 1)[1])
                if value is None or not str(value).strip() or str(value).lower() in {"none", "null"}:
                    issues.append(ValidationIssue(field=mapped, issue_type="missing_required_field", severity="error", message=f"Required target field '{target_field.name}' is empty", suggested_fix=f"Provide a value for {target_field.name}"))

        # Rule 4: Sale price check
        if p.sale_price is not None:
            try:
                sale_val = float(p.sale_price)
                if sale_val < 0:
                    issues.append(ValidationIssue(
                        field="sale_price",
                        issue_type="negative_sale_price",
                        severity="error",
                        message="Sale price cannot be negative",
                        suggested_fix="Set a positive sale price",
                    ))
                elif p.price and sale_val > float(p.price):
                    issues.append(ValidationIssue(
                        field="sale_price",
                        issue_type="sale_price_exceeds_regular",
                        severity="warning",
                        message=f"Sale price ({sale_val}) exceeds regular price ({p.price})",
                        suggested_fix="Ensure sale price is lower than regular price",
                    ))
            except (ValueError, TypeError):
                issues.append(ValidationIssue(
                    field="sale_price",
                    issue_type="invalid_numeric",
                    severity="error",
                    message="Invalid sale price format",
                ))

        # Rule 5: Stock quantity
        if p.stock_quantity is not None:
            if p.stock_quantity < 0:
                issues.append(ValidationIssue(
                    field="stock_quantity",
                    issue_type="negative_stock",
                    severity="error",
                    message=f"Stock quantity cannot be negative ({p.stock_quantity})",
                    suggested_fix="Set stock quantity to 0 or greater",
                ))

        # Rule 6: Image URL format
        if p.image_url and p.image_url.strip():
            url = p.image_url.strip()
            if not (url.startswith("http://") or url.startswith("https://")):
                issues.append(ValidationIssue(
                    field="image_url",
                    issue_type="invalid_url",
                    severity="warning",
                    message=f"Image URL does not start with http:// or https://: '{url[:40]}...'",
                    suggested_fix="Prefix image link with https://",
                ))

        # Rule 7: Description presence
        if not p.description or not p.description.strip():
            issues.append(ValidationIssue(
                field="description",
                issue_type="empty_description",
                severity="info",
                message="Product has no description",
                suggested_fix="Add descriptive specifications or use AI enrichment to polish",
            ))

        # Measure completeness
        prod_dict = p.model_dump()
        for f_name in expected_field_names:
            total_fields_checked += 1
            val = prod_dict.get(f_name)
            if val is not None and str(val).strip() and str(val) != "0" and str(val) != "0.0":
                total_fields_populated += 1

        # Classify record status
        has_errors = any(i.severity == "error" for i in issues)
        has_warnings = any(i.severity == "warning" for i in issues)

        if has_errors:
            status = "error"
            total_error += 1
        elif has_warnings:
            status = "warning"
            total_warning += 1
        else:
            status = "valid"
            total_valid += 1

        for issue in issues:
            issues_by_field[issue.field] = issues_by_field.get(issue.field, 0) + 1
            issue_counts_by_severity[issue.severity] = issue_counts_by_severity.get(issue.severity, 0) + 1

        # Update product copy
        p_copy = p.model_copy(update={
            "validation_status": status,
            "validation_issues": issues,
        })
        validated_products.append(p_copy)

    completeness_score = (
        round((total_fields_populated / total_fields_checked) * 100, 1)
        if total_fields_checked > 0 else 100.0
    )

    summary = ProductValidationSummary(
        total_records=len(products),
        valid_records=total_valid,
        warning_records=total_warning,
        error_records=total_error,
        completeness_score=completeness_score,
        issues_by_field=issues_by_field,
        issue_counts_by_severity=issue_counts_by_severity,
    )

    return validated_products, summary
