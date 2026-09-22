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
    "text/csv",
    "application/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/json",
    "text/json",
    "text/plain",  # many CSVs come as text/plain
    "application/octet-stream",  # generic binary
}

MAX_SIZE_BYTES = 500 * 1024 * 1024  # 500MB


def detect_file_format(filename: str, content_type: str) -> str:
    """Detect the canonical file format from filename extension."""
    suffix = Path(filename).suffix.lower()
    if suffix in (".csv",):
        return "csv"
    elif suffix == ".xlsx":
        return "xlsx"
    elif suffix == ".xls":
        return "xls"
    elif suffix in (".json",):
        return "json"
    elif suffix in (".parquet",):
        return "parquet"
    else:
        raise ValidationError(f"Unsupported file format: {suffix}. Supported: CSV, XLSX, JSON, Parquet")


def detect_encoding(data: bytes) -> str:
    """Detect file encoding using chardet."""
    result = chardet.detect(data[:65536])  # sample first 64KB
    encoding = result.get("encoding") or "utf-8"
    # Normalize
    if encoding.lower() in ("ascii",):
        encoding = "utf-8"
    return encoding


def parse_to_polars(data: bytes, file_format: str, filename: str) -> Tuple[pl.DataFrame, dict]:
    """
    Parse raw file bytes into a Polars DataFrame.
    Returns (dataframe, metadata).
    """
    start = time.perf_counter()
    meta = {"encoding": None, "delimiter": None}

    if file_format == "csv":
        encoding = detect_encoding(data)
        meta["encoding"] = encoding

        try:
            text = data.decode(encoding, errors="replace")
            # Detect delimiter
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
            raise ValidationError(f"Failed to parse CSV: {e}")

    elif file_format in ("xlsx", "xls"):
        try:
            import pandas as pd
            frame = pd.read_excel(io.BytesIO(data), engine="openpyxl" if file_format == "xlsx" else "xlrd")
            df = pl.from_pandas(frame)
        except Exception as e:
            raise ValidationError(f"Failed to parse Excel file: {e}")

    elif file_format == "parquet":
        try:
            df = pl.read_parquet(io.BytesIO(data))
        except Exception as e:
            raise ValidationError(f"Failed to parse Parquet file: {e}")

    elif file_format == "json":
        try:
            import json
            parsed = json.loads(data.decode("utf-8", errors="replace"))
            if isinstance(parsed, list):
                df = pl.DataFrame(parsed, infer_schema_length=10000)
            elif isinstance(parsed, dict):
                # Check if it's records format {"data": [...]}
                if any(isinstance(v, list) for v in parsed.values()):
                    for key, val in parsed.items():
                        if isinstance(val, list):
                            df = pl.DataFrame(val, infer_schema_length=10000)
                            break
                    else:
                        df = pl.DataFrame([parsed])
                else:
                    df = pl.DataFrame([parsed])
            else:
                raise ValidationError("JSON must be an array or object")
        except Exception as e:
            raise ValidationError(f"Failed to parse JSON: {e}")
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
    counts = {d: sample.count(d) for d in candidates}
    best = max(counts, key=counts.get)
    if counts[best] > 0:
        return best
    return ","


def validate_upload(filename: str, size: int, content_type: str) -> str:
    """Validate upload metadata before reading bytes. Returns file_format."""
    if size > MAX_SIZE_BYTES:
        raise ValidationError(f"File too large: {size / 1024 / 1024:.1f}MB. Maximum: 500MB")
    if size == 0:
        raise ValidationError("File is empty")
    file_format = detect_file_format(filename, content_type)
    return file_format



def validate_file_signature(data: bytes, file_format: str) -> None:
    """Validate cheap magic-byte signatures for binary formats."""
    if file_format == "parquet" and not data.startswith(b"PAR1"):
        raise ValidationError("Invalid Parquet file signature")
    if file_format == "xlsx" and data[:4] != b"PK\\x03\\x04":
        raise ValidationError("Invalid XLSX file signature")
    if file_format == "xls" and data[:8] != b"\\xd0\\xcf\\x11\\xe0\\xa1\\xb1\\x1a\\xe1":
        raise ValidationError("Invalid XLS file signature")
