"""Pre-configured and dynamic target templates for e-commerce, ERP, and custom export."""

import uuid
from typing import Dict, List, Optional
from datetime import datetime, timezone

from app.catalogue.models import ProductTemplate, TemplateField


# ── 1. Standard E-Commerce (Universal) ───────────────────────────
STANDARD_ECOMMERCE_TEMPLATE = ProductTemplate(
    id="standard_ecommerce",
    name="Standard E-Commerce (Universal)",
    description="Clean, industry-standard product schema compatible with most catalog systems and marketplaces.",
    platform="standard",
    is_default=True,
    fields=[
        TemplateField(name="sku", label="SKU", data_type="string", required=True, mapped_to="sku"),
        TemplateField(name="name", label="Product Name", data_type="string", required=True, mapped_to="name"),
        TemplateField(name="brand", label="Brand", data_type="string", required=False, mapped_to="brand"),
        TemplateField(name="category", label="Category", data_type="string", required=False, mapped_to="category"),
        TemplateField(name="subcategory", label="Subcategory", data_type="string", required=False, mapped_to="subcategory"),
        TemplateField(name="description", label="Description", data_type="string", required=False, mapped_to="description"),
        TemplateField(name="short_description", label="Short Description", data_type="string", required=False, mapped_to="short_description"),
        TemplateField(name="price", label="Price", data_type="number", required=True, mapped_to="price"),
        TemplateField(name="sale_price", label="Sale Price", data_type="number", required=False, mapped_to="sale_price"),
        TemplateField(name="cost_price", label="Cost Price", data_type="number", required=False, mapped_to="cost_price"),
        TemplateField(name="currency", label="Currency", data_type="string", required=False, default_value="USD", mapped_to="currency"),
        TemplateField(name="stock_quantity", label="Stock Quantity", data_type="integer", required=False, default_value=0, mapped_to="stock_quantity"),
        TemplateField(name="unit_of_measure", label="UOM", data_type="string", required=False, default_value="ea", mapped_to="unit_of_measure"),
        TemplateField(name="weight", label="Weight", data_type="number", required=False, mapped_to="weight"),
        TemplateField(name="color", label="Color", data_type="string", required=False, mapped_to="color"),
        TemplateField(name="size", label="Size", data_type="string", required=False, mapped_to="size"),
        TemplateField(name="material", label="Material", data_type="string", required=False, mapped_to="material"),
        TemplateField(name="barcode", label="Barcode", data_type="string", required=False, mapped_to="barcode"),
        TemplateField(name="image_url", label="Image URL", data_type="url", required=False, mapped_to="image_url"),
        TemplateField(name="tags", label="Tags", data_type="tags", required=False, mapped_to="tags"),
        TemplateField(name="seo_title", label="SEO Title", data_type="string", required=False, mapped_to="seo_title"),
        TemplateField(name="seo_description", label="SEO Description", data_type="string", required=False, mapped_to="seo_description"),
    ],
    created_at=datetime.now(timezone.utc).isoformat(),
    updated_at=datetime.now(timezone.utc).isoformat(),
)


