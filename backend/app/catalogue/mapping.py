"""Dynamic field mapping and normalization engine for product catalogues."""

import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from fuzzywuzzy import fuzz

from app.catalogue.models import FieldMapping, ProductRecord

# Canonical fields in the standard product model with their known synonyms
CANONICAL_TARGET_FIELDS: Dict[str, Dict[str, Any]] = {
    "name": {
        "label": "Product Name",
        "type": "string",
        "required": True,
        "synonyms": [
            "name", "product_name", "title", "product_title", "item_name",
            "item_title", "description", "item_description", "designation", "label"
        ],
    },
    "sku": {
        "label": "SKU / Part Number",
        "type": "string",
        "required": True,
        "synonyms": [
            "sku", "part_number", "part_no", "item_number", "item_no",
            "product_code", "item_code", "model_number", "model_no", "article_number",
            "id", "product_id", "catalog_number", "ref", "reference"
        ],
    },
    "brand": {
        "label": "Brand / Manufacturer",
        "type": "string",
        "required": False,
        "synonyms": ["brand", "manufacturer", "vendor", "make", "designer", "producer"],
    },
    "category": {
        "label": "Category",
        "type": "string",
        "required": False,
        "synonyms": ["category", "product_category", "department", "type", "product_type", "group", "class"],
    },
    "subcategory": {
        "label": "Subcategory",
        "type": "string",
        "required": False,
        "synonyms": ["subcategory", "sub_category", "sub_type", "sub_group", "secondary_category"],
    },
    "description": {
        "label": "Full Description",
        "type": "string",
        "required": False,
        "synonyms": [
            "full_description", "long_description", "details", "specifications",
            "specs", "body", "body_html", "overview", "product_details"
        ],
    },
    "short_description": {
        "label": "Short Description",
        "type": "string",
        "required": False,
        "synonyms": ["short_description", "summary", "teaser", "excerpt", "tagline", "bullet_points"],
    },
    "price": {
        "label": "Price (Regular)",
        "type": "number",
        "required": True,
        "synonyms": [
            "price", "retail_price", "msrp", "unit_price", "list_price",
            "selling_price", "our_price", "price_usd", "amount", "rate", "standard_price"
        ],
    },
    "sale_price": {
        "label": "Sale / Promotional Price",
        "type": "number",
        "required": False,
        "synonyms": ["sale_price", "discount_price", "offer_price", "promo_price", "special_price", "deal_price"],
    },
    "cost_price": {
        "label": "Wholesale Cost Price",
        "type": "number",
        "required": False,
        "synonyms": ["cost", "cost_price", "wholesale_price", "supplier_price", "purchase_price", "base_cost"],
    },
    "currency": {
        "label": "Currency",
        "type": "string",
        "required": False,
        "synonyms": ["currency", "curr", "currency_code", "iso_currency"],
    },
    "stock_quantity": {
        "label": "Stock Quantity",
        "type": "integer",
        "required": False,
        "synonyms": [
            "stock", "stock_quantity", "quantity", "qty", "inventory",
            "units_available", "qty_available", "inventory_qty", "qty_in_stock", "on_hand"
        ],
    },
    "unit_of_measure": {
        "label": "Unit of Measure",
        "type": "string",
        "required": False,
        "synonyms": ["uom", "unit", "unit_of_measure", "packaging", "pack_size", "per"],
    },
    "weight": {
        "label": "Weight",
        "type": "number",
        "required": False,
        "synonyms": ["weight", "item_weight", "package_weight", "shipping_weight", "gross_weight", "net_weight"],
    },
    "dimensions": {
        "label": "Dimensions",
        "type": "string",
        "required": False,
        "synonyms": ["dimensions", "size_dimensions", "measurements", "l_w_h", "box_dimensions"],
    },
    "color": {
        "label": "Color",
        "type": "string",
        "required": False,
        "synonyms": ["color", "colour", "shade", "finish", "pattern"],
    },
    "size": {
        "label": "Size",
        "type": "string",
        "required": False,
        "synonyms": ["size", "sizing", "apparel_size", "shoe_size"],
    },
    "material": {
        "label": "Material",
        "type": "string",
        "required": False,
        "synonyms": ["material", "composition", "fabric", "construction"],
    },
    "barcode": {
        "label": "Barcode / UPC / EAN",
        "type": "string",
        "required": False,
        "synonyms": ["barcode", "upc", "ean", "gtin", "isbn"],
    },
    "image_url": {
        "label": "Product Image URL",
        "type": "url",
        "required": False,
        "synonyms": [
            "image", "image_url", "photo", "picture", "image_src",
            "image_link", "img_url", "main_image", "thumbnail", "photo_url"
        ],
    },
    "tags": {
        "label": "Tags / Keywords",
        "type": "tags",
        "required": False,
        "synonyms": ["tags", "keywords", "labels", "search_terms", "attributes"],
    },
    "seo_title": {
        "label": "SEO Title",
        "type": "string",
        "required": False,
        "synonyms": ["seo_title", "meta_title", "page_title"],
    },
    "seo_description": {
        "label": "SEO Description",
        "type": "string",
        "required": False,
        "synonyms": ["seo_description", "meta_description", "meta_desc"],
    },
}


