"""Ensure every registered SQLAlchemy model table is represented in db/schema.sql."""
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import Base
import app.models  # noqa: F401

schema_path = Path(__file__).resolve().parents[2] / "db" / "schema.sql"
schema = schema_path.read_text(encoding="utf-8")
reference_tables = {
    name.lower()
    for name in re.findall(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z_][a-zA-Z0-9_]*)",
        schema,
        re.IGNORECASE,
    )
}
model_tables = {name.lower() for name in Base.metadata.tables}
missing = sorted(model_tables - reference_tables)
if missing:
    raise SystemExit(f"ORM tables missing from db/schema.sql: {', '.join(missing)}")
print(f"Schema reference contains all {len(model_tables)} ORM tables.")
