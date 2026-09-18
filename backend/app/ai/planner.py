"""
AI Transformation Planner — generates structured, allowlisted transformation plans.

The LLM NEVER modifies data. It only generates a JSON plan.
The plan is validated against an allowlist before execution.
"""

import json
import re
from typing import Any
import structlog

from app.ai.base import AIProvider, AIMessage
from app.core.exceptions import AIError

logger = structlog.get_logger(__name__)

# ── Allowlisted transformation operations ─────
ALLOWED_OPERATIONS = {
    "trim_whitespace",
    "normalize_whitespace",
    "lowercase",
    "uppercase",
    "title_case",
    "standardize_date",
    "standardize_datetime",
    "coerce_numeric",
    "coerce_boolean",
    "normalize_currency",
    "normalize_phone",
    "normalize_email",
    "normalize_category",
    "fill_null",
    "drop_nulls",
    "remove_duplicates",
    "flag_duplicates",
    "flag_outliers",
    "replace_value",
    "regex_replace",
    "clip_numeric",
    "drop_column",
    "rename_column",
}

SYSTEM_PROMPT = """You are Rivu's Data Transformation Planner. Your job is to analyze a dataset profile and quality report, then generate a precise, actionable transformation plan.

CRITICAL RULES:
1. You NEVER modify data directly. You only create a JSON plan.
2. Only use operations from the allowed list.
3. Every operation must have: type, column (if applicable), confidence (0-1), reason.
4. Be specific and accurate. Don't suggest operations that aren't needed.
5. Focus on the most impactful fixes first.
6. Return ONLY valid JSON — no explanation text outside the JSON.

Allowed operations:
- trim_whitespace: Remove leading/trailing whitespace from string column
- normalize_whitespace: Collapse multiple spaces to single space
- lowercase / uppercase / title_case: Standardize text case
- standardize_date: Convert dates to ISO 8601 (YYYY-MM-DD)
- standardize_datetime: Convert datetimes to ISO 8601
- coerce_numeric: Convert string column to numeric
- normalize_currency: Standardize currency format (remove symbols, parse to float)
- normalize_phone: Standardize phone to E.164 format
- normalize_email: Lowercase email, trim whitespace
- normalize_category: Standardize category values (consistent capitalization)
- fill_null: Fill null values with specified fill_value or strategy (mean/median/mode/empty_string)
- remove_duplicates: Remove duplicate rows (keep first occurrence)
- flag_duplicates: Add a boolean column flagging duplicate rows
- flag_outliers: Add a boolean column flagging statistical outliers
- replace_value: Replace specific value with another
- clip_numeric: Clip numeric values to [min, max] range
- drop_column: Drop a column

Response format:
{
  "dataset_summary": "Brief description of what this dataset contains",
  "detected_domain": "e.g., customer_data, financial_transactions, product_catalog",
  "operations": [
    {
      "type": "operation_name",
      "column": "column_name_or_null_for_row_ops",
      "confidence": 0.95,
      "reason": "Clear explanation of why this transformation is needed",
      "parameters": {}
    }
  ],
  "estimated_quality_gain": 15.5,
  "summary": "What these transformations will accomplish"
}"""


