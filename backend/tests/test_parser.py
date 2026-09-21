import pytest
import polars as pl

from app.core.exceptions import ValidationError
from app.ingestion.parser import parse_to_polars, validate_upload


def test_csv_roundtrip_preserves_rows_and_long_values():
    value = "x" * 1000
    data = ("name,value\nAlice," + value + "\nBob," + ("y" * 200) + "\n").encode()
    df, meta = parse_to_polars(data, "csv", "sample.csv")
    assert df.height == 2
    assert df.width == 2
    assert df["value"][0] == value
    assert meta["delimiter"] == ","


def test_ragged_csv_is_rejected_instead_of_truncated():
    data = b"name,age\nAlice,20\nBob,21,unexpected\n"
    with pytest.raises(ValidationError):
        parse_to_polars(data, "csv", "bad.csv")


def test_empty_upload_rejected():
    with pytest.raises(ValidationError):
        validate_upload("empty.csv", 0, "text/csv")


def test_unsupported_extension_rejected():
    with pytest.raises(ValidationError):
        validate_upload("payload.exe", 10, "application/octet-stream")


def test_invalid_content_type_rejected():
    with pytest.raises(ValidationError):
        validate_upload("data.csv", 10, "application/pdf")


def test_shape_limits_are_enforced():
    # 2,001 columns should fail before entering the refinery.
    header = ",".join(f"c{i}" for i in range(2001))
    with pytest.raises(ValidationError):
        parse_to_polars((header + "\n" + ",".join("1" for _ in range(2001))).encode(), "csv", "wide.csv")
