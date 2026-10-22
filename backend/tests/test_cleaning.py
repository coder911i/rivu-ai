import polars as pl

from app.cleaning.engine import TransformationEngine


def test_cleaning_is_deterministic_and_does_not_mutate_source():
    source = pl.DataFrame({"name": ["  Alice  ", "BOB"], "email": [" A@X.COM ", "b@x.com"]})
    result = TransformationEngine(source).execute_operations([
        {"type": "trim_whitespace", "column": "name", "parameters": {}},
        {"type": "normalize_email", "column": "email", "parameters": {}},
    ])
    assert source["name"].to_list() == ["  Alice  ", "BOB"]
    assert result["df"]["name"].to_list() == ["Alice", "BOB"]
    assert result["df"]["email"].to_list() == ["a@x.com", "b@x.com"]


def test_duplicate_and_null_cleanup():
    source = pl.DataFrame({"id": [1, 1, 2], "value": ["x", None, "y"]})
    result = TransformationEngine(source).execute_operations([
        {"type": "remove_duplicates", "column": "id", "parameters": {}},
        {"type": "fill_null", "column": "value", "parameters": {"strategy": "empty_string"}},
    ])
    assert result["df"].height == 2
    assert result["df"]["value"].null_count() == 0


def test_invalid_column_is_recorded_as_failed_operation():
    source = pl.DataFrame({"id": [1, 2]})
    result = TransformationEngine(source).execute_operations([
        {"type": "trim_whitespace", "column": "missing", "parameters": {}},
    ])
    assert result["ops_failed"] == 1
    assert result["df"].height == 2


def test_normalize_email_trims_and_lowercases_without_mutating_source():
    source = pl.DataFrame({"email": ["  Zoë@Example.COM  ", "User+tag@EXAMPLE.org", None]})
    original = source.clone()

    result = TransformationEngine(source).execute_operations([
        {"type": "normalize_email", "column": "email", "parameters": {}},
    ])

    assert result["ops_failed"] == 0
    assert result["df"]["email"].to_list() == ["zoë@example.com", "user+tag@example.org", None]
    assert source.equals(original)
