"""Interactive refinery endpoints for safe before/after previews."""

import json
from typing import Any
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
import polars as pl

from app.core.security import get_current_user
from app.models.user import User
from app.ingestion.parser import validate_upload, parse_to_polars
from app.cleaning.engine import TransformationEngine

router = APIRouter()


def _profile(df: pl.DataFrame) -> dict[str, Any]:
    rows = df.height
    cols = df.width
    nulls = sum(df[c].null_count() for c in df.columns)
    cells = max(rows * cols, 1)
    duplicates = rows - df.unique().height
    return {
        "rows": rows,
        "columns": cols,
        "column_names": df.columns,
        "null_cells": nulls,
        "null_rate": round(nulls / cells * 100, 2),
        "duplicate_rows": duplicates,
        "duplicate_rate": round(duplicates / max(rows, 1) * 100, 2),
        "schema": {c: str(df.schema[c]) for c in df.columns},
    }


@router.post("/preview")
async def refinery_preview(
    file: UploadFile = File(...),
    operations: str = Form("[]"),
    current_user: User = Depends(get_current_user),
):
    """Run approved deterministic operations in memory and return a safe preview."""
    raw = await file.read()
    filename = file.filename or "upload"
    try:
        file_format = validate_upload(filename, len(raw), file.content_type or "application/octet-stream")
        ops = json.loads(operations)
        if not isinstance(ops, list):
            raise ValueError("operations must be an array")
        if len(ops) > 100:
            raise ValueError("A preview may contain at most 100 operations")
        before, meta = parse_to_polars(raw, file_format, filename)
        result = TransformationEngine(before).execute_operations(ops)
        after = result["df"]
        return {
            "file": {"name": filename, "format": file_format, **meta},
            "before": _profile(before),
            "after": _profile(after),
            "operations": {k: result[k] for k in ("log", "ops_applied", "ops_skipped", "ops_failed", "duration_ms")},
            "preview": {
                "columns": after.columns,
                "rows": after.head(25).to_dicts(),
            },
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc), "type": "refinery_preview_error"}) from exc
