import json

import pytest

from app.core.exceptions import ValidationError
from app.ingestion.parser import (
    FALLBACK_ENCODING,
    detect_encoding,
    detect_file_format,
    parse_to_polars,
    validate_file_signature,
)


def test_supported_formats_preserve_extension():
    assert detect_file_format("data.csv", "text/csv") == "csv"
    assert detect_file_format("data.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet") == "xlsx"
    assert detect_file_format("data.xls", "application/vnd.ms-excel") == "xls"
    assert detect_file_format("data.json", "application/json") == "json"
    assert detect_file_format("data.parquet", "application/octet-stream") == "parquet"


def test_csv_strictly_rejects_ragged_rows():
    bad = b"name,age\nAlice,20\nBob,21,EXTRA\n"
    with pytest.raises(Exception):
        parse_to_polars(bad, "csv", "bad.csv")


def test_csv_delimiter_and_unicode_are_detected():
    raw = "name;city\nTanishq;Meerut\nZoë;Paris\n".encode("utf-8")
    df, meta = parse_to_polars(raw, "csv", "people.csv")
    assert df.height == 2
    assert df.width == 2
    assert meta["delimiter"] == ";"
    assert "Zoë" in df["name"].to_list()


def test_short_utf8_csv_with_accented_text_preserves_characters():
    # Short UTF-8 CSV containing accented text like Zoë
    raw = "name,city\nZoë,Paris\n".encode("utf-8")
    assert detect_encoding(raw) == "utf-8"

    df, meta = parse_to_polars(raw, "csv", "short_zoe.csv")
    assert df.height == 1
    assert df.width == 2
    assert meta["encoding"] == "utf-8"
    assert meta["delimiter"] == ","
    assert df["name"].to_list() == ["Zoë"]
    assert df["city"].to_list() == ["Paris"]
    # Ensure no replacement character was introduced
    assert "\ufffd" not in df["name"][0]


def test_legacy_encoded_csv_supported_by_fallback_preserves_characters():
    # Genuinely legacy-encoded CSV (latin-1) containing characters that are invalid UTF-8 bytes
    raw = "name;city\nZoë;Paris\nRené;München\n".encode(FALLBACK_ENCODING)
    assert detect_encoding(raw).lower().replace("_", "-") in {"latin-1", "iso-8859-1", "cp1252", "windows-1252"}

    df, meta = parse_to_polars(raw, "csv", "legacy_zoe.csv")
    assert df.height == 2
    assert df.width == 2
    assert meta["encoding"].lower().replace("_", "-") in {"latin-1", "iso-8859-1", "cp1252", "windows-1252"}
    assert meta["delimiter"] == ";"
    assert df["name"].to_list() == ["Zoë", "René"]
    assert df["city"].to_list() == ["Paris", "München"]
    # Ensure characters are strictly preserved without silent replacement
    assert "\ufffd" not in "".join(df["name"].to_list() + df["city"].to_list())



def test_json_records_round_trip_to_dataframe():
    raw = json.dumps([{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]).encode()
    df, _ = parse_to_polars(raw, "json", "data.json")
    assert df.height == 2
    assert df.columns == ["id", "name"]


def test_parquet_signature_rejects_invalid_bytes():
    with pytest.raises(ValidationError):
        validate_file_signature(b"NOTPARQUET", "parquet")


def test_xlsx_signature_accepts_valid_bytes():
    # Valid ZIP / XLSX signature: 0x50, 0x4B, 0x03, 0x04
    valid_xlsx_bytes = b"PK\x03\x04" + b"\x14\x00\x06\x00dummy-payload"
    validate_file_signature(valid_xlsx_bytes, "xlsx")


def test_xlsx_signature_rejects_invalid_bytes():
    with pytest.raises(ValidationError):
        validate_file_signature(b"NOTXLSX", "xlsx")


def test_csv_prefers_valid_utf8_for_accented_text():
    raw = "name,city\nZoë,Montréal\nFrançois,Québec\n".encode("utf-8")
    df, meta = parse_to_polars(raw, "csv", "utf8.csv")
    assert meta["encoding"] == "utf-8"
    assert df["name"].to_list() == ["Zoë", "François"]
    assert df["city"].to_list() == ["Montréal", "Québec"]


def test_csv_falls_back_to_legacy_windows_1252():
    raw = "name,city\nAndré,Montréal\n".encode("cp1252")
    df, meta = parse_to_polars(raw, "csv", "legacy.csv")
    assert meta["encoding"].lower().replace("_", "-") in {"cp1252", "windows-1252", "iso-8859-1", "latin-1"}
    assert df["name"].to_list() == ["André"]
    assert df["city"].to_list() == ["Montréal"]


@pytest.mark.parametrize(
    ("payload", "file_format"),
    [
        (b"PK\x03\x04" + b"\x00" * 8, "xlsx"),
        (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 8, "xls"),
    ],
)
def test_excel_real_binary_signatures_are_accepted(payload, file_format):
    validate_file_signature(payload, file_format)


@pytest.mark.parametrize(
    ("payload", "file_format"),
    [
        (b"PK\x03\x05" + b"\x00" * 8, "xlsx"),
        (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe0" + b"\x00" * 8, "xls"),
        (b"not-an-office-file", "xlsx"),
        (b"not-an-office-file", "xls"),
    ],
)
def test_excel_invalid_binary_signatures_are_rejected(payload, file_format):
    from app.core.exceptions import ValidationError
    with pytest.raises(ValidationError):
        validate_file_signature(payload, file_format)
    # Literal backslash text must be rejected
    with pytest.raises(ValidationError):
        validate_file_signature(b"PK\\x03\\x04" + b"extra", "xlsx")


def test_xls_signature_accepts_valid_bytes():
    # Valid OLE2 / XLS signature: 0xD0, 0xCF, 0x11, 0xE0, 0xA1, 0xB1, 0x1A, 0xE1
    valid_xls_bytes = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"dummy-payload"
    validate_file_signature(valid_xls_bytes, "xls")


def test_xls_signature_rejects_invalid_bytes():
    with pytest.raises(ValidationError):
        validate_file_signature(b"NOTXLSFILE", "xls")

    # Literal backslash text must be rejected
    with pytest.raises(ValidationError):
        validate_file_signature(b"\\xd0\\xcf\\x11\\xe0\\xa1\\xb1\\x1a\\xe1" + b"extra", "xls")