async def generate_transformation_plan(
    provider: AIProvider,
    profile: dict,
    quality_report: dict,
    column_profiles: list[dict],
) -> dict:
    """
    Call the AI to generate a transformation plan.
    Validates all operations against the allowlist.
    Returns validated plan dict.
    """
    # Build compact context (NEVER send full dataset to AI)
    context = _build_compact_context(profile, quality_report, column_profiles)

    messages = [
        AIMessage("system", SYSTEM_PROMPT),
        AIMessage("user", f"Analyze this dataset and create a transformation plan:\n\n{context}"),
    ]

    response = await provider.complete_json(messages, temperature=0.1, max_tokens=4096)

    try:
        plan = json.loads(response.content)
    except json.JSONDecodeError as e:
        # Try to extract JSON from the response
        json_match = re.search(r"\{.*\}", response.content, re.DOTALL)
        if json_match:
            plan = json.loads(json_match.group())
        else:
            raise AIError(f"AI returned invalid JSON: {e}")

    # Validate and sanitize operations. Never trust model-generated parameters.
    valid_columns = {str(c.get("column_name")) for c in column_profiles}
    validated_operations = []
    for op in plan.get("operations", []):
        if not isinstance(op, dict):
            continue
        op_type = str(op.get("type", "")).strip().lower()
        if op_type not in ALLOWED_OPERATIONS:
            logger.warning("rejected_operation", type=op_type, reason="not in allowlist")
            continue

        column = op.get("column")
        row_level = {"remove_duplicates", "drop_nulls"}
        if op_type not in row_level:
            if not isinstance(column, str) or column not in valid_columns:
                logger.warning("rejected_operation", type=op_type, reason="unknown_column", column=column)
                continue

        try:
            confidence = float(op.get("confidence", 0.8))
        except (TypeError, ValueError):
            confidence = 0.8
        confidence = max(0.0, min(1.0, confidence))

        params = op.get("parameters")
        if not isinstance(params, dict):
            params = {}

        if op_type == "fill_null":
            strategy = str(params.get("strategy", "empty_string")).lower()
            if strategy not in {"mean", "median", "mode", "empty_string"} and "fill_value" not in params:
                strategy = "empty_string"
            params = {**params, "strategy": strategy}
        elif op_type == "clip_numeric":
            if params.get("min") is None and params.get("max") is None:
                logger.warning("rejected_operation", type=op_type, reason="missing_bounds")
                continue
        elif op_type == "rename_column":
            new_name = str(params.get("new_name", "")).strip()
            if not new_name or new_name in valid_columns or len(new_name) > 255:
                logger.warning("rejected_operation", type=op_type, reason="invalid_new_name")
                continue
            params = {**params, "new_name": new_name}
        elif op_type in {"flag_duplicates", "flag_outliers"}:
            flag = str(params.get("flag_column", "")).strip()
            if flag and (flag in valid_columns or len(flag) > 255):
                logger.warning("rejected_operation", type=op_type, reason="invalid_flag_column")
                continue
        elif op_type in {"replace_value", "regex_replace"}:
            if "old_value" not in params and "pattern" not in params:
                logger.warning("rejected_operation", type=op_type, reason="missing_replacement_target")
                continue

        validated_operations.append({
            "type": op_type,
            "column": column,
            "confidence": confidence,
            "reason": str(op.get("reason", ""))[:2000],
            "parameters": params,
        })
    plan["operations"] = validated_operations
    plan["total_operations"] = len(validated_operations)
    plan["model"] = response.model
    plan["provider"] = response.provider
    plan["input_tokens"] = response.input_tokens
    plan["output_tokens"] = response.output_tokens
    plan["latency_ms"] = response.latency_ms

    logger.info(
        "transformation_plan_generated",
        operations=len(validated_operations),
        model=response.model,
        input_tokens=response.input_tokens,
    )

    return plan


def _build_compact_context(profile: dict, quality_report: dict, column_profiles: list[dict]) -> str:
    """Build a compact, token-efficient context for the AI."""
    col_summaries = []
    for col in column_profiles[:50]:  # cap at 50 columns
        summary = {
            "name": col["column_name"],
            "type": col["semantic_type"],
            "null_pct": col.get("null_pct") or 0,
            "unique_pct": col.get("uniqueness_pct") or 0,
            "is_constant": col.get("is_constant", False),
            "samples": (col.get("sample_values") or [])[:5],
            "date_formats": col.get("date_formats") or [],
        }
        col_summaries.append(summary)

    issues_summary = [
        {
            "type": issue["issue_type"],
            "severity": issue["severity"],
            "column": issue.get("affected_column"),
            "title": issue["title"],
        }
        for issue in (quality_report.get("issues") or [])[:30]
    ]

    context = {
        "dataset_overview": {
            "rows": profile.get("row_count"),
            "columns": profile.get("column_count"),
            "duplicate_rows": profile.get("duplicate_row_count"),
            "duplicate_pct": profile.get("duplicate_row_pct"),
            "total_null_pct": profile.get("total_null_pct"),
        },
        "quality_scores": {
            "overall": quality_report.get("overall_score"),
            "completeness": quality_report.get("completeness_score"),
            "validity": quality_report.get("validity_score"),
            "consistency": quality_report.get("consistency_score"),
            "uniqueness": quality_report.get("uniqueness_score"),
        },
        "columns": col_summaries,
        "detected_issues": issues_summary,
    }

    return json.dumps(context, indent=2)
