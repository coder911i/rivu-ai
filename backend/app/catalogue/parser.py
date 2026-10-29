"""Multi-format catalogue file parser supporting PDF, Excel, CSV, and JSON."""

import io
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import structlog
from pypdf import PdfReader

from app.core.exceptions import ValidationError
from app.ingestion.parser import detect_encoding, _detect_csv_delimiter

logger = structlog.get_logger(__name__)


def detect_catalogue_format(filename: str, content_type: str = "") -> str:
    """Detect file format from filename extension with validation."""
    suffix = Path(filename).suffix.lower()
    mapping = {
        ".pdf": "pdf",
        ".xlsx": "xlsx",
        ".xls": "xls",
        ".csv": "csv",
        ".json": "json",
    }
    if suffix not in mapping:
        raise ValidationError(
            f"Unsupported file format '{suffix}'. Supported formats: .pdf, .xlsx, .xls, .csv, .json"
        )
    return mapping[suffix]


def parse_catalogue_file(
    data: bytes,
    filename: str,
    sheet_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Parse raw bytes into a list of standardized record dictionaries with extraction metadata."""
    fmt = detect_catalogue_format(filename)
    if len(data) == 0:
        raise ValidationError("Uploaded file is empty (0 bytes)")

    if fmt == "csv":
        return _parse_csv(data, filename)
    elif fmt in ("xlsx", "xls"):
        return _parse_excel(data, filename, sheet_name=sheet_name)
    elif fmt == "json":
        return _parse_json(data, filename)
    elif fmt == "pdf":
        return _parse_pdf(data, filename)
    else:
        raise ValidationError(f"Unhandled file format: {fmt}")


def _parse_csv(data: bytes, filename: str) -> Dict[str, Any]:
    encoding = detect_encoding(data)
    try:
        text = data.decode(encoding, errors="strict")
    except UnicodeDecodeError:
        text = data.decode("latin-1", errors="replace")

    delimiter = _detect_csv_delimiter(text[:8192])
    try:
        df = pd.read_csv(
            io.StringIO(text),
            sep=delimiter,
            dtype=str,
            keep_default_na=False,
            na_values=[""],
            skip_blank_lines=True,
        )
    except Exception as exc:
        raise ValidationError(f"Failed to parse CSV file: {exc}") from exc

    df = _clean_dataframe_columns(df)
    records = df.to_dict(orient="records")
    columns = list(df.columns)

    return {
        "file_format": "csv",
        "original_filename": filename,
        "row_count": len(records),
        "column_count": len(columns),
        "columns": columns,
        "sheet_names": [],
        "total_pages": None,
        "raw_records": records,
        "sample_records": records[:10],
    }


def _parse_excel(data: bytes, filename: str, sheet_name: Optional[str] = None) -> Dict[str, Any]:
    ext = Path(filename).suffix.lower()
    engine = "openpyxl" if ext == ".xlsx" else "xlrd"
    excel_file = io.BytesIO(data)

    try:
        xl = pd.ExcelFile(excel_file, engine=engine)
        available_sheets = xl.sheet_names
        if not available_sheets:
            raise ValidationError("Excel workbook contains no sheets")

        target_sheet = sheet_name if sheet_name and sheet_name in available_sheets else available_sheets[0]
        df = pd.read_excel(
            xl,
            sheet_name=target_sheet,
            dtype=str,
            keep_default_na=False,
            na_values=[""],
        )
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError(f"Failed to read Excel file: {exc}") from exc

    # Clean rows: remove rows where all values are empty or whitespace
    df = df.dropna(how="all")
    df = _clean_dataframe_columns(df)
    records = df.to_dict(orient="records")
    columns = list(df.columns)

    return {
        "file_format": ext.lstrip("."),
        "original_filename": filename,
        "row_count": len(records),
        "column_count": len(columns),
        "columns": columns,
        "sheet_names": available_sheets,
        "selected_sheet": target_sheet,
        "total_pages": None,
        "raw_records": records,
        "sample_records": records[:10],
    }


def _parse_json(data: bytes, filename: str) -> Dict[str, Any]:
    try:
        text = data.decode("utf-8-sig", errors="strict")
        payload = json.loads(text)
    except Exception as exc:
        raise ValidationError(f"Invalid JSON file: {exc}") from exc

    items: List[Dict[str, Any]] = []
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        # Look for standard wrapper keys e.g. "products", "items", "catalog", "data"
        for key in ["products", "items", "catalog", "catalogue", "data", "records", "result"]:
            if key in payload and isinstance(payload[key], list):
                items = payload[key]
                break
        if not items:
            items = [payload]
    else:
        raise ValidationError("JSON root must be an array of objects or an object containing an array")

    if not items:
        raise ValidationError("JSON file contains no record elements")

    # Flatten nested dictionaries
    flattened_records = [_flatten_dict(item) for item in items if isinstance(item, dict)]
    if not flattened_records:
        raise ValidationError("JSON file contains no valid object records")

    # Derive unified column set
    columns_set: set[str] = set()
    for rec in flattened_records:
        columns_set.update(rec.keys())
    columns = sorted(list(columns_set))

    # Standardize all records to have all keys
    normalized_records = []
    for rec in flattened_records:
        clean_rec = {col: str(rec.get(col, "") or "").strip() for col in columns}
        normalized_records.append(clean_rec)

    return {
        "file_format": "json",
        "original_filename": filename,
        "row_count": len(normalized_records),
        "column_count": len(columns),
        "columns": columns,
        "sheet_names": [],
        "total_pages": None,
        "raw_records": normalized_records,
        "sample_records": normalized_records[:10],
    }


def _parse_pdf(data: bytes, filename: str) -> Dict[str, Any]:
    """Extract structured product records and tables from PDF catalogues."""
    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as exc:
        raise ValidationError(f"Failed to read PDF file: {exc}") from exc

    total_pages = len(reader.pages)
    if total_pages == 0:
        raise ValidationError("PDF document contains no pages")

    lines_by_page: List[Tuple[int, str]] = []
    for page_idx, page in enumerate(reader.pages):
        try:
            page_text = page.extract_text() or ""
        except Exception:
            page_text = ""
        for raw_line in page_text.splitlines():
            clean = raw_line.strip()
            if clean:
                lines_by_page.append((page_idx + 1, clean))

    if not lines_by_page:
        raise ValidationError(
            "PDF contains no extractable text. The file appears to be a scanned image or non-text PDF."
        )

    # Table layout inference
    # Detect line delimiter (pipes, tabs, or multi-space gaps >= 2 spaces)
    parsed_rows: List[Dict[str, Any]] = []
    detected_headers: List[str] = []

    # Check for pipe-delimited tables
    pipe_lines = [line for _, line in lines_by_page if "|" in line]
    if len(pipe_lines) >= 3 and len(pipe_lines) >= len(lines_by_page) * 0.2:
        # Pipe-delimited table format
        raw_rows = []
        for p_idx, line in lines_by_page:
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) >= 2:
                raw_rows.append((p_idx, parts))

        if raw_rows:
            # First row is likely header
            first_idx, first_parts = raw_rows[0]
            detected_headers = [f"col_{i+1}" if not h else h for i, h in enumerate(first_parts)]
            detected_headers = _deduplicate_names(detected_headers)

            for p_idx, parts in raw_rows[1:]:
                row_dict = {"_page": str(p_idx)}
                for i, col in enumerate(detected_headers):
                    row_dict[col] = parts[i] if i < len(parts) else ""
                parsed_rows.append(row_dict)
    else:
        # Multi-space / tab delimiter pattern
        tokenized_rows = []
        for p_idx, line in lines_by_page:
            # Split by 2 or more spaces, or tab
            tokens = [t.strip() for t in re.split(r"\t+|\s{2,}", line) if t.strip()]
            if len(tokens) >= 2:
                tokenized_rows.append((p_idx, tokens))

        if tokenized_rows:
            # Detect most common row token count to avoid noisy header/footer lines
            lengths = [len(tokens) for _, tokens in tokenized_rows]
            from collections import Counter
            modal_len = Counter(lengths).most_common(1)[0][0]

            filtered_rows = [(p_idx, tokens) for p_idx, tokens in tokenized_rows if len(tokens) >= modal_len]
            if filtered_rows:
                first_p_idx, first_tokens = filtered_rows[0]
                detected_headers = [f"col_{i+1}" if not h else h for i, h in enumerate(first_tokens[:modal_len])]
                detected_headers = _deduplicate_names(detected_headers)

                for p_idx, tokens in filtered_rows[1:]:
                    row_dict = {"_page": str(p_idx)}
                    for i, col in enumerate(detected_headers):
                        row_dict[col] = tokens[i] if i < len(tokens) else ""
                    parsed_rows.append(row_dict)

    # Fallback if table tokenization failed: create structured rows with line text
    if not parsed_rows:
        detected_headers = ["line_content"]
        for p_idx, line in lines_by_page:
            parsed_rows.append({"_page": str(p_idx), "line_content": line})

    columns = [col for col in detected_headers if col != "_page"]
    if not columns:
        columns = ["text"]
        for r in parsed_rows:
            r["text"] = r.get("line_content", "")

    return {
        "file_format": "pdf",
        "original_filename": filename,
        "row_count": len(parsed_rows),
        "column_count": len(columns),
        "columns": columns,
        "sheet_names": [],
        "total_pages": total_pages,
        "raw_records": parsed_rows,
        "sample_records": parsed_rows[:10],
    }


def _clean_dataframe_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize column names: strip whitespace, remove unnamed columns, deduplicate."""
    clean_cols = []
    for i, col in enumerate(df.columns):
        col_str = str(col).strip()
        if not col_str or col_str.lower().startswith("unnamed:"):
            col_str = f"column_{i+1}"
        clean_cols.append(col_str)

    clean_cols = _deduplicate_names(clean_cols)
    df.columns = clean_cols
    # Replace NaN with empty string
    return df.fillna("")


def _deduplicate_names(names: List[str]) -> List[str]:
    seen: Dict[str, int] = {}
    result = []
    for name in names:
        base = name.strip() or "column"
        if base in seen:
            seen[base] += 1
            result.append(f"{base}_{seen[base]}")
        else:
            seen[base] = 0
            result.append(base)
    return result


def _flatten_dict(d: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    items: Dict[str, Any] = {}
    for k, v in d.items():
        key = f"{prefix}_{k}".strip("_") if prefix else str(k)
        if isinstance(v, dict):
            items.update(_flatten_dict(v, prefix=key))
        elif isinstance(v, list):
            # If list of primitives, join as comma-separated
            if all(isinstance(x, (str, int, float, bool)) for x in v):
                items[key] = ", ".join(str(x) for x in v)
            else:
                items[key] = json.dumps(v)
        else:
            items[key] = v
    return items