def _clean_key(key: str) -> str:
    """Normalize a column name for matching."""
    s = str(key).strip().lower()
    return re.sub(r"[^a-z0-9]", "_", s).strip("_")


def infer_field_mappings(
    source_columns: List[str],
    sample_records: List[Dict[str, Any]],
) -> List[FieldMapping]:
    """Inspect source column names and representative values to suggest canonical field mappings."""
    mappings: List[FieldMapping] = []
    used_targets: set[str] = set()

    # Pre-extract sample column values
    col_samples: Dict[str, List[str]] = {col: [] for col in source_columns}
    for row in sample_records[:10]:
        for col in source_columns:
            val = str(row.get(col, "") or "").strip()
            if val:
                col_samples[col].append(val)

    # First pass: High confidence matches (exact synonym match or strong fuzzy)
    scored_candidates: List[Tuple[float, str, str, Optional[str]]] = []

    for col in source_columns:
        clean_col = _clean_key(col)
        samples = col_samples.get(col, [])

        for target_field, meta in CANONICAL_TARGET_FIELDS.items():
            synonyms = meta["synonyms"]
            field_type = meta["type"]

            # Exact synonym match
            if clean_col in synonyms:
                transform = _default_transform(field_type)
                scored_candidates.append((1.0, col, target_field, transform))
                continue

            # Substring match (e.g., "product_sku_number" contains "sku")
            sub_match = any(syn in clean_col for syn in synonyms if len(syn) >= 3)
            if sub_match:
                transform = _default_transform(field_type)
                scored_candidates.append((0.85, col, target_field, transform))
                continue

            # Fuzzy match with synonyms
            best_ratio = 0
            for syn in synonyms:
                ratio = fuzz.ratio(clean_col, syn)
                if ratio > best_ratio:
                    best_ratio = ratio

            if best_ratio >= 80:
                confidence = round(best_ratio / 100.0 * 0.9, 2)
                transform = _default_transform(field_type)
                scored_candidates.append((confidence, col, target_field, transform))
                continue

            # Value-based heuristic fallback:
            # Check if values look like image URLs
            if field_type == "url" and samples and all(_is_url(v) for v in samples[:3]):
                scored_candidates.append((0.75, col, target_field, None))
            # Check if values look like prices ($12.99, 45.00)
            elif field_type == "number" and target_field in ("price", "cost_price") and samples:
                if any(_looks_like_currency(v) for v in samples):
                    scored_candidates.append((0.70, col, target_field, "currency_to_decimal"))

    # Sort candidates by confidence descending
    scored_candidates.sort(key=lambda x: x[0], reverse=True)

    assigned_sources: set[str] = set()
    for conf, source_col, target_field, transform in scored_candidates:
        if source_col not in assigned_sources and target_field not in used_targets:
            mappings.append(FieldMapping(
                source_column=source_col,
                target_field=target_field,
                confidence=conf,
                transform=transform,
            ))
            assigned_sources.add(source_col)
            used_targets.add(target_field)

    # For remaining source columns that didn't match canonical fields, suggest custom attribute
    for col in source_columns:
        if col not in assigned_sources and not col.startswith("_"):
            mappings.append(FieldMapping(
                source_column=col,
                target_field=f"custom:{col}",
                confidence=0.5,
                transform="trim",
            ))

    return mappings


