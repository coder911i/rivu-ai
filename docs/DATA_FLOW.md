# Rivu AI — Data Flow Specification

**Product:** Rivu AI by WaterTing  
**Workflow:** Supplier Catalogue Ingestion → Refinement → Product Export  

---

## 1. End-to-End Workflow Diagram

```mermaid
sequenceDiagram
    autonumber
    actor User as Operator / Merchandiser
    participant UI as Rivu Web Workspace
    participant API as FastAPI Ingestion Router
    participant Parser as Catalogue Parser Engine
    participant S3 as Private Storage (S3)
    participant Mapper as Field Mapping Engine
    participant Validator as Quality & Validation Engine
    participant AI as Optional AI Advisory (Groq)
    participant Exporter as Multi-Format Export Engine

    User->>UI: Upload supplier catalogue (.pdf, .xlsx, .csv, .json)
    UI->>API: POST /api/v1/catalogue/upload
    API->>S3: Persist raw catalogue with SHA-256 checksum
    API->>Parser: Parse file bytes into normalized record stream
    Parser-->>API: Extracted raw records & source columns
    API->>Mapper: Auto-infer canonical product fields (confidence score)
    Mapper-->>API: Suggested mappings + preview rows
    API-->>UI: Return upload summary, detected fields & initial mappings

    User->>UI: Inspect & adjust field mappings / transformations
    UI->>API: POST /api/v1/catalogue/map (source-to-target rules)
    API->>Mapper: Apply field mappings & deterministic transformations
    API->>Validator: Run validation rules against active template
    Validator-->>API: Validation issues & data quality metrics
    API-->>UI: Transformed product records & validation report

    Note over User,UI: Interactive Review & Workspace Editing
    User->>UI: Inline edit fields, fix errors, filter invalid items
    opt User clicks AI Enrichment
        User->>UI: Request AI cleanup (categories, descriptions, SEO)
        UI->>API: POST /api/v1/catalogue/enrich
        API->>AI: Fact-grounded prompt with extracted product context
        AI-->>API: Proposed enhancements (categories, tags, copy)
        API-->>UI: Return proposed suggestions for user review
        User->>UI: Accept or reject suggestions
    end

    User->>UI: Select Target Template (Shopify, WooCommerce, ERP, Custom)
    User->>UI: Request Export (XLSX, CSV, JSON)
    UI->>API: POST /api/v1/catalogue/export
    API->>Exporter: Transform approved records into target template format
    Exporter-->>API: Binary stream / file artifact
    API-->>UI: Trigger file download in browser
    API->>S3: Archive export manifest & audit record
```

---

## 2. Stage Details & Data Transformations

### Stage 1: File Upload & Ingestion
- **Input:** Raw binary bytes of uploaded file (HTTP multipart).
- **Validation:**
  - File extension verification (`.pdf`, `.xlsx`, `.xls`, `.csv`, `.json`).
  - Size check (configured maximum 500 MB).
  - Binary signature check (ZIP signature for XLSX, OLE for XLS, `%PDF-` header for PDF).
- **Storage:** Persisted to `orgs/{org_id}/catalogues/{catalogue_id}/source/{filename}`.
- **Output:** Raw tabular data structure: List of dicts representing raw source rows, with `_source_row_index` tracked for every entry.

### Stage 2: Schema Inference & Field Mapping
- **Input:** Raw column names (e.g., `Part #`, `Item Description`, `List Price`, `Qty Available`, `Pkg Wt (lbs)`).
- **Inference Logic:**
  - Standard dictionary matching with aliases.
  - Levenshtein string similarity against standard target fields.
  - Data sample inspection (detecting numeric currencies, URL patterns, integers).
- **Mapping Specification:**
  ```json
  {
    "mappings": [
      { "source_column": "Part #", "target_field": "sku", "confidence": 0.95 },
      { "source_column": "Item Description", "target_field": "name", "confidence": 0.90 },
      { "source_column": "List Price", "target_field": "price", "transform": "currency_to_decimal", "confidence": 0.98 },
      { "source_column": "Qty Available", "target_field": "stock_quantity", "transform": "to_integer", "confidence": 0.95 }
    ]
  }
  ```

### Stage 3: Normalization & Validation
- **Input:** Mapped records.
- **Normalization:**
  - Prices converted to float with 2 decimal precision.
  - Currencies isolated.
  - Whitespace trimmed.
  - SKU stripped of non-printable characters and uppercase normalized.
- **Validation Rules:**
  - Check missing required fields.
  - Duplicate SKU detection across the batch.
  - Price validity ($ > 0.00).
- **Output:** Canonical Product Records with status (`valid`, `warning`, `error`) and structured issue objects.

### Stage 4: Workspace Editing & User Approval
- User can search, sort, filter by issue severity (`All`, `Errors only`, `Warnings only`, `Valid only`).
- User can perform inline cell edits, add products, duplicate rows, or delete junk rows.
- Unsaved changes indicator prevents accidental navigation data loss.

### Stage 5: Export Serialization
- **Shopify Template:** Formats Handles (kebab-cased from product title), HTML-formatted descriptions, Variant pricing, and Shopify-compatible column headers.
- **WooCommerce Template:** Maps Regular Price, Stock status (`instock`/`outofstock`), and image galleries.
- **Standard E-Commerce / Universal:** Complete flat or structured schema.
- **File Serialization:**
  - **XLSX:** Multi-column Excel with typed cells (numeric price, integer stock).
  - **CSV:** Quoted, UTF-8 encoded with standard CRLF or LF line endings.
  - **JSON:** Pretty-printed JSON array.
