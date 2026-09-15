"""
Dataset Profiling Engine — core of Rivu's data intelligence.

Analyzes every column for: types, nulls, uniqueness, distributions,
outliers, patterns, and semantic types.
"""

import re
import time
from collections import Counter
from typing import Any

import polars as pl
import structlog

logger = structlog.get_logger(__name__)

# ── Regex patterns ────────────────────────────
_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
_PHONE_RE = re.compile(r"^[\+\d][\d\s\-\.\(\)]{6,18}$")
_URL_RE = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)
_CURRENCY_RE = re.compile(r"^[\$€£¥₹]?\s?[\d,]+\.?\d*$")
_DATE_PATTERNS = [
    (re.compile(r"^\d{4}-\d{2}-\d{2}$"), "YYYY-MM-DD"),
    (re.compile(r"^\d{2}/\d{2}/\d{4}$"), "MM/DD/YYYY"),
    (re.compile(r"^\d{2}-\d{2}-\d{4}$"), "DD-MM-YYYY"),
    (re.compile(r"^\d{2}/\d{2}/\d{2}$"), "MM/DD/YY"),
    (re.compile(r"^\d{4}/\d{2}/\d{2}$"), "YYYY/MM/DD"),
    (re.compile(r"^\d{1,2}-[A-Za-z]{3}-\d{4}$"), "DD-Mon-YYYY"),
    (re.compile(r"^[A-Za-z]{3}\s+\d{1,2},?\s+\d{4}$"), "Mon DD, YYYY"),
]
_ID_LIKE_RE = re.compile(r"^[A-Z0-9\-_]{4,}$")


def _infer_semantic_type(
    col_name: str,
    dtype: str,
    sample_values: list[str],
    null_pct: float,
    unique_pct: float,
    total_count: int,
) -> str:
    """
    Determine semantic type using column name, dtype, and sample values.
    Purely deterministic — no AI calls.
    """
    name_lower = col_name.lower()
    sample_str = [str(v) for v in sample_values if v is not None and str(v).strip()]

    # Email detection
    if "email" in name_lower or "e_mail" in name_lower or "mail" in name_lower:
        if _check_pattern_match(sample_str, _EMAIL_RE, 0.5):
            return "email"

    # Phone detection
    if any(x in name_lower for x in ["phone", "mobile", "cell", "tel"]):
        if _check_pattern_match(sample_str, _PHONE_RE, 0.5):
            return "phone"

    # URL detection
    if any(x in name_lower for x in ["url", "link", "website", "href", "uri"]):
        if _check_pattern_match(sample_str, _URL_RE, 0.5):
            return "url"

    # Currency detection
    if any(x in name_lower for x in ["price", "cost", "amount", "revenue", "salary", "fee", "rate", "pay"]):
        if _check_pattern_match(sample_str, _CURRENCY_RE, 0.5):
            return "currency"

    # Date/datetime detection
    date_formats = _detect_date_formats(sample_str)
    if date_formats:
        if any("time" in f.lower() or "T" in f for f in sample_str[:5]):
            return "datetime"
        return "date"

    # Boolean detection
    bool_vals = {"true", "false", "yes", "no", "y", "n", "1", "0", "t", "f"}
    if sample_str and all(s.lower() in bool_vals for s in sample_str[:20]):
        return "boolean"

    # Numeric types
    if dtype in ("Int8", "Int16", "Int32", "Int64", "UInt8", "UInt16", "UInt32", "UInt64"):
        # Check if it could be an ID
        if (
            any(x in name_lower for x in ["id", "_id", "key", "pk", "code", "num", "no", "ref"])
            and unique_pct > 0.9
        ):
            return "id_like"
        return "integer"

    if dtype in ("Float32", "Float64"):
        return "float"

    # String-based types
    if dtype == "String" or dtype == "Utf8":
        # Check all sample values against patterns
        if _check_pattern_match(sample_str, _EMAIL_RE, 0.6):
            return "email"
        if _check_pattern_match(sample_str, _PHONE_RE, 0.6):
            return "phone"
        if _check_pattern_match(sample_str, _URL_RE, 0.6):
            return "url"
        if _check_pattern_match(sample_str, _CURRENCY_RE, 0.5):
            return "currency"
        if date_formats:
            return "date"
        # ID-like: high uniqueness, uppercase alphanumeric
        if unique_pct > 0.9 and _check_pattern_match(sample_str, _ID_LIKE_RE, 0.7):
            return "id_like"
        # Categorical: low cardinality
        if total_count > 10 and unique_pct < 0.05:
            return "categorical"
        # Long text
        avg_len = sum(len(s) for s in sample_str) / max(len(sample_str), 1)
        if avg_len > 100:
            return "text"
        return "string"

    if dtype == "Boolean":
        return "boolean"
    if dtype == "Date":
        return "date"
    if dtype in ("Datetime", "Time"):
        return "datetime"

    return "unknown"


