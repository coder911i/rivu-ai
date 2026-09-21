import pytest

from app.core.exceptions import ValidationError
from app.ingestion.parser import parse_to_polars, validate_upload


def test_csv_roundtrip_and_delimiter_metadata():
    data = "id,name\n1,Alice\n2,Bob\n".encode()
    df, meta = parse_to_polars(data, "csv", "people.csv")
    assert df.height == 2
    assert df.width == 2
    assert meta["delimiter"] == ","


def test_csv_ragged_rows_are_rejected_instead_of_truncated():
    data = "id,name\n1,Alice\n2,Bob,EXTRA\n".encode()
    with pytest.raises(ValidationError):
        parse_to_polars(data, "csv", "people.csv")


@pytest.mark.parametrize("size,ok", [(1, True), (500 * 1024 * 1024, True), (500 * 1024 * 1024 + 1, False)])
def test_upload_size_boundary(size, ok):
    if ok:
        assert validate_upload("data.csv", size, "text/csv") == "csv"
    else:
        with pytest.raises(ValidationError):
            validate_upload("data.csv", size, "text/csv")


def test_unsupported_extension_is_rejected():
    with pytest.raises(ValidationError):
        validate_upload("data.exe", 10, "application/octet-stream")
