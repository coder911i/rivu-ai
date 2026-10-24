import polars as pl

from app.cleaning.engine import TransformationEngine


def test_cleaning_is_deterministic_and_does_not_mutate_source():
    source = pl.DataFrame({"name": ["  Alice  ", "BOB"], "email": [" A@X.COM ", "b@x.com"]})
    result = TransformationEngine(source).execute_operations([
        {"type": "trim_whitespace", "column": "name", "parameters": {}},
        {"type": "normalize_email", "column": "email", "parameters": {}},
    ])
    assert source["name"].to_list() == ["  Alice  ", "BOB"]
    assert source["email"].to_list() == [" A@X.COM ", "b@x.com"]
    assert result["df"]["name"].to_list() == ["Alice", "BOB"]
    assert result["df"]["email"].to_list() == ["a@x.com", "b@x.com"]


def test_normalize_email_lowercases_and_trims_whitespace():
    source = pl.DataFrame({"email": ["  Alice@EXAMPLE.com  ", "\tBOB@Domain.ORG\n", "already.clean@test.co"]})
    result = TransformationEngine(source).execute_operations([
        {"type": "normalize_email", "column": "email", "parameters": {}},
    ])
    assert result["ops_failed"] == 0
    assert result["ops_applied"] == 1
    # Verify source DataFrame remains unchanged
    assert source["email"].to_list() == ["  Alice@EXAMPLE.com  ", "\tBOB@Domain.ORG\n", "already.clean@test.co"]
    assert result["df"]["email"].to_list() == [
        "alice@example.com",
        "bob@domain.org",
        "already.clean@test.co",
    ]


def test_lowercase_does_not_trim_whitespace():
    source = pl.DataFrame({"text": ["  Alice  ", " BOB "]})
    result = TransformationEngine(source).execute_operations([
        {"type": "lowercase", "column": "text", "parameters": {}},
    ])
    assert result["ops_failed"] == 0
    assert result["ops_applied"] == 1
    # Verify source DataFrame remains unchanged
    assert source["text"].to_list() == ["  Alice  ", " BOB "]
    # Verify letter case changes but whitespace is preserved
    assert result["df"]["text"].to_list() == ["  alice  ", " bob "]



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
