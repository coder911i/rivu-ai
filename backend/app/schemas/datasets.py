"""Pydantic schemas for projects and datasets."""

from datetime import datetime
from typing import Optional, List, Any
from uuid import UUID
from pydantic import BaseModel, field_validator


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    color: str = "#6366f1"
    tags: List[str] = []

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Project name cannot be empty")
        if len(v) > 200:
            raise ValueError("Project name too long")
        return v


class ProjectResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    description: Optional[str]
    color: str
    tags: List[str]
    created_at: str
    updated_at: str
    dataset_count: int = 0
    avg_quality_score: Optional[float] = None

    model_config = {"from_attributes": True}


class DataSourceResponse(BaseModel):
    id: str
    project_id: str
    name: str
    description: Optional[str]
    original_filename: str
    file_format: str
    status: str
    current_version: int
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class DatasetVersionResponse(BaseModel):
    id: str
    data_source_id: str
    version_number: int
    version_label: Optional[str]
    file_format: str
    file_size_bytes: Optional[int]
    row_count: Optional[int]
    column_count: Optional[int]
    quality_score: Optional[float]
    quality_delta: Optional[float]
    created_at: str

    model_config = {"from_attributes": True}


class JobResponse(BaseModel):
    id: str
    job_type: str
    status: str
    progress_pct: Optional[int]
    progress_message: Optional[str]
    error_message: Optional[str]
    result: Optional[Any]
    queued_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    duration_ms: Optional[int]

    model_config = {"from_attributes": True}


class ColumnProfileResponse(BaseModel):
    column_index: int
    column_name: str
    inferred_type: Optional[str]
    semantic_type: str
    null_count: int
    null_pct: Optional[float]
    non_null_count: int
    unique_count: Optional[int]
    uniqueness_pct: Optional[float]
    is_constant: bool
    is_unique: bool
    numeric_min: Optional[float]
    numeric_max: Optional[float]
    numeric_mean: Optional[float]
    numeric_median: Optional[float]
    numeric_std_dev: Optional[float]
    numeric_q1: Optional[float]
    numeric_q3: Optional[float]
    string_min_length: Optional[int]
    string_max_length: Optional[int]
    value_frequency: Optional[dict]
    sample_values: Optional[list]
    date_formats: Optional[list]

    model_config = {"from_attributes": True}


class DataProfileResponse(BaseModel):
    id: str
    dataset_version_id: str
    row_count: int
    column_count: int
    duplicate_row_count: int
    duplicate_row_pct: Optional[float]
    total_null_count: int
    total_null_pct: Optional[float]
    total_cell_count: int
    encoding: Optional[str]
    sample_rows: Optional[list]
    profiled_at: str
    profiling_duration_ms: Optional[int]
    columns: List[ColumnProfileResponse] = []

    model_config = {"from_attributes": True}


class QualityIssueResponse(BaseModel):
    id: str
    issue_type: str
    severity: str
    title: str
    description: Optional[str]
    affected_column: Optional[str]
    affected_row_count: Optional[int]
    affected_row_pct: Optional[float]
    evidence: Optional[dict]
    suggested_fix: Optional[str]
    auto_fixable: bool

    model_config = {"from_attributes": True}


class QualityReportResponse(BaseModel):
    id: str
    dataset_version_id: str
    overall_score: float
    completeness_score: Optional[float]
    validity_score: Optional[float]
    consistency_score: Optional[float]
    uniqueness_score: Optional[float]
    integrity_score: Optional[float]
    total_issues: int
    critical_issues: int
    high_issues: int
    medium_issues: int
    low_issues: int
    issues: List[QualityIssueResponse] = []

    model_config = {"from_attributes": True}


class TransformationOperationResponse(BaseModel):
    type: str
    column: Optional[str]
    confidence: float
    reason: str
    parameters: Optional[dict] = None
    preview_before: Optional[list] = None
    preview_after: Optional[list] = None


class TransformationPlanResponse(BaseModel):
    id: str
    dataset_version_id: str
    status: str
    total_operations: int
    estimated_quality_gain: Optional[float]
    operations: List[TransformationOperationResponse]
    created_at: str

    model_config = {"from_attributes": True}
