import pytest

from app.core.exceptions import ValidationError
from app.ingestion.parser import FALLBACK_ENCODING, parse_to_polars, validate_upload


def test_csv_roundtrip_and_delimiter_metadata():
    data = "id,name\n1,Alice\n2,Bob\n".encode()
    df, meta = parse_to_polars(data, "csv", "people.csv")
    assert df.height == 2
    assert df.width == 2
    assert meta["delimiter"] == ","


def test_csv_short_utf8_and_legacy_fallback():
    # Strict UTF-8 with accented characters
    utf8_data = "id,name\n1,Zoë\n".encode("utf-8")
    df_utf8, meta_utf8 = parse_to_polars(utf8_data, "csv", "utf8.csv")
    assert meta_utf8["encoding"] == "utf-8"
    assert df_utf8["name"][0] == "Zoë"
    assert "\ufffd" not in df_utf8["name"][0]

    # Legacy-encoded fallback with accented characters
    legacy_data = "id,name\n1,Zoë\n".encode(FALLBACK_ENCODING)
    df_legacy, meta_legacy = parse_to_polars(legacy_data, "csv", "legacy.csv")
    assert meta_legacy["encoding"].lower().replace("_", "-") in {"latin-1", "iso-8859-1", "cp1252", "windows-1252"}
    assert df_legacy["name"][0] == "Zoë"
    assert "\ufffd" not in df_legacy["name"][0]



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


def test_binary_signature_validation():
    from app.ingestion.parser import validate_file_signature
    validate_file_signature(b"PAR1" + b"x", "parquet")
    validate_file_signature(b"PK\x03\x04" + b"x", "xlsx")
    validate_file_signature(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"x", "xls")

    with pytest.raises(ValidationError):
        validate_file_signature(b"not-a-parquet", "parquet")

    with pytest.raises(ValidationError):
        validate_file_signature(b"not-an-xlsx", "xlsx")

    with pytest.raises(ValidationError):
        validate_file_signature(b"not-an-xls", "xls")

    # Verify literal backslash strings are rejected
    with pytest.raises(ValidationError):
        validate_file_signature(b"PK\\x03\\x04" + b"x", "xlsx")

    with pytest.raises(ValidationError):
        validate_file_signature(b"\\xd0\\xcf\\x11\\xe0\\xa1\\xb1\\x1a\\xe1" + b"x", "xls")
