"""File ingestion: upload, validate, parse, store."""

import io
import time
from pathlib import Path
from typing import Tuple

import chardet
import polars as pl
import structlog

from app.core.exceptions import ValidationError

logger = structlog.get_logger(__name__)

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".json", ".parquet"}
ALLOWED_MIMETYPES = {
    "text/csv", "application/csv", "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/json", "text/json", "text/plain", "application/octet-stream",
}
MAX_SIZE_BYTES = 500 * 1024 * 1024


def detect_file_format(filename: str, content_type: str) -> str:
    """Detect the canonical file format from filename extension."""
    suffix = Path(filename).suffix.lower()
    formats = {".csv": "csv", ".xlsx": "xlsx", ".xls": "xls", ".json": "json", ".parquet": "parquet"}
    if suffix not in formats:
        raise ValidationError(f"Unsupported file format: {suffix}. Supported: CSV, XLSX, JSON, Parquet")
    return formats[suffix]


def detect_encoding(data: bytes) -> str:
    """Prefer strict UTF-8; otherwise use chardet, with Windows-1252 as a documented fallback.

    UTF-8 is checked against the complete file so an invalid byte after the sample
    window cannot silently turn into a replacement character. Windows-1252 is a
    practical last resort for legacy exports from older Windows/Excel workflows.
    """
    if data.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    try:
        data.decode("utf-8", errors="strict")
        return "utf-8"
    except UnicodeDecodeError:
        detected = chardet.detect(data[:65536]).get("encoding")
        if detected:
            try:
                data.decode(detected, errors="strict")
                return detected
            except (LookupError, UnicodeDecodeError):
                pass
        try:
            data.decode("cp1252", errors="strict")
            return "cp1252"
        except UnicodeDecodeError:
            # Keep the failure explicit rather than silently corrupting text.
            raise ValidationError(
                "CSV encoding could not be detected. Save the file as UTF-8 or Windows-1252."
            )


def parse_to_polars(data: bytes, file_format: str, filename: str) -> Tuple[pl.DataFrame, dict]:
    """Parse raw file bytes into a Polars DataFrame and return parsing metadata."""
    start = time.perf_counter()
    meta = {"encoding": None, "delimiter": None}

    if file_format == "csv":
        encoding = detect_encoding(data)
        meta["encoding"] = encoding
        try:
            text = data.decode(encoding, errors="strict")
            delimiter = _detect_csv_delimiter(text[:4096])
            meta["delimiter"] = delimiter
            df = pl.read_csv(
                io.StringIO(text),
                separator=delimiter,
                infer_schema_length=10000,
                null_values=["", "NA", "N/A", "na", "n/a", "NULL", "null", "None", "none", "NaN", "nan"],
                ignore_errors=False,
                truncate_ragged_lines=False,
            )
        except Exception as e:
            raise ValidationError(f"Failed to parse CSV: {e}") from e
    elif file_format in ("xlsx", "xls"):
        try:
            import pandas as pd
            frame = pd.read_excel(io.BytesIO(data), engine="openpyxl" if file_format == "xlsx" else "xlrd")
            df = pl.from_pandas(frame)
        except Exception as e:
            raise ValidationError(f"Failed to parse Excel file: {e}") from e
    elif file_format == "parquet":
        try:
            df = pl.read_parquet(io.BytesIO(data))
        except Exception as e:
            raise ValidationError(f"Failed to parse Parquet file: {e}") from e
    elif file_format == "json":
        try:
            import json
            parsed = json.loads(data.decode("utf-8-sig", errors="strict"))
            if isinstance(parsed, list):
                df = pl.DataFrame(parsed, infer_schema_length=10000)
            elif isinstance(parsed, dict):
                list_value = next((v for v in parsed.values() if isinstance(v, list)), None)
                df = pl.DataFrame(list_value, infer_schema_length=10000) if list_value is not None else pl.DataFrame([parsed])
            else:
                raise ValidationError("JSON must be an array or object")
        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(f"Failed to parse JSON: {e}") from e
    else:
        raise ValidationError(f"Unknown format: {file_format}")

    duration = (time.perf_counter() - start) * 1000
    logger.info("file_parsed", format=file_format, rows=df.height, cols=df.width, ms=round(duration, 1))
    if df.height == 0:
        raise ValidationError("File contains no data rows")
    if df.width == 0:
        raise ValidationError("File contains no columns")
    return df, meta


def _detect_csv_delimiter(sample: str) -> str:
    """Heuristic CSV delimiter detection."""
    candidates = [",", ";", "\t", "|"]
    counts = {delimiter: sample.count(delimiter) for delimiter in candidates}
    best = max(counts, key=counts.get)
    return best if counts[best] > 0 else ","


def validate_upload(filename: str, size: int, content_type: str) -> str:
    """Validate upload metadata before reading bytes. Returns file_format."""
    if size > MAX_SIZE_BYTES:
        raise ValidationError(f"File too large: {size / 1024 / 1024:.1f}MB. Maximum: 500MB")
    if size == 0:
        raise ValidationError("File is empty")
    return detect_file_format(filename, content_type)


def validate_file_signature(data: bytes, file_format: str) -> None:
    """Validate the documented binary container signatures before parsing."""
    signatures = {
        "parquet": ((b"PAR1",), "Parquet"),
        # Office Open XML workbooks are ZIP packages; a non-empty XLSX package
        # starts with a ZIP local-file header.
        "xlsx": ((b"PK\x03\x04",), "XLSX"),
        # Legacy .xls workbooks use the OLE Compound File Binary Format header.
        "xls": ((b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",), "XLS"),
    }
    if file_format not in signatures:
        return
    accepted, label = signatures[file_format]
    if not any(data.startswith(signature) for signature in accepted):
        raise ValidationError(f"Invalid {label} file signature")