# ── 2. Shopify Official Product CSV ──────────────────────────────
SHOPIFY_TEMPLATE = ProductTemplate(
    id="shopify",
    name="Shopify Products CSV",
    description="Compliant with Shopify's official product bulk import specification.",
    platform="shopify",
    is_default=False,
    fields=[
        TemplateField(name="Handle", label="Handle", data_type="string", required=True, mapped_to="_shopify_handle"),
        TemplateField(name="Title", label="Title", data_type="string", required=True, mapped_to="name"),
        TemplateField(name="Body (HTML)", label="Body (HTML)", data_type="string", required=False, mapped_to="description"),
        TemplateField(name="Vendor", label="Vendor", data_type="string", required=False, mapped_to="brand"),
        TemplateField(name="Product Category", label="Product Category", data_type="string", required=False, mapped_to="category"),
        TemplateField(name="Type", label="Type", data_type="string", required=False, mapped_to="subcategory"),
        TemplateField(name="Tags", label="Tags", data_type="tags", required=False, mapped_to="tags"),
        TemplateField(name="Published", label="Published", data_type="boolean", required=False, default_value="TRUE"),
        TemplateField(name="Option1 Name", label="Option1 Name", data_type="string", required=False, default_value="Title"),
        TemplateField(name="Option1 Value", label="Option1 Value", data_type="string", required=False, default_value="Default Title"),
        TemplateField(name="Variant SKU", label="Variant SKU", data_type="string", required=True, mapped_to="sku"),
        TemplateField(name="Variant Grams", label="Variant Grams", data_type="number", required=False, default_value=0),
        TemplateField(name="Variant Inventory Tracker", label="Variant Inventory Tracker", data_type="string", required=False, default_value="shopify"),
        TemplateField(name="Variant Inventory Qty", label="Variant Inventory Qty", data_type="integer", required=False, default_value=0, mapped_to="stock_quantity"),
        TemplateField(name="Variant Inventory Policy", label="Variant Inventory Policy", data_type="string", required=False, default_value="deny"),
        TemplateField(name="Variant Fulfillment Service", label="Variant Fulfillment Service", data_type="string", required=False, default_value="manual"),
        TemplateField(name="Variant Price", label="Variant Price", data_type="number", required=True, mapped_to="price"),
        TemplateField(name="Variant Compare At Price", label="Variant Compare At Price", data_type="number", required=False, mapped_to="sale_price"),
        TemplateField(name="Variant Requires Shipping", label="Variant Requires Shipping", data_type="boolean", required=False, default_value="TRUE"),
        TemplateField(name="Variant Taxable", label="Variant Taxable", data_type="boolean", required=False, default_value="TRUE"),
        TemplateField(name="Variant Barcode", label="Variant Barcode", data_type="string", required=False, mapped_to="barcode"),
        TemplateField(name="Image Src", label="Image Src", data_type="url", required=False, mapped_to="image_url"),
        TemplateField(name="Image Position", label="Image Position", data_type="integer", required=False, default_value=1),
        TemplateField(name="Image Alt Text", label="Image Alt Text", data_type="string", required=False, mapped_to="name"),
        TemplateField(name="SEO Title", label="SEO Title", data_type="string", required=False, mapped_to="seo_title"),
        TemplateField(name="SEO Description", label="SEO Description", data_type="string", required=False, mapped_to="seo_description"),
        TemplateField(name="Status", label="Status", data_type="string", required=False, default_value="active"),
    ],
    created_at=datetime.now(timezone.utc).isoformat(),
    updated_at=datetime.now(timezone.utc).isoformat(),
)


# ── 3. WooCommerce Official Product CSV ──────────────────────────
WOOCOMMERCE_TEMPLATE = ProductTemplate(
    id="woocommerce",
    name="WooCommerce Products CSV",
    description="Matches WooCommerce core product CSV import structure.",
    platform="woocommerce",
    is_default=False,
    fields=[
        TemplateField(name="ID", label="ID", data_type="string", required=False, mapped_to="id"),
        TemplateField(name="Type", label="Type", data_type="string", required=False, default_value="simple"),
        TemplateField(name="SKU", label="SKU", data_type="string", required=True, mapped_to="sku"),
        TemplateField(name="Name", label="Name", data_type="string", required=True, mapped_to="name"),
        TemplateField(name="Published", label="Published", data_type="integer", required=False, default_value=1),
        TemplateField(name="Is featured?", label="Is featured?", data_type="integer", required=False, default_value=0),
        TemplateField(name="Visibility in catalog", label="Visibility in catalog", data_type="string", required=False, default_value="visible"),
        TemplateField(name="Short description", label="Short description", data_type="string", required=False, mapped_to="short_description"),
        TemplateField(name="Description", label="Description", data_type="string", required=False, mapped_to="description"),
        TemplateField(name="Tax status", label="Tax status", data_type="string", required=False, default_value="taxable"),
        TemplateField(name="In stock?", label="In stock?", data_type="integer", required=False, default_value=1),
        TemplateField(name="Stock", label="Stock", data_type="integer", required=False, default_value=0, mapped_to="stock_quantity"),
        TemplateField(name="Regular price", label="Regular price", data_type="number", required=True, mapped_to="price"),
        TemplateField(name="Sale price", label="Sale price", data_type="number", required=False, mapped_to="sale_price"),
        TemplateField(name="Categories", label="Categories", data_type="string", required=False, mapped_to="category"),
        TemplateField(name="Tags", label="Tags", data_type="tags", required=False, mapped_to="tags"),
        TemplateField(name="Images", label="Images", data_type="url", required=False, mapped_to="image_url"),
        TemplateField(name="Weight (kg)", label="Weight (kg)", data_type="number", required=False, mapped_to="weight"),
    ],
    created_at=datetime.now(timezone.utc).isoformat(),
    updated_at=datetime.now(timezone.utc).isoformat(),
)


