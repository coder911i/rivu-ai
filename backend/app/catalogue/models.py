"""Data models for Catalogue-to-Product Data Entry solution."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ValidationIssue(BaseModel):
    field: str
    issue_type: str
    severity: str = "error"  # error, warning, info
    message: str
    suggested_fix: Optional[str] = None


class ProductRecord(BaseModel):
    id: str = Field(description="Unique record identifier within catalogue session")
    name: str = Field(default="", description="Product display name / title")
    sku: str = Field(default="", description="Stock keeping unit / product code")
    barcode: Optional[str] = Field(default=None, description="UPC / EAN / Barcode")
    brand: Optional[str] = Field(default=None, description="Manufacturer or brand")
    category: Optional[str] = Field(default=None, description="Primary product category")
    subcategory: Optional[str] = Field(default=None, description="Secondary category")
    description: Optional[str] = Field(default=None, description="Full product description")
    short_description: Optional[str] = Field(default=None, description="Brief summary / excerpt")
    price: float = Field(default=0.0, description="Regular retail price")
    sale_price: Optional[float] = Field(default=None, description="Discounted / promotional price")
    cost_price: Optional[float] = Field(default=None, description="Wholesale / supplier cost")
    currency: str = Field(default="USD", description="ISO currency code (USD, EUR, GBP, INR, etc.)")
    stock_quantity: int = Field(default=0, description="Available stock quantity")
    unit_of_measure: Optional[str] = Field(default="ea", description="Unit (ea, box, kg, pack, etc.)")
    weight: Optional[float] = Field(default=None, description="Item weight")
    dimensions: Optional[str] = Field(default=None, description="Dimensions (e.g. 10x20x5 cm)")
    color: Optional[str] = Field(default=None, description="Color variant")
    size: Optional[str] = Field(default=None, description="Size variant")
    material: Optional[str] = Field(default=None, description="Material / composition")
    image_url: Optional[str] = Field(default=None, description="Public URL to primary product photo")
    tags: List[str] = Field(default_factory=list, description="Search and categorization tags")
    seo_title: Optional[str] = Field(default=None, description="Optimized title for search engines")
    seo_description: Optional[str] = Field(default=None, description="Optimized meta description")
    custom_attributes: Dict[str, Any] = Field(default_factory=dict, description="Unmapped or supplier-specific fields")
    source_row: int = Field(default=0, description="Origin row index in supplier source file")
    validation_status: str = Field(default="valid", description="valid, warning, or error")
    validation_issues: List[ValidationIssue] = Field(default_factory=list)


class FieldMapping(BaseModel):
    source_column: str
    target_field: str
    confidence: float = 1.0
    transform: Optional[str] = None  # trim, uppercase, lowercase, titlecase, currency_to_decimal, to_integer, slugify


class TemplateField(BaseModel):
    name: str
    label: str
    data_type: str = "string"  # string, number, integer, boolean, url, tags
    required: bool = False
    default_value: Optional[Any] = None
    mapped_to: Optional[str] = None  # ProductRecord field name
    description: Optional[str] = None


class ProductTemplate(BaseModel):
    id: str
    name: str
    description: str
    platform: str = "custom"  # standard, shopify, woocommerce, erp, custom
    fields: List[TemplateField] = Field(default_factory=list)
    is_default: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ProductValidationSummary(BaseModel):
    total_records: int = 0
    valid_records: int = 0
    warning_records: int = 0
    error_records: int = 0
    completeness_score: float = 0.0
    issues_by_field: Dict[str, int] = Field(default_factory=dict)
    issue_counts_by_severity: Dict[str, int] = Field(default_factory=dict)


class IngestionUploadResponse(BaseModel):
    catalogue_id: str
    original_filename: str
    file_format: str
    file_size_bytes: int
    row_count: int
    column_count: int
    columns: List[str]
    sheet_names: List[str] = Field(default_factory=list)
    selected_sheet: Optional[str] = None
    total_pages: Optional[int] = None
    sample_records: List[Dict[str, Any]] = Field(default_factory=list)
    # Kept client-side for review and mapping; upload is a stateless catalogue session.
    raw_records: List[Dict[str, Any]] = Field(default_factory=list)
    suggested_mappings: List[FieldMapping] = Field(default_factory=list)
    available_templates: List[ProductTemplate] = Field(default_factory=list)


class ApplyMappingRequest(BaseModel):
    raw_records: List[Dict[str, Any]]
    mappings: List[FieldMapping]
    template_id: Optional[str] = "standard_ecommerce"


class ApplyMappingResponse(BaseModel):
    products: List[ProductRecord]
    validation_summary: ProductValidationSummary


class ValidateProductsRequest(BaseModel):
    products: List[ProductRecord]
    template_id: Optional[str] = "standard_ecommerce"


class AIEnrichmentRequest(BaseModel):
    products: List[ProductRecord]
    enrichment_types: List[str] = Field(default=["description", "category", "seo", "tags"])


class AIEnrichmentSuggestion(BaseModel):
    product_id: str
    suggested_description: Optional[str] = None
    suggested_category: Optional[str] = None
    suggested_seo_title: Optional[str] = None
    suggested_seo_description: Optional[str] = None
    suggested_tags: Optional[List[str]] = None
    reasoning: Optional[str] = None


class AIEnrichmentResponse(BaseModel):
    suggestions: List[AIEnrichmentSuggestion]
    model_used: str
    provider: str


class ExportRequest(BaseModel):
    products: List[ProductRecord]
    template_id: str = "standard_ecommerce"
    format: str = "xlsx"  # xlsx, csv, json
    custom_filename: Optional[str] = None


class ExportPreviewResponse(BaseModel):
    template_name: str
    format: str
    total_records: int
    valid_records: int
    error_records: int
    output_columns: List[str]
    sample_rows: List[Dict[str, Any]]
