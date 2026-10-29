import uuid
import asyncio

import pytest
from fastapi import HTTPException

from app.catalogue.auth import CatalogueRefresh, _decode, _make_token, refresh_catalogue_tokens
from app.catalogue.auth_db import _validated_catalogue_database_url
from app.catalogue.auth_models import CatalogueAccount, CatalogueWorkspace
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


def test_catalogue_db_url_cannot_bypass_same_database_check_with_default_port(monkeypatch):
    monkeypatch.setattr("app.catalogue.auth_db.settings.DATABASE_URL", "postgresql+asyncpg://u:p@localhost/rivu")
    monkeypatch.setattr("app.catalogue.auth_db.settings.CATALOGUE_DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/rivu")

    with pytest.raises(RuntimeError, match="different database"):
        _validated_catalogue_database_url()


def test_catalogue_db_url_accepts_a_distinct_database(monkeypatch):
    monkeypatch.setattr("app.catalogue.auth_db.settings.DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/rivu")
    monkeypatch.setattr("app.catalogue.auth_db.settings.CATALOGUE_DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5433/rivu_catalogue")

    assert _validated_catalogue_database_url().endswith("/rivu_catalogue")


def test_catalogue_refresh_rotates_tokens_and_rejects_replay(monkeypatch):
    monkeypatch.setattr("app.catalogue.auth.settings.CATALOGUE_JWT_SECRET", "catalogue-secret-that-is-at-least-32-chars")
    account_id, workspace_id = uuid.uuid4(), uuid.uuid4()
    account = CatalogueAccount(id=account_id, token_version=0)
    workspace = CatalogueWorkspace(id=workspace_id, owner_id=account_id)
    old_refresh = _make_token(account, workspace_id, "refresh")

    class Result:
        def scalar_one_or_none(self):
            return account

    class Session:
        async def execute(self, _statement):
            return Result()

        async def get(self, model, _key):
            return workspace if model is CatalogueWorkspace else None

        async def flush(self):
            return None

    session = Session()
    rotated = asyncio.run(refresh_catalogue_tokens(CatalogueRefresh(refresh_token=old_refresh), session))
    assert account.token_version == 1
    assert _decode(rotated["tokens"]["refresh_token"], "refresh")["tv"] == 1

    with pytest.raises(HTTPException) as error:
        asyncio.run(refresh_catalogue_tokens(CatalogueRefresh(refresh_token=old_refresh), session))
    assert error.value.status_code == 401
