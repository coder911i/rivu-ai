import io
import json
import pandas as pd
import polars as pl
import pytest

from app.ingestion.parser import detect_file_format, parse_to_polars, validate_file_signature


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


def test_json_records_round_trip_to_dataframe():
    raw = json.dumps([{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]).encode()
    df, _ = parse_to_polars(raw, "json", "data.json")
    assert df.height == 2
    assert df.columns == ["id", "name"]


def test_parquet_signature_rejects_invalid_bytes():
    with pytest.raises(Exception):
        validate_file_signature(b"NOTPARQUET", "parquet")


def test_xlsx_signature_rejects_invalid_bytes():
    with pytest.raises(Exception):
        validate_file_signature(b"NOTXLSX", "xlsx")
