import polars as pl

from app.cleaning.engine import TransformationEngine


def run(df, ops):
    return TransformationEngine(df).execute_operations(ops)


def test_trim_and_lowercase_are_deterministic():
    result = run(pl.DataFrame({"Name": ["  ALICE  ", " Bob"]}), [
        {"type": "trim_whitespace", "column": "Name", "parameters": {}},
        {"type": "lowercase", "column": "Name", "parameters": {}},
    ])
    assert result["ops_failed"] == 0
    assert result["df"]["Name"].to_list() == ["alice", "bob"]


def test_remove_duplicates_is_row_safe():
    result = run(pl.DataFrame({"id": [1, 1, 2], "name": ["a", "a", "b"]}), [
        {"type": "remove_duplicates", "column": None, "parameters": {}}
    ])
    assert result["ops_failed"] == 0
    assert result["df"].height == 2


def test_invalid_column_fails_operation_without_corrupting_dataframe():
    source = pl.DataFrame({"id": [1, 2]})
    result = run(source, [{"type": "lowercase", "column": "missing", "parameters": {}}])
    assert result["ops_failed"] == 1
    assert result["df"].to_dicts() == source.to_dicts()


def test_normalize_email_direct():
    source = pl.DataFrame({"email": ["  User@Example.COM  ", " TEST@Domain.org "]})
    result = run(source, [{"type": "normalize_email", "column": "email", "parameters": {}}])
    assert result["ops_failed"] == 0
    assert source["email"].to_list() == ["  User@Example.COM  ", " TEST@Domain.org "]
    assert result["df"]["email"].to_list() == ["user@example.com", "test@domain.org"]
