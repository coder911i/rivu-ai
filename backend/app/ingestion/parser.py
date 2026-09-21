"""Strict, bounded dataset ingestion helpers."""

import io
import time
from pathlib import Path
from typing import Tuple

import chardet
import polars as pl
import structlog

from app.core.exceptions import ValidationError

logger = structlog.get_logger(__name__)

ALLOWED_MIMETYPES = {
    "text/csv", "application/csv", "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/json", "text/json", "text/plain", "application/octet-stream",
}
MAX_SIZE_BYTES = 500 * 1024 * 1024
MAX_COLUMNS = 2_000
MAX_ROWS = 10_000_000


def detect_file_format(filename: str, content_type: str) -> str:
    mapping = {".csv": "csv", ".xlsx": "xlsx", ".xls": "xls", ".json": "json", ".parquet": "parquet"}
    suffix = Path(filename).suffix.lower()
    if suffix not in mapping:
        raise ValidationError("Unsupported file format: CSV, XLSX, XLS, JSON, Parquet")
    if content_type and content_type not in ALLOWED_MIMETYPES:
        raise ValidationError(f"Unsupported content type: {content_type}")
    return mapping[suffix]


def detect_encoding(data: bytes) -> str:
    result = chardet.detect(data[:65536])
    encoding = result.get("encoding") or "utf-8"
    return "utf-8" if encoding.lower() == "ascii" else encoding


def _check_shape(df: pl.DataFrame) -> None:
    if df.height == 0:
        raise ValidationError("File contains no data rows")
    if df.width == 0:
        raise ValidationError("File contains no columns")
    if df.width > MAX_COLUMNS:
        raise ValidationError(f"Dataset has {df.width} columns; maximum is {MAX_COLUMNS}")
    if df.height > MAX_ROWS:
        raise ValidationError(f"Dataset has {df.height} rows; maximum is {MAX_ROWS}")


def parse_to_polars(data: bytes, file_format: str, filename: str) -> Tuple[pl.DataFrame, dict]:
    """Parse a dataset without silently discarding malformed records."""
    start = time.perf_counter()
    meta = {"encoding": None, "delimiter": None, "source_format": file_format}

    if file_format == "csv":
        encoding = detect_encoding(data)
        meta["encoding"] = encoding
        try:
            text = data.decode(encoding, errors="strict")
            delimiter = _detect_csv_delimiter(text[:8192])
            meta["delimiter"] = delimiter
            df = pl.read_csv(
                io.StringIO(text), separator=delimiter, infer_schema_length=10_000,
                null_values=["", "NA", "N/A", "na", "n/a", "NULL", "null", "None", "none", "NaN", "nan"],
                ignore_errors=False, truncate_ragged_lines=False,
            )
        except UnicodeDecodeError as exc:
            raise ValidationError(f"CSV encoding could not be decoded safely: {exc}") from exc
        except Exception as exc:
            raise ValidationError(f"Failed to parse CSV without data loss: {exc}") from exc
    elif file_format == "xlsx":
        try:
            import pandas as pd
            df = pl.from_pandas(pd.read_excel(io.BytesIO(data), engine="openpyxl"))
        except Exception as exc:
            raise ValidationError(f"Failed to parse XLSX: {exc}") from exc
    elif file_format == "xls":
        try:
            import pandas as pd
            df = pl.from_pandas(pd.read_excel(io.BytesIO(data), engine="xlrd"))
        except Exception as exc:
            raise ValidationError(f"Failed to parse XLS: {exc}") from exc
    elif file_format == "parquet":
        try:
            df = pl.read_parquet(io.BytesIO(data))
        except Exception as exc:
            raise ValidationError(f"Failed to parse Parquet: {exc}") from exc
    elif file_format == "json":
        try:
            import json
            parsed = json.loads(data.decode("utf-8", errors="strict"))
            if isinstance(parsed, list):
                df = pl.DataFrame(parsed, infer_schema_length=10_000)
            elif isinstance(parsed, dict):
                record_lists = [v for v in parsed.values() if isinstance(v, list)]
                df = pl.DataFrame(record_lists[0], infer_schema_length=10_000) if record_lists else pl.DataFrame([parsed])
            else:
                raise ValidationError("JSON must be an array or object")
        except ValidationError:
            raise
        except Exception as exc:
            raise ValidationError(f"Failed to parse JSON without data loss: {exc}") from exc
    else:
        raise ValidationError(f"Unknown format: {file_format}")

    _check_shape(df)
    duration = (time.perf_counter() - start) * 1000
    logger.info("file_parsed", format=file_format, rows=df.height, cols=df.width, ms=round(duration, 1))
    return df, meta


def _detect_csv_delimiter(sample: str) -> str:
    candidates = [",", ";", "\t", "|"]
    counts = {d: sample.count(d) for d in candidates}
    ranked = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    if not ranked[0][1]:
        return ","
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        raise ValidationError("CSV delimiter is ambiguous; use a consistent delimiter")
    return ranked[0][0]


def validate_upload(filename: str, size: int, content_type: str) -> str:
    if size > MAX_SIZE_BYTES:
        raise ValidationError(f"File too large: {size / 1024 / 1024:.1f}MB. Maximum: 500MB")
    if size <= 0:
        raise ValidationError("File is empty")
    return detect_file_format(filename, content_type)
