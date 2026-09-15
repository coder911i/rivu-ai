"""
Data Quality Engine — calculates quality scores and detects issues.

Dimensions:
  - Completeness (25%): null values, missing data
  - Validity (25%): format violations, type errors
  - Consistency (20%): inconsistent formats, capitalization, categories
  - Uniqueness (15%): duplicate rows, duplicate values in ID columns
  - Integrity (15%): impossible values, referential anomalies
"""

import re
from typing import Any
import structlog

logger = structlog.get_logger(__name__)

# Default weights
WEIGHTS = {
    "completeness": 0.25,
    "validity": 0.25,
    "consistency": 0.20,
    "uniqueness": 0.15,
    "integrity": 0.15,
}

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
_PHONE_RE = re.compile(r"^[\+\d][\d\s\-\.\(\)]{6,18}$")


def calculate_quality_report(profile: dict, column_profiles: list[dict]) -> dict:
    """
    Calculate a full quality report from profiling data.
    Returns dict with scores and issues list.
    """
    issues = []

    # ── COMPLETENESS ─────────────────────────────
    completeness_score = _score_completeness(profile, column_profiles, issues)

    # ── VALIDITY ──────────────────────────────────
    validity_score = _score_validity(profile, column_profiles, issues)

    # ── CONSISTENCY ───────────────────────────────
    consistency_score = _score_consistency(profile, column_profiles, issues)

    # ── UNIQUENESS ────────────────────────────────
    uniqueness_score = _score_uniqueness(profile, column_profiles, issues)

    # ── INTEGRITY ─────────────────────────────────
    integrity_score = _score_integrity(profile, column_profiles, issues)

    # ── Overall score ─────────────────────────────
    overall_score = (
        completeness_score * WEIGHTS["completeness"]
        + validity_score * WEIGHTS["validity"]
        + consistency_score * WEIGHTS["consistency"]
        + uniqueness_score * WEIGHTS["uniqueness"]
        + integrity_score * WEIGHTS["integrity"]
    )

    # Count by severity
    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for issue in issues:
        severity_counts[issue["severity"]] = severity_counts.get(issue["severity"], 0) + 1

    return {
        "overall_score": round(overall_score, 2),
        "completeness_score": round(completeness_score, 2),
        "validity_score": round(validity_score, 2),
        "consistency_score": round(consistency_score, 2),
        "uniqueness_score": round(uniqueness_score, 2),
        "integrity_score": round(integrity_score, 2),
        "total_issues": len(issues),
        "critical_issues": severity_counts["critical"],
        "high_issues": severity_counts["high"],
        "medium_issues": severity_counts["medium"],
        "low_issues": severity_counts["low"],
        "issues": issues,
    }


def _score_completeness(profile: dict, columns: list[dict], issues: list) -> float:
    """Score based on null/missing values."""
    total_null_pct = profile.get("total_null_pct") or 0

    for col in columns:
        null_pct = col.get("null_pct") or 0
        null_count = col.get("null_count", 0)
        col_name = col["column_name"]

        if null_pct > 50:
            severity = "critical" if null_pct > 80 else "high"
            issues.append({
                "issue_type": "missing_values",
                "severity": severity,
                "title": f"High missing values in '{col_name}'",
                "description": f"{null_pct:.1f}% of values are missing in column '{col_name}'",
                "affected_column": col_name,
                "affected_row_count": null_count,
                "affected_row_pct": round(null_pct, 2),
                "evidence": {"null_pct": null_pct, "null_count": null_count},
                "suggested_fix": "Consider filling missing values with mean/median/mode or flagging for manual review",
                "auto_fixable": True,
            })
        elif null_pct > 10:
            issues.append({
                "issue_type": "missing_values",
                "severity": "medium",
                "title": f"Missing values in '{col_name}'",
                "description": f"{null_pct:.1f}% of values are missing in column '{col_name}'",
                "affected_column": col_name,
                "affected_row_count": null_count,
                "affected_row_pct": round(null_pct, 2),
                "evidence": {"null_pct": null_pct},
                "suggested_fix": "Fill nulls or drop rows depending on use case",
                "auto_fixable": True,
            })
        elif null_pct > 0:
            issues.append({
                "issue_type": "missing_values",
                "severity": "low",
                "title": f"Some missing values in '{col_name}'",
                "description": f"{null_count} missing values ({null_pct:.1f}%) in '{col_name}'",
                "affected_column": col_name,
                "affected_row_count": null_count,
                "affected_row_pct": round(null_pct, 2),
                "evidence": {"null_pct": null_pct},
                "suggested_fix": "Review and handle missing values",
                "auto_fixable": True,
            })

    # Score: 100 - proportional penalty for nulls
    score = max(0.0, 100.0 - (total_null_pct * 1.5))
    return min(100.0, score)