def _check_pattern_match(samples: list[str], pattern: re.Pattern, threshold: float) -> bool:
    if not samples:
        return False
    matches = sum(1 for s in samples if pattern.match(str(s).strip()))
    return matches / len(samples) >= threshold


def _detect_date_formats(samples: list[str]) -> list[str]:
    detected = []
    for pattern, fmt in _DATE_PATTERNS:
        matched = sum(1 for s in samples if pattern.match(str(s).strip()))
        if matched / max(len(samples), 1) > 0.5:
            detected.append(fmt)
    return detected


def profile_dataframe(df: pl.DataFrame, org_id: str, sample_limit: int = 100_000) -> dict:
    """
    Profile a Polars DataFrame. Returns a structured dict suitable
    for persisting to the database.
    """
    start = time.perf_counter()

    # Sample if very large
    if df.height > sample_limit:
        df_sample = df.sample(n=sample_limit, seed=42)
    else:
        df_sample = df

    total_cells = df.height * df.width
    total_nulls = sum(df[col].null_count() for col in df.columns)

    # Duplicate rows
    try:
        dup_count = df.height - df.unique().height
    except Exception:
        dup_count = 0

    # Sample rows for preview (first 25)
    sample_rows = df.head(25).to_dicts()
    # Convert all values to JSON-serializable
    sample_rows = _sanitize_rows(sample_rows)

    # Profile each column
    column_profiles = []
    for idx, col_name in enumerate(df.columns):
        col_profile = _profile_column(df, df_sample, col_name, idx)
        column_profiles.append(col_profile)

    duration_ms = round((time.perf_counter() - start) * 1000)
    logger.info("profiling_complete", rows=df.height, cols=df.width, ms=duration_ms)

    return {
        "row_count": df.height,
        "column_count": df.width,
        "duplicate_row_count": dup_count,
        "duplicate_row_pct": round(dup_count / max(df.height, 1) * 100, 3),
        "total_null_count": total_nulls,
        "total_null_pct": round(total_nulls / max(total_cells, 1) * 100, 3),
        "total_cell_count": total_cells,
        "sample_rows": sample_rows,
        "profiling_duration_ms": duration_ms,
        "columns": column_profiles,
    }


