import polars as pl

from app.cleaning.engine import TransformationEngine


def test_engine_never_mutates_source_and_is_deterministic():
    source = pl.DataFrame({
        "name": ["  Alice  ", "BOB", "Alice"],
        "amount": ["₹1,000", "2,500", "2,500"],
        "email": [" Alice@Example.COM ", "bob@example.com", "bob@example.com"],
    })
    operations = [
        {"type": "trim_whitespace", "column": "name", "parameters": {}},
        {"type": "lowercase", "column": "email", "parameters": {}},
        {"type": "normalize_currency", "column": "amount", "parameters": {}},
        {"type": "remove_duplicates", "column": None, "parameters": {}},
    ]

    first = TransformationEngine(source).execute_operations(operations)
    second = TransformationEngine(source).execute_operations(operations)

    assert source["name"][0] == "  Alice  "
    assert first["df"].equals(second["df"])
    assert first["ops_failed"] == 0
    assert first["df"].height == 2


def test_null_fill_and_numeric_coercion():
    source = pl.DataFrame({"amount": ["10", None, "30"]})
    result = TransformationEngine(source).execute_operations([
        {"type": "coerce_numeric", "column": "amount", "parameters": {}},
        {"type": "fill_null", "column": "amount", "parameters": {"strategy": "median"}},
    ])
    assert result["ops_failed"] == 0
    assert result["df"]["amount"].null_count() == 0
    assert result["df"]["amount"].to_list() == [10.0, 20.0, 30.0]


def test_date_normalization_and_duplicate_flag():
    source = pl.DataFrame({"date": ["2026-01-02", "01/03/2026"], "id": ["a", "a"]})
    result = TransformationEngine(source).execute_operations([
        {"type": "standardize_date", "column": "date", "parameters": {}},
        {"type": "flag_duplicates", "column": "id", "parameters": {"flag_column": "dup"}},
    ])
    assert result["ops_failed"] == 0
    assert result["df"]["date"].to_list()[0].isoformat() == "2026-01-02"
    assert result["df"]["dup"].to_list() == [True, True]