def _score_validity(profile: dict, columns: list[dict], issues: list) -> float:
    """Score based on format validity and type correctness."""
    penalties = 0.0

    for col in columns:
        col_name = col["column_name"]
        semantic_type = col.get("semantic_type", "unknown")
        sample_values = col.get("sample_values") or []
        non_null_count = col.get("non_null_count", 0)
        value_freq = col.get("value_frequency") or {}

        # Email validation
        if semantic_type == "email" and sample_values:
            invalid = [v for v in sample_values if v and not _EMAIL_RE.match(str(v).strip())]
            if invalid:
                inv_pct = len(invalid) / len(sample_values) * 100
                issues.append({
                    "issue_type": "malformed_email",
                    "severity": "high" if inv_pct > 30 else "medium",
                    "title": f"Malformed email addresses in '{col_name}'",
                    "description": f"Found {len(invalid)} malformed email(s) in sample",
                    "affected_column": col_name,
                    "affected_row_count": int(non_null_count * inv_pct / 100),
                    "affected_row_pct": round(inv_pct, 2),
                    "evidence": {"invalid_samples": invalid[:5]},
                    "suggested_fix": "Validate and clean email format",
                    "auto_fixable": False,
                })
                penalties += inv_pct * 0.3

        # Phone validation
        if semantic_type == "phone" and sample_values:
            invalid_phones = [v for v in sample_values if v and not _PHONE_RE.match(str(v).strip())]
            if invalid_phones:
                inv_pct = len(invalid_phones) / len(sample_values) * 100
                issues.append({
                    "issue_type": "malformed_phone",
                    "severity": "medium",
                    "title": f"Malformed phone numbers in '{col_name}'",
                    "description": f"Inconsistent phone number formats detected",
                    "affected_column": col_name,
                    "affected_row_count": int(non_null_count * inv_pct / 100),
                    "affected_row_pct": round(inv_pct, 2),
                    "evidence": {"samples": invalid_phones[:5]},
                    "suggested_fix": "Normalize phone numbers to E.164 format",
                    "auto_fixable": True,
                })
                penalties += inv_pct * 0.2

        # Constant columns
        if col.get("is_constant") and non_null_count > 0:
            issues.append({
                "issue_type": "schema_inconsistency",
                "severity": "medium",
                "title": f"Constant column '{col_name}'",
                "description": f"Column '{col_name}' has only one unique value — likely useless for analysis",
                "affected_column": col_name,
                "affected_row_count": None,
                "affected_row_pct": None,
                "evidence": {"unique_value": sample_values[0] if sample_values else None},
                "suggested_fix": "Consider dropping this column or investigating data collection",
                "auto_fixable": False,
            })
            penalties += 5

    score = max(0.0, 100.0 - penalties)
    return min(100.0, score)


def _score_consistency(profile: dict, columns: list[dict], issues: list) -> float:
    """Score based on consistency of formats, capitalization, categories."""
    penalties = 0.0

    for col in columns:
        col_name = col["column_name"]
        semantic_type = col.get("semantic_type", "unknown")
        sample_values = col.get("sample_values") or []
        date_formats = col.get("date_formats") or []

        # Multiple date formats
        if semantic_type in ("date", "datetime") and len(date_formats) > 1:
            issues.append({
                "issue_type": "date_format_inconsistency",
                "severity": "high",
                "title": f"Mixed date formats in '{col_name}'",
                "description": f"Found {len(date_formats)} different date formats: {', '.join(date_formats)}",
                "affected_column": col_name,
                "affected_row_count": None,
                "affected_row_pct": None,
                "evidence": {"formats_found": date_formats, "samples": sample_values[:5]},
                "suggested_fix": f"Standardize to ISO 8601 format (YYYY-MM-DD)",
                "auto_fixable": True,
            })
            penalties += 15

        # Inconsistent capitalization (string columns)
        if semantic_type in ("string", "categorical") and len(sample_values) >= 3:
            has_upper = any(s == s.upper() and s.isalpha() for s in sample_values)
            has_lower = any(s == s.lower() and s.isalpha() for s in sample_values)
            has_mixed = any(s.istitle() for s in sample_values)
            styles = sum([has_upper, has_lower, has_mixed])
            if styles > 1:
                issues.append({
                    "issue_type": "inconsistent_capitalization",
                    "severity": "low",
                    "title": f"Inconsistent capitalization in '{col_name}'",
                    "description": f"Mixed letter cases detected (e.g., INDIA, India, india)",
                    "affected_column": col_name,
                    "affected_row_count": None,
                    "affected_row_pct": None,
                    "evidence": {"samples": sample_values[:5]},
                    "suggested_fix": "Standardize to title case or lowercase",
                    "auto_fixable": True,
                })
                penalties += 5

        # Whitespace issues
        if semantic_type in ("string", "text", "email", "phone") and sample_values:
            has_leading = any(str(v) != str(v).strip() for v in sample_values)
            if has_leading:
                issues.append({
                    "issue_type": "whitespace",
                    "severity": "low",
                    "title": f"Leading/trailing whitespace in '{col_name}'",
                    "description": f"Values have leading or trailing whitespace",
                    "affected_column": col_name,
                    "affected_row_count": None,
                    "affected_row_pct": None,
                    "evidence": {"sample_with_space": [repr(v) for v in sample_values[:3]]},
                    "suggested_fix": "Trim whitespace from all values",
                    "auto_fixable": True,
                })
                penalties += 3

    score = max(0.0, 100.0 - penalties)
    return min(100.0, score)