def _profile_column(df: pl.DataFrame, df_sample: pl.DataFrame, col_name: str, idx: int) -> dict:
    series = df[col_name]
    sample_series = df_sample[col_name]
    dtype_str = str(series.dtype)
    n_rows = df.height

    null_count = series.null_count()
    non_null_count = n_rows - null_count
    null_pct = round(null_count / max(n_rows, 1) * 100, 3)

    # Unique values
    try:
        unique_count = series.n_unique()
        uniqueness_pct = round(unique_count / max(n_rows, 1) * 100, 3)
        is_constant = unique_count <= 1
        is_unique = unique_count == n_rows and non_null_count == n_rows
    except Exception:
        unique_count = None
        uniqueness_pct = None
        is_constant = False
        is_unique = False

    # Sample values (non-null, up to 10)
    sample_vals = [
        str(v) for v in series.drop_nulls().head(10).to_list()
    ]

    # Semantic type
    semantic_type = _infer_semantic_type(
        col_name, dtype_str, sample_vals, null_pct or 0, uniqueness_pct or 0, n_rows
    )

    # Value frequency (top 20 non-null values)
    value_frequency = {}
    if non_null_count > 0:
        try:
            vc = series.drop_nulls().cast(pl.Utf8).value_counts(sort=True).head(20)
            value_frequency = {row[col_name]: row["count"] for row in vc.to_dicts()}
        except Exception:
            pass

    # Numeric stats
    numeric_stats = {}
    if dtype_str in (
        "Int8", "Int16", "Int32", "Int64", "UInt8", "UInt16", "UInt32", "UInt64",
        "Float32", "Float64"
    ) and non_null_count > 0:
        try:
            numeric_series = series.drop_nulls().cast(pl.Float64)
            numeric_stats = {
                "min": float(numeric_series.min()),
                "max": float(numeric_series.max()),
                "mean": float(numeric_series.mean()),
                "median": float(numeric_series.median()),
                "std": float(numeric_series.std()),
                "q1": float(numeric_series.quantile(0.25, interpolation="nearest")),
                "q3": float(numeric_series.quantile(0.75, interpolation="nearest")),
            }
            # Skewness (manual)
            mean = numeric_stats["mean"]
            std = numeric_stats["std"]
            if std and std > 0:
                try:
                    skewness = float(((numeric_series - mean) ** 3).mean() / (std ** 3))
                    numeric_stats["skewness"] = round(skewness, 4)
                except Exception:
                    pass
        except Exception as e:
            logger.warning("numeric_stats_failed", col=col_name, error=str(e))

    # String stats
    string_stats = {}
    if dtype_str in ("String", "Utf8", "Categorical") and non_null_count > 0:
        try:
            str_series = series.drop_nulls().cast(pl.Utf8)
            lengths = str_series.str.len_chars()
            string_stats = {
                "min_length": int(lengths.min()),
                "max_length": int(lengths.max()),
                "avg_length": round(float(lengths.mean()), 2),
            }
        except Exception:
            pass

    # Date formats
    date_formats = _detect_date_formats(sample_vals) if semantic_type in ("date", "datetime") else []

    return {
        "column_index": idx,
        "column_name": col_name,
        "inferred_type": dtype_str,
        "semantic_type": semantic_type,
        "null_count": null_count,
        "null_pct": null_pct,
        "non_null_count": non_null_count,
        "unique_count": unique_count,
        "uniqueness_pct": uniqueness_pct,
        "is_constant": is_constant,
        "is_unique": is_unique,
        "numeric_min": numeric_stats.get("min"),
        "numeric_max": numeric_stats.get("max"),
        "numeric_mean": numeric_stats.get("mean"),
        "numeric_median": numeric_stats.get("median"),
        "numeric_std_dev": numeric_stats.get("std"),
        "numeric_q1": numeric_stats.get("q1"),
        "numeric_q3": numeric_stats.get("q3"),
        "numeric_skewness": numeric_stats.get("skewness"),
        "string_min_length": string_stats.get("min_length"),
        "string_max_length": string_stats.get("max_length"),
        "string_avg_length": string_stats.get("avg_length"),
        "date_formats": date_formats or None,
        "value_frequency": value_frequency if value_frequency else None,
        "sample_values": sample_vals or None,
    }


def _sanitize_rows(rows: list[dict]) -> list[dict]:
    """Make rows JSON serializable."""
    result = []
    for row in rows:
        clean = {}
        for k, v in row.items():
            if v is None:
                clean[k] = None
            elif isinstance(v, (int, float, str, bool)):
                clean[k] = v
            else:
                clean[k] = str(v)
        result.append(clean)
    return result
