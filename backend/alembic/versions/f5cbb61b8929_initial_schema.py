"""initial_schema

Revision ID: f5cbb61b8929
Revises:
Create Date: 2026-10-07 23:59:57.430393
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'f5cbb61b8929'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Enums defined in db/schema.sql
user_status_enum = sa.Enum(
    'active', 'inactive', 'suspended', 'pending_verification',
    name='user_status'
)
membership_role_enum = sa.Enum(
    'owner', 'admin', 'editor', 'viewer',
    name='membership_role'
)
dataset_status_enum = sa.Enum(
    'uploading', 'uploaded', 'processing', 'profiled', 'analyzed', 'transformed', 'failed', 'archived',
    name='dataset_status'
)
job_status_enum = sa.Enum(
    'queued', 'processing', 'profiling', 'ai_analysis', 'transformation', 'validation', 'completed', 'failed', 'cancelled',
    name='job_status'
)
job_type_enum = sa.Enum(
    'profile', 'quality_analysis', 'ai_analysis', 'transformation', 'validation', 'export',
    name='job_type'
)
column_semantic_type_enum = sa.Enum(
    'string', 'integer', 'float', 'boolean', 'date', 'datetime', 'timestamp',
    'email', 'phone', 'currency', 'url', 'id_like', 'categorical',
    'text', 'json', 'array', 'unknown',
    name='column_semantic_type'
)
issue_severity_enum = sa.Enum(
    'critical', 'high', 'medium', 'low', 'info',
    name='issue_severity'
)
issue_type_enum = sa.Enum(
    'missing_values', 'invalid_type', 'invalid_format', 'inconsistent_format',
    'inconsistent_capitalization', 'whitespace', 'duplicate_rows', 'duplicate_values',
    'outlier', 'impossible_value', 'malformed_email', 'malformed_phone',
    'currency_inconsistency', 'date_format_inconsistency', 'category_inconsistency',
    'schema_inconsistency', 'constant_column', 'high_cardinality', 'suspicious_pattern',
    name='issue_type'
)
transformation_op_type_enum = sa.Enum(
    'trim_whitespace', 'normalize_whitespace', 'lowercase', 'uppercase', 'title_case',
    'standardize_date', 'standardize_datetime', 'coerce_numeric', 'coerce_boolean',
    'normalize_currency', 'normalize_phone', 'normalize_email', 'normalize_category',
    'fill_null', 'drop_nulls', 'remove_duplicates', 'flag_duplicates',
    'flag_outliers', 'replace_value', 'regex_replace', 'clip_numeric',
    'drop_column', 'rename_column', 'reorder_columns', 'cast_type',
    name='transformation_op_type'
)
transformation_status_enum = sa.Enum(
    'planned', 'previewed', 'approved', 'rejected', 'running', 'completed', 'failed',
    name='transformation_status'
)
ai_provider_enum = sa.Enum(
    'groq', 'openai', 'gemini', 'anthropic', 'local',
    name='ai_provider'
)
export_format_enum = sa.Enum(
    'csv', 'parquet', 'json', 'xlsx',
    name='export_format'
)
audit_action_enum = sa.Enum(
    'create', 'read', 'update', 'delete', 'upload', 'download', 'export',
    'transform', 'approve', 'reject', 'login', 'logout', 'signup',
    name='audit_action'
)
db_recommendation_enum = sa.Enum(
    'postgresql', 'mysql', 'mongodb', 'cassandra', 'redis', 'elasticsearch',
    'bigquery', 'snowflake', 'duckdb', 'sqlite', 'dynamodb',
    name='db_recommendation'
)

ALL_ENUMS = [
    user_status_enum,
    membership_role_enum,
    dataset_status_enum,
    job_status_enum,
    job_type_enum,
    column_semantic_type_enum,
    issue_severity_enum,
    issue_type_enum,
    transformation_op_type_enum,
    transformation_status_enum,
    ai_provider_enum,
    export_format_enum,
    audit_action_enum,
    db_recommendation_enum,
]

TRIGGER_TABLES = [
    ('users', 'update_users_updated_at'),
    ('organizations', 'update_organizations_updated_at'),
    ('projects', 'update_projects_updated_at'),
    ('data_sources', 'update_data_sources_updated_at'),
    ('transformation_plans', 'update_transformation_plans_updated_at'),
    ('dashboards', 'update_dashboards_updated_at'),
    ('ai_conversations', 'update_ai_conversations_updated_at'),
    ('jobs', 'update_jobs_updated_at'),
]


def upgrade() -> None:
    # ── Extensions ────────────────────────────────────────────────────────────
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "btree_gin"')

    # ── Standalone Enums ──────────────────────────────────────────────────────
    transformation_op_type_enum.create(op.get_bind(), checkfirst=True)

    # ── 1. Users ─────────────────────────────────────────────────────────────
    op.create_table(
        'users',
        sa.Column('id', sa.UUID(), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('email', sa.String(length=320), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('full_name', sa.String(length=200), nullable=True),
        sa.Column('password_hash', sa.Text(), nullable=False),
        sa.Column('status', user_status_enum, server_default='active', nullable=False),
        sa.Column('avatar_url', sa.Text(), nullable=True),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('username'),
    )
    op.create_index('idx_users_email', 'users', ['email'], unique=False)
    op.create_index('idx_users_username', 'users', ['username'], unique=False)

    # ── 2. Organizations ─────────────────────────────────────────────────────
    op.create_table(
        'organizations',
        sa.Column('id', sa.UUID(), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('plan', sa.String(length=50), server_default='free', nullable=False),
        sa.Column('owner_id', sa.UUID(), nullable=False),
        sa.Column('settings', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug'),
    )
    op.create_index('idx_organizations_slug', 'organizations', ['slug'], unique=False)
    op.create_index('idx_organizations_owner', 'organizations', ['owner_id'], unique=False)

    # ── 3. Memberships ───────────────────────────────────────────────────────
    op.create_table(
        'memberships',
        sa.Column('id', sa.UUID(), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('role', membership_role_enum, server_default='viewer', nullable=False),
        sa.Column('invited_by', sa.UUID(), nullable=True),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['invited_by'], ['users.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'user_id'),
    )
    op.create_index('idx_memberships_org', 'memberships', ['organization_id'], unique=False)
    op.create_index('idx_memberships_user', 'memberships', ['user_id'], unique=False)

    # ── 4. API Keys ──────────────────────────────────────────────────────────
    op.create_table(
        'api_keys',
        sa.Column('id', sa.UUID(), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('key_hash', sa.Text(), nullable=False),
        sa.Column('key_prefix', sa.String(length=10), nullable=False),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key_hash'),
    )

    # ── 5. Projects ──────────────────────────────────────────────────────────
    op.create_table(
        'projects',
        sa.Column('id', sa.UUID(), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('color', sa.String(length=7), server_default='#6366f1', nullable=True),
        sa.Column('tags', sa.ARRAY(sa.Text()), server_default=sa.text("'{}'::text[]"), nullable=True),
        sa.Column('settings', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_projects_org', 'projects', ['organization_id'], unique=False)
    op.create_index('idx_projects_created_by', 'projects', ['created_by'], unique=False)

    # ── 6. Data Sources ──────────────────────────────────────────────────────
    op.create_table(
        'data_sources',
        sa.Column('id', sa.UUID(), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=300), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('original_filename', sa.String(length=500), nullable=False),
        sa.Column('file_format', sa.String(length=20), nullable=False),
        sa.Column('status', dataset_status_enum, server_default='uploading', nullable=False),
        sa.Column('current_version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('tags', sa.ARRAY(sa.Text()), server_default=sa.text("'{}'::text[]"), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_data_sources_org', 'data_sources', ['organization_id'], unique=False)
    op.create_index('idx_data_sources_project', 'data_sources', ['project_id'], unique=False)

    # ── 7. Dataset Versions ──────────────────────────────────────────────────
    op.create_table(
        'dataset_versions',
        sa.Column('id', sa.UUID(), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('data_source_id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('version_label', sa.String(length=100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('storage_key', sa.Text(), nullable=False),
        sa.Column('storage_bucket', sa.Text(), nullable=False),
        sa.Column('file_format', sa.String(length=20), nullable=False),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('row_count', sa.Integer(), nullable=True),
        sa.Column('column_count', sa.Integer(), nullable=True),
        sa.Column('checksum', sa.Text(), nullable=True),
        sa.Column('parent_version_id', sa.UUID(), nullable=True),
        sa.Column('transformation_run_id', sa.UUID(), nullable=True),
        sa.Column('quality_score', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('quality_delta', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['data_source_id'], ['data_sources.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_version_id'], ['dataset_versions.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('data_source_id', 'version_number'),
    )
    op.create_index('idx_dataset_versions_source', 'dataset_versions', ['data_source_id'], unique=False)
    op.create_index('idx_dataset_versions_org', 'dataset_versions', ['organization_id'], unique=False)

    # ── 8. Data Profiles ─────────────────────────────────────────────────────
    op.create_table(
        'data_profiles',
        sa.Column('id', sa.UUID(), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('dataset_version_id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('row_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('column_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('duplicate_row_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('duplicate_row_pct', sa.Numeric(precision=6, scale=3), nullable=True),
        sa.Column('total_null_count', sa.BigInteger(), server_default='0', nullable=False),
        sa.Column('total_null_pct', sa.Numeric(precision=6, scale=3), nullable=True),
        sa.Column('total_cell_count', sa.BigInteger(), server_default='0', nullable=False),
        sa.Column('encoding', sa.String(length=50), nullable=True),
        sa.Column('delimiter', sa.String(length=10), nullable=True),
        sa.Column('has_header', sa.Boolean(), server_default=sa.text('true'), nullable=True),
        sa.Column('sample_rows', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('profiled_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('profiling_duration_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['dataset_version_id'], ['dataset_versions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_data_profiles_version', 'data_profiles', ['dataset_version_id'], unique=False)

    # ── 9. Column Profiles ───────────────────────────────────────────────────
    op.create_table(
        'column_profiles',
        sa.Column('id', sa.UUID(), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('data_profile_id', sa.UUID(), nullable=False),
        sa.Column('dataset_version_id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('column_index', sa.Integer(), nullable=False),
        sa.Column('column_name', sa.String(length=300), nullable=False),
        sa.Column('inferred_type', sa.String(length=50), nullable=True),
        sa.Column('semantic_type', column_semantic_type_enum, server_default='unknown', nullable=False),
        sa.Column('ai_semantic_type', sa.String(length=100), nullable=True),
        sa.Column('ai_semantic_reason', sa.Text(), nullable=True),
        sa.Column('null_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('null_pct', sa.Numeric(precision=6, scale=3), nullable=True),
        sa.Column('non_null_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('unique_count', sa.Integer(), nullable=True),
        sa.Column('uniqueness_pct', sa.Numeric(precision=6, scale=3), nullable=True),
        sa.Column('is_constant', sa.Boolean(), server_default=sa.text('false'), nullable=True),
        sa.Column('is_unique', sa.Boolean(), server_default=sa.text('false'), nullable=True),
        sa.Column('numeric_min', sa.Numeric(), nullable=True),
        sa.Column('numeric_max', sa.Numeric(), nullable=True),
        sa.Column('numeric_mean', sa.Numeric(), nullable=True),
        sa.Column('numeric_median', sa.Numeric(), nullable=True),
        sa.Column('numeric_std_dev', sa.Numeric(), nullable=True),
        sa.Column('numeric_q1', sa.Numeric(), nullable=True),
        sa.Column('numeric_q3', sa.Numeric(), nullable=True),
        sa.Column('numeric_skewness', sa.Numeric(), nullable=True),
        sa.Column('string_min_length', sa.Integer(), nullable=True),
        sa.Column('string_max_length', sa.Integer(), nullable=True),
        sa.Column('string_avg_length', sa.Numeric(), nullable=True),
        sa.Column('date_min', sa.Text(), nullable=True),
        sa.Column('date_max', sa.Text(), nullable=True),
        sa.Column('date_formats', sa.ARRAY(sa.Text()), nullable=True),
        sa.Column('value_frequency', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('sample_values', sa.ARRAY(sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['data_profile_id'], ['data_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['dataset_version_id'], ['dataset_versions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_column_profiles_profile', 'column_profiles', ['data_profile_id'], unique=False)
    op.create_index('idx_column_profiles_version', 'column_profiles', ['dataset_version_id'], unique=False)

    # ── 10. Quality Reports ──────────────────────────────────────────────────
    op.create_table(
        'quality_reports',
        sa.Column('id', sa.UUID(), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('dataset_version_id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('overall_score', sa.Numeric(precision=5, scale=2), server_default='0', nullable=False),
        sa.Column('completeness_score', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('validity_score', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('consistency_score', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('uniqueness_score', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('integrity_score', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('completeness_weight', sa.Numeric(precision=4, scale=2), server_default='0.25', nullable=True),
        sa.Column('validity_weight', sa.Numeric(precision=4, scale=2), server_default='0.25', nullable=True),
        sa.Column('consistency_weight', sa.Numeric(precision=4, scale=2), server_default='0.20', nullable=True),
        sa.Column('uniqueness_weight', sa.Numeric(precision=4, scale=2), server_default='0.15', nullable=True),
        sa.Column('integrity_weight', sa.Numeric(precision=4, scale=2), server_default='0.15', nullable=True),
        sa.Column('total_issues', sa.Integer(), server_default='0', nullable=False),
        sa.Column('critical_issues', sa.Integer(), server_default='0', nullable=False),
        sa.Column('high_issues', sa.Integer(), server_default='0', nullable=False),
        sa.Column('medium_issues', sa.Integer(), server_default='0', nullable=False),
        sa.Column('low_issues', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['dataset_version_id'], ['dataset_versions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_quality_reports_version', 'quality_reports', ['dataset_version_id'], unique=False)

    # ── 11. Quality Issues ───────────────────────────────────────────────────
    op.create_table(
        'quality_issues',
        sa.Column('id', sa.UUID(), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('quality_report_id', sa.UUID(), nullable=False),
        sa.Column('dataset_version_id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('issue_type', issue_type_enum, nullable=False),
        sa.Column('severity', issue_severity_enum, nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('affected_column', sa.String(length=300), nullable=True),
        sa.Column('affected_row_count', sa.Integer(), nullable=True),
        sa.Column('affected_row_pct', sa.Numeric(precision=6, scale=3), nullable=True),
        sa.Column('evidence', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('suggested_fix', sa.Text(), nullable=True),
        sa.Column('auto_fixable', sa.Boolean(), server_default=sa.text('false'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['dataset_version_id'], ['dataset_versions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['quality_report_id'], ['quality_reports.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_quality_issues_report', 'quality_issues', ['quality_report_id'], unique=False)
    op.create_index('idx_quality_issues_column', 'quality_issues', ['affected_column'], unique=False)

    # ── 12. AI Analyses ──────────────────────────────────────────────────────
    op.create_table(
        'ai_analyses',
        sa.Column('id', sa.UUID(), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('dataset_version_id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('provider', ai_provider_enum, server_default='groq', nullable=False),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('prompt_version', sa.String(length=20), server_default='1.0', nullable=False),
        sa.Column('dataset_summary', sa.Text(), nullable=True),
        sa.Column('detected_domain', sa.String(length=100), nullable=True),
        sa.Column('entity_types', sa.ARRAY(sa.Text()), nullable=True),
        sa.Column('key_relationships', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('column_semantics', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('issue_interpretations', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('input_tokens', sa.Integer(), nullable=True),
        sa.Column('output_tokens', sa.Integer(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['dataset_version_id'], ['dataset_versions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── 13. Transformation Plans ─────────────────────────────────────────────
    op.create_table(
        'transformation_plans',
        sa.Column('id', sa.UUID(), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('dataset_version_id', sa.UUID(), nullable=False),
        sa.Column('ai_analysis_id', sa.UUID(), nullable=True),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('plan_version', sa.String(length=20), server_default='1.0', nullable=False),
        sa.Column('status', transformation_status_enum, server_default='planned', nullable=False),
        sa.Column('operations', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column('total_operations', sa.Integer(), server_default='0', nullable=False),
        sa.Column('estimated_quality_gain', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('approved_by', sa.UUID(), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejected_by', sa.UUID(), nullable=True),
        sa.Column('rejected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['ai_analysis_id'], ['ai_analyses.id']),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['dataset_version_id'], ['dataset_versions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['rejected_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_transformation_plans_version', 'transformation_plans', ['dataset_version_id'], unique=False)

    # ── 14. Transformation Runs ─────────────────────────────────────────────
    op.create_table(
        'transformation_runs',
        sa.Column('id', sa.UUID(), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('transformation_plan_id', sa.UUID(), nullable=False),
        sa.Column('dataset_version_id', sa.UUID(), nullable=False),
        sa.Column('output_version_id', sa.UUID(), nullable=True),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('executed_by', sa.UUID(), nullable=False),
        sa.Column('status', transformation_status_enum, server_default='running', nullable=False),
        sa.Column('operations_total', sa.Integer(), server_default='0', nullable=False),
        sa.Column('operations_applied', sa.Integer(), server_default='0', nullable=False),
        sa.Column('operations_skipped', sa.Integer(), server_default='0', nullable=False),
        sa.Column('operations_failed', sa.Integer(), server_default='0', nullable=False),
        sa.Column('rows_modified', sa.Integer(), nullable=True),
        sa.Column('quality_before', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('quality_after', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('quality_delta', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('execution_log', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['dataset_version_id'], ['dataset_versions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['executed_by'], ['users.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['output_version_id'], ['dataset_versions.id']),
        sa.ForeignKeyConstraint(['transformation_plan_id'], ['transformation_plans.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_transformation_runs_plan', 'transformation_runs', ['transformation_plan_id'], unique=False)
    op.create_index('idx_transformation_runs_org', 'transformation_runs', ['organization_id'], unique=False)

    # ── 15. Schema Analyses ──────────────────────────────────────────────────
    op.create_table(
        'schema_analyses',
        sa.Column('id', sa.UUID(), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('dataset_version_id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('detected_entities', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=True),
        sa.Column('pk_candidates', sa.ARRAY(sa.Text()), nullable=True),
        sa.Column('fk_candidates', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=True),
        sa.Column('suggested_schema', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('normalization_form', sa.String(length=10), nullable=True),
        sa.Column('recommended_db', db_recommendation_enum, nullable=True),
        sa.Column('db_confidence', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('db_reasoning', sa.Text(), nullable=True),
        sa.Column('db_tradeoffs', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('db_scores', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['dataset_version_id'], ['dataset_versions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── 16. Analytics Queries ────────────────────────────────────────────────
    op.create_table(
        'analytics_queries',
        sa.Column('id', sa.UUID(), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('dataset_version_id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('natural_language', sa.Text(), nullable=False),
        sa.Column('generated_sql', sa.Text(), nullable=True),
        sa.Column('validated_sql', sa.Text(), nullable=True),
        sa.Column('result_rows', sa.Integer(), nullable=True),
        sa.Column('result_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('chart_type', sa.String(length=50), nullable=True),
        sa.Column('chart_config', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_safe', sa.Boolean(), server_default=sa.text('false'), nullable=True),
        sa.Column('execution_ms', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('provider', ai_provider_enum, server_default='groq', nullable=True),
        sa.Column('model', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['dataset_version_id'], ['dataset_versions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_analytics_queries_version', 'analytics_queries', ['dataset_version_id'], unique=False)
    op.create_index('idx_analytics_queries_org', 'analytics_queries', ['organization_id'], unique=False)

    # ── 17. Dashboards ───────────────────────────────────────────────────────
    op.create_table(
        'dashboards',
        sa.Column('id', sa.UUID(), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('layout', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=True),
        sa.Column('widgets', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=True),
        sa.Column('is_public', sa.Boolean(), server_default=sa.text('false'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── 18. AI Conversations ─────────────────────────────────────────────────
    op.create_table(
        'ai_conversations',
        sa.Column('id', sa.UUID(), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('dataset_version_id', sa.UUID(), nullable=True),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(length=300), nullable=True),
        sa.Column('context', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['dataset_version_id'], ['dataset_versions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── 19. AI Messages ─────────────────────────────────────────────────────
    op.create_table(
        'ai_messages',
        sa.Column('id', sa.UUID(), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('conversation_id', sa.UUID(), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column('generated_sql', sa.Text(), nullable=True),
        sa.Column('result_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('chart_config', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('input_tokens', sa.Integer(), nullable=True),
        sa.Column('output_tokens', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['ai_conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_ai_messages_conversation', 'ai_messages', ['conversation_id'], unique=False)

    # ── 20. Jobs ─────────────────────────────────────────────────────────────
    op.create_table(
        'jobs',
        sa.Column('id', sa.UUID(), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('job_type', job_type_enum, nullable=False),
        sa.Column('status', job_status_enum, server_default='queued', nullable=False),
        sa.Column('data_source_id', sa.UUID(), nullable=True),
        sa.Column('dataset_version_id', sa.UUID(), nullable=True),
        sa.Column('transformation_plan_id', sa.UUID(), nullable=True),
        sa.Column('priority', sa.Integer(), server_default='5', nullable=False),
        sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
        sa.Column('max_attempts', sa.Integer(), server_default='3', nullable=False),
        sa.Column('progress_pct', sa.Integer(), server_default='0', nullable=True),
        sa.Column('progress_message', sa.Text(), nullable=True),
        sa.Column('result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_traceback', sa.Text(), nullable=True),
        sa.Column('queued_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['data_source_id'], ['data_sources.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['dataset_version_id'], ['dataset_versions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['transformation_plan_id'], ['transformation_plans.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_jobs_org', 'jobs', ['organization_id'], unique=False)
    op.create_index('idx_jobs_status', 'jobs', ['status'], unique=False)
    op.create_index('idx_jobs_data_source', 'jobs', ['data_source_id'], unique=False)

    # ── 21. Job Logs ─────────────────────────────────────────────────────────
    op.create_table(
        'job_logs',
        sa.Column('id', sa.UUID(), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('job_id', sa.UUID(), nullable=False),
        sa.Column('level', sa.String(length=10), server_default='INFO', nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_job_logs_job', 'job_logs', ['job_id'], unique=False)

    # ── 22. Exports ──────────────────────────────────────────────────────────
    op.create_table(
        'exports',
        sa.Column('id', sa.UUID(), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('dataset_version_id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('format', export_format_enum, nullable=False),
        sa.Column('storage_key', sa.Text(), nullable=False),
        sa.Column('storage_bucket', sa.Text(), nullable=False),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('download_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['dataset_version_id'], ['dataset_versions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── 23. Audit Logs ───────────────────────────────────────────────────────
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.UUID(), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=True),
        sa.Column('user_id', sa.UUID(), nullable=True),
        sa.Column('action', audit_action_enum, nullable=False),
        sa.Column('resource_type', sa.String(length=100), nullable=True),
        sa.Column('resource_id', sa.UUID(), nullable=True),
        sa.Column('ip_address', postgresql.INET(), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_audit_logs_org', 'audit_logs', ['organization_id'], unique=False)
    op.create_index('idx_audit_logs_user', 'audit_logs', ['user_id'], unique=False)
    op.create_index('idx_audit_logs_created', 'audit_logs', ['created_at'], unique=False)

    # ── 24. Usage Records ────────────────────────────────────────────────────
    op.create_table(
        'usage_records',
        sa.Column('id', sa.UUID(), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=True),
        sa.Column('metric', sa.String(length=100), nullable=False),
        sa.Column('value', sa.BigInteger(), server_default='0', nullable=False),
        sa.Column('period', sa.Date(), server_default=sa.text('CURRENT_DATE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'metric', 'period'),
    )

    # ── Triggers & Functions ─────────────────────────────────────────────────
    op.execute("""
    CREATE OR REPLACE FUNCTION update_updated_at_column()
    RETURNS TRIGGER AS $$
    BEGIN
      NEW.updated_at = NOW();
      RETURN NEW;
    END;
    $$ language 'plpgsql';
    """)

    for table, trigger in TRIGGER_TABLES:
        op.execute(f"""
        CREATE TRIGGER {trigger} BEFORE UPDATE ON {table}
          FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """)


def downgrade() -> None:
    # Drop triggers and helper function
    for table, trigger in reversed(TRIGGER_TABLES):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger} ON {table};")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column();")

    # Drop tables in reverse dependency order
    op.drop_table('usage_records')
    op.drop_table('audit_logs')
    op.drop_table('exports')
    op.drop_table('job_logs')
    op.drop_table('jobs')
    op.drop_table('ai_messages')
    op.drop_table('ai_conversations')
    op.drop_table('dashboards')
    op.drop_table('analytics_queries')
    op.drop_table('schema_analyses')
    op.drop_table('transformation_runs')
    op.drop_table('transformation_plans')
    op.drop_table('ai_analyses')
    op.drop_table('quality_issues')
    op.drop_table('quality_reports')
    op.drop_table('column_profiles')
    op.drop_table('data_profiles')
    op.drop_table('dataset_versions')
    op.drop_table('data_sources')
    op.drop_table('projects')
    op.drop_table('api_keys')
    op.drop_table('memberships')
    op.drop_table('organizations')
    op.drop_table('users')

    # Drop enums
    for enum_type in reversed(ALL_ENUMS):
        enum_type.drop(op.get_bind(), checkfirst=True)

    # Drop extensions
    op.execute('DROP EXTENSION IF EXISTS "btree_gin"')
    op.execute('DROP EXTENSION IF EXISTS "pg_trgm"')
    op.execute('DROP EXTENSION IF EXISTS "uuid-ossp"')