def _score_uniqueness(profile: dict, columns: list[dict], issues: list) -> float:
    """Score based on duplicates."""
    penalties = 0.0

    dup_pct = profile.get("duplicate_row_pct") or 0
    dup_count = profile.get("duplicate_row_count") or 0

    if dup_pct > 0:
        severity = "critical" if dup_pct > 20 else ("high" if dup_pct > 5 else "medium")
        issues.append({
            "issue_type": "duplicate_rows",
            "severity": severity,
            "title": f"Duplicate rows detected",
            "description": f"{dup_count} duplicate rows found ({dup_pct:.2f}% of total)",
            "affected_column": None,
            "affected_row_count": dup_count,
            "affected_row_pct": round(dup_pct, 2),
            "evidence": {"duplicate_count": dup_count, "duplicate_pct": dup_pct},
            "suggested_fix": "Remove or flag duplicate rows. Review if duplicates are expected.",
            "auto_fixable": True,
        })
        penalties += dup_pct * 1.5

    # ID columns that aren't unique
    for col in columns:
        col_name = col["column_name"]
        semantic_type = col.get("semantic_type", "")
        uniqueness_pct = col.get("uniqueness_pct") or 100

        if semantic_type == "id_like" and uniqueness_pct < 100:
            issues.append({
                "issue_type": "duplicate_values",
                "severity": "high",
                "title": f"Duplicate IDs in '{col_name}'",
                "description": f"Column appears to be an identifier but has duplicates ({100-uniqueness_pct:.1f}% duplicates)",
                "affected_column": col_name,
                "affected_row_count": None,
                "affected_row_pct": round(100 - uniqueness_pct, 2),
                "evidence": {"uniqueness_pct": uniqueness_pct},
                "suggested_fix": "Investigate and deduplicate ID column",
                "auto_fixable": False,
            })
            penalties += 10

    score = max(0.0, 100.0 - penalties)
    return min(100.0, score)


def _score_integrity(profile: dict, columns: list[dict], issues: list) -> float:
    """Score based on impossible values and integrity violations."""
    penalties = 0.0

    for col in columns:
        col_name = col["column_name"]
        semantic_type = col.get("semantic_type", "")

        # Numeric outlier detection
        if semantic_type in ("integer", "float", "currency"):
            q1 = col.get("numeric_q1")
            q3 = col.get("numeric_q3")
            _min = col.get("numeric_min")
            _max = col.get("numeric_max")

            if q1 is not None and q3 is not None:
                iqr = q3 - q1
                lower_fence = q1 - 3 * iqr
                upper_fence = q3 + 3 * iqr

                if _min is not None and _min < lower_fence:
                    issues.append({
                        "issue_type": "outlier",
                        "severity": "medium",
                        "title": f"Extreme low outliers in '{col_name}'",
                        "description": f"Minimum value {_min} is far below Q1-3×IQR fence ({lower_fence:.2f})",
                        "affected_column": col_name,
                        "affected_row_count": None,
                        "affected_row_pct": None,
                        "evidence": {"min": _min, "q1": q1, "q3": q3, "lower_fence": lower_fence},
                        "suggested_fix": "Review extreme values. Cap or flag outliers.",
                        "auto_fixable": True,
                    })
                    penalties += 5

                if _max is not None and _max > upper_fence:
                    issues.append({
                        "issue_type": "outlier",
                        "severity": "medium",
                        "title": f"Extreme high outliers in '{col_name}'",
                        "description": f"Maximum value {_max} exceeds Q3+3×IQR fence ({upper_fence:.2f})",
                        "affected_column": col_name,
                        "affected_row_count": None,
                        "affected_row_pct": None,
                        "evidence": {"max": _max, "q1": q1, "q3": q3, "upper_fence": upper_fence},
                        "suggested_fix": "Review extreme values. Cap or flag outliers.",
                        "auto_fixable": True,
                    })
                    penalties += 5

    score = max(0.0, 100.0 - penalties)
    return min(100.0, score)
