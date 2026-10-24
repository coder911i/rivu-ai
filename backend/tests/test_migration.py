"""Tests for Alembic migration scripts and schema definitions."""

import contextlib
import io
import os
import re
from alembic.config import Config
from alembic import command
from app.core.database import Base
import app.models  # noqa: F401


def test_initial_migration_exists():
    """Verify that the initial migration file exists in alembic/versions."""
    migration_path = os.path.join(
        os.path.dirname(__file__), "..", "alembic", "versions", "f5cbb61b8929_initial_schema.py"
    )
    assert os.path.isfile(migration_path), "Initial migration file f5cbb61b8929_initial_schema.py not found"


def _get_alembic_config() -> Config:
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    cfg = Config(os.path.join(backend_dir, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(backend_dir, "alembic"))
    cfg.set_main_option("sqlalchemy.url", "postgresql://placeholder")
    return cfg


def _get_schema_sql_objects() -> dict:
    schema_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "db", "schema.sql")
    )
    with open(schema_path, "r", encoding="utf-8") as f:
        content = f.read()

    tables = re.findall(r"CREATE TABLE (?:IF NOT EXISTS )?([a-zA-Z_]+)", content, re.IGNORECASE)
    enums = re.findall(r"CREATE TYPE ([a-zA-Z_]+) AS ENUM", content, re.IGNORECASE)
    indexes = re.findall(
        r"CREATE (?:UNIQUE )?INDEX (?:IF NOT EXISTS )?([a-zA-Z0-9_]+)", content, re.IGNORECASE
    )
    return {
        "tables": tables,
        "enums": enums,
        "indexes": indexes,
        "content": content,
    }


def test_migration_upgrade_sql_aligns_with_schema_sql():
    """Verify that alembic upgrade --sql generates DDL matching db/schema.sql."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cfg = _get_alembic_config()
        command.upgrade(cfg, "head", sql=True)

    sql_output = buf.getvalue()
    schema_objects = _get_schema_sql_objects()

    # 1. Check all 24 tables from schema.sql are created
    assert len(schema_objects["tables"]) == 24, "schema.sql should contain 24 tables"
    for table_name in schema_objects["tables"]:
        assert f"CREATE TABLE {table_name}" in sql_output, f"Missing CREATE TABLE for {table_name}"

    # Verify all 14 Base.metadata tables are also covered
    for table_name in Base.metadata.tables.keys():
        assert f"CREATE TABLE {table_name}" in sql_output, f"Missing Base.metadata table {table_name}"

    # 2. Check all 14 enums from schema.sql are created
    assert len(schema_objects["enums"]) == 14, "schema.sql should contain 14 enums"
    for enum_name in schema_objects["enums"]:
        assert f"CREATE TYPE {enum_name}" in sql_output, f"Missing CREATE TYPE for {enum_name}"

    # 3. Check extensions
    assert "uuid-ossp" in sql_output
    assert "pg_trgm" in sql_output
    assert "btree_gin" in sql_output

    # 4. Check helper function and triggers
    assert "update_updated_at_column" in sql_output
    for trigger_name in [
        "update_users_updated_at",
        "update_organizations_updated_at",
        "update_projects_updated_at",
        "update_data_sources_updated_at",
        "update_transformation_plans_updated_at",
        "update_dashboards_updated_at",
        "update_ai_conversations_updated_at",
        "update_jobs_updated_at",
    ]:
        assert trigger_name in sql_output, f"Missing trigger {trigger_name}"

    # 5. Check key indexes
    for idx in schema_objects["indexes"]:
        assert idx in sql_output, f"Missing index {idx}"


def test_migration_downgrade_sql_drops_all_schema_objects():
    """Verify that alembic downgrade --sql generates DROP statements for all schema objects."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cfg = _get_alembic_config()
        command.downgrade(cfg, "f5cbb61b8929:base", sql=True)

    sql_output = buf.getvalue()
    schema_objects = _get_schema_sql_objects()

    # Check all 24 tables are dropped
    for table_name in schema_objects["tables"]:
        assert f"DROP TABLE {table_name}" in sql_output, f"Missing DROP TABLE for {table_name}"

    # Check all 14 enums are dropped
    for enum_name in schema_objects["enums"]:
        assert f"DROP TYPE {enum_name}" in sql_output, f"Missing DROP TYPE for {enum_name}"

    # Check extensions and triggers are dropped
    assert "DROP EXTENSION IF EXISTS \"uuid-ossp\"" in sql_output
    assert "DROP EXTENSION IF EXISTS \"pg_trgm\"" in sql_output
    assert "DROP EXTENSION IF EXISTS \"btree_gin\"" in sql_output
    assert "DROP FUNCTION IF EXISTS update_updated_at_column" in sql_output