# ── 4. ERP & Inventory Master ───────────────────────────────────
ERP_INVENTORY_TEMPLATE = ProductTemplate(
    id="erp_inventory",
    name="ERP & Inventory Master",
    description="Designed for ERP systems, inventory software, and warehouse management bulk imports.",
    platform="erp",
    is_default=False,
    fields=[
        TemplateField(name="ItemCode", label="Item Code (SKU)", data_type="string", required=True, mapped_to="sku"),
        TemplateField(name="ItemName", label="Item Name", data_type="string", required=True, mapped_to="name"),
        TemplateField(name="ItemCategory", label="Item Category", data_type="string", required=False, mapped_to="category"),
        TemplateField(name="Brand", label="Brand / Vendor", data_type="string", required=False, mapped_to="brand"),
        TemplateField(name="UnitOfMeasure", label="UOM", data_type="string", required=False, default_value="ea", mapped_to="unit_of_measure"),
        TemplateField(name="StandardCost", label="Standard Cost", data_type="number", required=False, mapped_to="cost_price"),
        TemplateField(name="UnitPrice", label="Selling Unit Price", data_type="number", required=True, mapped_to="price"),
        TemplateField(name="CurrentStock", label="Current Stock", data_type="integer", required=False, default_value=0, mapped_to="stock_quantity"),
        TemplateField(name="Barcode", label="Barcode", data_type="string", required=False, mapped_to="barcode"),
        TemplateField(name="Status", label="Status", data_type="string", required=False, default_value="Active"),
    ],
    created_at=datetime.now(timezone.utc).isoformat(),
    updated_at=datetime.now(timezone.utc).isoformat(),
)


# In-memory template store for organization-scoped custom templates
_CUSTOM_TEMPLATES: Dict[str, Dict[str, ProductTemplate]] = {}


def get_all_templates(org_id: str = "default") -> List[ProductTemplate]:
    """Return built-in standard templates plus any custom templates saved for the organization."""
    built_ins = [
        STANDARD_ECOMMERCE_TEMPLATE,
        SHOPIFY_TEMPLATE,
        WOOCOMMERCE_TEMPLATE,
        ERP_INVENTORY_TEMPLATE,
    ]
    customs = list(_CUSTOM_TEMPLATES.get(str(org_id), {}).values())
    return built_ins + customs


def get_template_by_id(template_id: str, org_id: str = "default") -> Optional[ProductTemplate]:
    """Lookup a template by ID in built-ins or custom store."""
    for tmpl in [STANDARD_ECOMMERCE_TEMPLATE, SHOPIFY_TEMPLATE, WOOCOMMERCE_TEMPLATE, ERP_INVENTORY_TEMPLATE]:
        if tmpl.id == template_id:
            return tmpl
    return _CUSTOM_TEMPLATES.get(str(org_id), {}).get(template_id)


def save_custom_template(org_id: str, template: ProductTemplate) -> ProductTemplate:
    """Save or update a custom template for an organization."""
    if not template.id or template.id in ("standard_ecommerce", "shopify", "woocommerce", "erp_inventory"):
        template.id = f"custom_{uuid.uuid4().hex[:8]}"

    template.platform = "custom"
    template.updated_at = datetime.now(timezone.utc).isoformat()
    if not template.created_at:
        template.created_at = template.updated_at

    org_store = _CUSTOM_TEMPLATES.setdefault(str(org_id), {})
    org_store[template.id] = template
    return template


def delete_custom_template(org_id: str, template_id: str) -> bool:
    """Delete a custom template."""
    org_store = _CUSTOM_TEMPLATES.get(str(org_id), {})
    if template_id in org_store:
        del org_store[template_id]
        return True
    return False
