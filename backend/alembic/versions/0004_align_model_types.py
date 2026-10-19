"""Align legacy schema.sql enum columns with SQLAlchemy string columns."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0004_align_model_types"
down_revision = "0003_email_recovery"
branch_labels = None
depends_on = None

# The ORM intentionally stores these workflow labels as VARCHAR. Older installs
# initialized from db/schema.sql used PostgreSQL ENUMs, which reject comparisons
# and values not represented in those older enum definitions.
_COLUMNS = {
    ("data_sources", "status"): ("dataset_status", "VARCHAR(50)"),
    ("column_profiles", "semantic_type"): ("column_semantic_type", "VARCHAR(50)"),
    ("quality_issues", "issue_type"): ("issue_type", "VARCHAR(100)"),
    ("quality_issues", "severity"): ("issue_severity", "VARCHAR(20)"),
    ("jobs", "job_type"): ("job_type", "VARCHAR(50)"),
    ("jobs", "status"): ("job_status", "VARCHAR(50)"),
    ("transformation_plans", "status"): ("transformation_status", "VARCHAR(50)"),
    ("transformation_runs", "status"): ("transformation_status", "VARCHAR(50)"),
}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    for (table, column), (legacy_enum, target_type) in _COLUMNS.items():
        if table not in tables:
            continue
        metadata = {item["name"]: item for item in inspector.get_columns(table)}
        if column not in metadata:
            continue
        current_type = metadata[column]["type"]
        if getattr(current_type, "name", None) == legacy_enum:
            op.execute(
                sa.text(
                    f'ALTER TABLE "{table}" ALTER COLUMN "{column}" '
                    f'TYPE {target_type} USING "{column}"::text'
                )
            )


def downgrade() -> None:
    # Converting free-form VARCHAR values back to ENUMs can lose data and fail
    # for labels introduced after the original schema, so this migration is safe
    # to roll forward only.
    raise RuntimeError("Schema type alignment cannot be safely downgraded.")
