import uuid

import pytest
from fastapi import HTTPException

from app.catalogue.auth import _decode, _make_token
from app.catalogue.auth_db import _validated_catalogue_database_url
from app.catalogue.auth_models import CatalogueAccount
from app.core.security import decode_token


def test_catalogue_tokens_use_a_separate_signing_secret(monkeypatch):
    monkeypatch.setattr("app.catalogue.auth.settings.CATALOGUE_JWT_SECRET", "catalogue-secret-that-is-at-least-32-chars")
    monkeypatch.setattr("app.core.security.settings.JWT_SECRET", "refinery-secret-that-is-at-least-32-chars")
    account = CatalogueAccount(id=uuid.uuid4(), token_version=0)

    token = _make_token(account, uuid.uuid4(), "access")

    assert _decode(token, "access")["type"] == "access"
    with pytest.raises(HTTPException) as error:
        decode_token(token)
    assert error.value.status_code == 401


def test_catalogue_db_url_must_be_a_different_database(monkeypatch):
    monkeypatch.setattr("app.catalogue.auth_db.settings.DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/rivu")
    monkeypatch.setattr("app.catalogue.auth_db.settings.CATALOGUE_DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/rivu")

    with pytest.raises(RuntimeError, match="different database"):
        _validated_catalogue_database_url()


def test_catalogue_db_url_accepts_a_distinct_database(monkeypatch):
    monkeypatch.setattr("app.catalogue.auth_db.settings.DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/rivu")
    monkeypatch.setattr("app.catalogue.auth_db.settings.CATALOGUE_DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5433/rivu_catalogue")

    assert _validated_catalogue_database_url().endswith("/rivu_catalogue")
