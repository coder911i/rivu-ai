import pytest

from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password


def test_password_roundtrip():
    password = "Strong@123"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("Wrong@123", hashed)


def test_access_token_roundtrip():
    token = create_access_token("00000000-0000-0000-0000-000000000001", {"org_id": "test-org"})
    payload = decode_token(token)
    assert payload["type"] == "access"
    assert payload["sub"] == "00000000-0000-0000-0000-000000000001"
    assert payload["org_id"] == "test-org"


def test_refresh_token_supports_rotation_version():
    token = create_refresh_token("00000000-0000-0000-0000-000000000001", {"rtv": 3})
    payload = decode_token(token)
    assert payload["type"] == "refresh"
    assert payload["rtv"] == 3


def test_access_token_carries_session_version():
    token = create_access_token("00000000-0000-0000-0000-000000000001", {"org_id": "org", "tv": 2})
    assert decode_token(token)["tv"] == 2


def test_password_policy_accepts_128_chars():
    password = "Aa1" + "x" * 125
    hashed = hash_password(password)
    assert verify_password(password, hashed)