def apply_field_mappings(
    raw_records: List[Dict[str, Any]],
    mappings: List[FieldMapping],
) -> List[ProductRecord]:
    """Transform raw records into standardized ProductRecord entities according to mapping rules."""
    products: List[ProductRecord] = []
    mapping_dict = {m.source_column: m for m in mappings}

    for row_idx, raw_row in enumerate(raw_records):
        prod_data: Dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "source_row": row_idx + 1,
            "custom_attributes": {},
            "tags": [],
        }

        for source_col, raw_val in raw_row.items():
            if source_col.startswith("_"):
                continue  # skip internal metadata like _page

            mapping = mapping_dict.get(source_col)
            if not mapping or mapping.target_field == "ignore":
                continue

            transformed_val = _apply_transformation(raw_val, mapping.transform)
            target = mapping.target_field

            if target.startswith("custom:"):
                attr_name = target.split(":", 1)[1]
                prod_data["custom_attributes"][attr_name] = transformed_val
            elif target in CANONICAL_TARGET_FIELDS:
                expected_type = CANONICAL_TARGET_FIELDS[target]["type"]
                typed_val = _coerce_to_canonical_type(transformed_val, expected_type)
                prod_data[target] = typed_val
            else:
                prod_data["custom_attributes"][target] = transformed_val

        # Guarantee string defaults for required fields if missing
        if "name" not in prod_data or not prod_data["name"]:
            prod_data["name"] = f"Product #{row_idx + 1}"
        if "sku" not in prod_data or not prod_data["sku"]:
            prod_data["sku"] = f"SKU-{row_idx + 1:04d}"

        product = ProductRecord(**prod_data)
        products.append(product)

    return products


def _default_transform(field_type: str) -> Optional[str]:
    if field_type == "number":
        return "currency_to_decimal"
    elif field_type == "integer":
        return "to_integer"
    return "trim"


def _apply_transformation(val: Any, transform: Optional[str]) -> Any:
    if val is None:
        return ""
    s = str(val).strip()

    if not transform or transform == "trim":
        return s
    elif transform == "uppercase":
        return s.upper()
    elif transform == "lowercase":
        return s.lower()
    elif transform == "titlecase":
        return s.title()
    elif transform == "currency_to_decimal":
        # Remove currency symbols ($ € £ ₹ ¥) and thousands commas
        cleaned = re.sub(r"[^\d.-]", "", s)
        try:
            return round(float(cleaned), 2)
        except ValueError:
            return 0.0
    elif transform == "to_integer":
        cleaned = re.sub(r"[^\d.-]", "", s)
        try:
            return int(float(cleaned))
        except (ValueError, TypeError):
            return 0
    elif transform == "slugify":
        clean = re.sub(r"[^a-zA-Z0-9]+", "-", s.lower()).strip("-")
        return clean
    return s


def _coerce_to_canonical_type(val: Any, expected_type: str) -> Any:
    if expected_type == "number":
        if isinstance(val, (int, float)):
            return float(val)
        cleaned = re.sub(r"[^\d.-]", "", str(val))
        try:
            return round(float(cleaned), 2)
        except ValueError:
            return 0.0
    elif expected_type == "integer":
        if isinstance(val, int):
            return val
        cleaned = re.sub(r"[^\d-]", "", str(val))
        try:
            return int(float(cleaned))
        except (ValueError, TypeError):
            return 0
    elif expected_type == "tags":
        if isinstance(val, list):
            return [str(x).strip() for x in val if str(x).strip()]
        return [t.strip() for t in str(val).split(",") if t.strip()]
    return str(val).strip() if val is not None else ""


def _is_url(val: str) -> bool:
    return val.startswith("http://") or val.startswith("https://")


def _looks_like_currency(val: str) -> bool:
    s = val.strip()
    return bool(re.search(r"[$€£₹¥]|(?:\d+\.\d{2})", s))
