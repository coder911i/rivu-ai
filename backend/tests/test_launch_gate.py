import pytest
import polars as pl

from app.cleaning.engine import TransformationEngine


def test_transformation_preserves_source_and_applies_deterministic_operations():
    source = pl.DataFrame({
        "name": [" Alice ", "Alice", "Bob"],
        "email": ["ALICE@EXAMPLE.COM", "alice@example.com", None],
    })
    result = TransformationEngine(source).execute_operations([
        {"type": "trim_whitespace", "column": "name"},
        {"type": "normalize_email", "column": "email"},
        {"type": "remove_duplicates"},
    ])

    assert source["name"].to_list() == [" Alice ", "Alice", "Bob"]
    assert result["ops_failed"] == 0
    assert result["df"].height == 3
    assert result["df"]["name"].to_list() == ["Alice", "Alice", "Bob"]
    assert result["df"]["email"].to_list() == ["alice@example.com", "alice@example.com", None]


@pytest.mark.parametrize(
    ("operation", "expected"),
    [
        ({"type": "lowercase", "column": "name"}, ["alice", "bob"]),
        ({"type": "uppercase", "column": "name"}, ["ALICE", "BOB"]),
        ({"type": "coerce_numeric", "column": "amount"}, [100.0, 250.0]),
    ],
)
def test_supported_transformations(operation, expected):
    if operation["type"] == "coerce_numeric":
        df = pl.DataFrame({"amount": ["₹100", "250"]})
    else:
        df = pl.DataFrame({"name": ["Alice", "Bob"]})

    result = TransformationEngine(df).execute_operations([operation])
    assert result["ops_failed"] == 0
    assert result["df"][operation["column"]].to_list() == expected


def test_invalid_column_is_reported_without_corrupting_output():
    df = pl.DataFrame({"name": ["Alice"]})
    result = TransformationEngine(df).execute_operations([
        {"type": "lowercase", "column": "missing"}
    ])

    assert result["ops_failed"] == 1
    assert result["df"].to_dicts() == [{"name": "Alice"}]
