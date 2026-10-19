import pytest
from pydantic import ValidationError

from app.api.v1.endpoints.auth import _hash_email_token
from app.schemas.auth import PasswordResetCompleteRequest


def test_email_tokens_are_stored_as_one_way_hashes():
    token = "high-entropy-reset-token"
    digest = _hash_email_token(token)
    assert digest == _hash_email_token(token)
    assert digest != token
    assert len(digest) == 64


@pytest.mark.parametrize("password", ["short1A", "alllowercase123", "ALLUPPERCASE123", "ValidPassword1" * 10])
def test_password_reset_rejects_passwords_outside_policy(password):
    with pytest.raises(ValidationError):
        PasswordResetCompleteRequest(token="reset-token", new_password=password)


def test_password_reset_accepts_valid_password():
    body = PasswordResetCompleteRequest(token="reset-token", new_password="RivuSecure123")
    assert body.new_password == "RivuSecure123"
