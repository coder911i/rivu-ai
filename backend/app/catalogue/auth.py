"""Authentication and one-owner workspace access for the standalone Catalogue Portal."""

from datetime import datetime, timedelta, timezone
import re
import uuid
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalogue.auth_db import get_catalogue_session
from app.catalogue.auth_models import CatalogueAccount, CatalogueWorkspace
from app.core.config import settings
from app.core.security import hash_password, verify_password

catalogue_oauth = OAuth2PasswordBearer(tokenUrl="/api/v1/catalogue/auth/login")


class CatalogueSignup(BaseModel):
    email: str
    password: str
    display_name: str = Field(min_length=2, max_length=200)
    workspace_name: str = Field(min_length=2, max_length=200)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if len(value) > 320 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Enter a valid email address")
        return value

    @field_validator("password")
    @classmethod
    def check_password(cls, value: str) -> str:
        if len(value) < 10 or len(value) > 128:
            raise ValueError("Password must be 10 to 128 characters")
        if not any(char.islower() for char in value) or not any(char.isupper() for char in value) or not any(char.isdigit() for char in value):
            raise ValueError("Password must include uppercase, lowercase, and a number")
        return value


class CatalogueLogin(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Enter a valid email address")
        return value


class CatalogueRefresh(BaseModel):
    refresh_token: str


def _secret() -> str:
    secret = settings.CATALOGUE_JWT_SECRET
    if not secret or len(secret) < 32:
        raise HTTPException(status_code=503, detail={"message": "Catalogue Portal signing key is not configured", "type": "catalogue_not_configured"})
    return secret


def _make_token(account: CatalogueAccount, workspace_id: uuid.UUID, token_type: str) -> str:
    now = datetime.now(timezone.utc)
    lifetime = timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS) if token_type == "refresh" else timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(account.id), "workspace_id": str(workspace_id), "iat": now, "exp": now + lifetime, "type": token_type, "tv": account.token_version}
    return jwt.encode(payload, _secret(), algorithm=settings.JWT_ALGORITHM)


def _tokens(account: CatalogueAccount, workspace: CatalogueWorkspace) -> dict[str, Any]:
    return {
        "access_token": _make_token(account, workspace.id, "access"),
        "refresh_token": _make_token(account, workspace.id, "refresh"),
        "token_type": "bearer",
        "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


def _decode(token: str, expected_type: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, _secret(), algorithms=[settings.JWT_ALGORITHM])
    except InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired Catalogue Portal token", headers={"WWW-Authenticate": "Bearer"}) from exc
    if payload.get("type") != expected_type:
        raise HTTPException(status_code=401, detail="Invalid Catalogue Portal token type")
    return payload


async def get_current_catalogue_user(
    token: str = Depends(catalogue_oauth),
    db: AsyncSession = Depends(get_catalogue_session),
) -> CatalogueAccount:
    payload = _decode(token, "access")
    try:
        account_id = uuid.UUID(payload["sub"])
        workspace_id = uuid.UUID(payload["workspace_id"])
    except (KeyError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=401, detail="Invalid Catalogue Portal token payload") from exc
    account = await db.get(CatalogueAccount, account_id)
    workspace = await db.get(CatalogueWorkspace, workspace_id)
    if not account or not workspace or workspace.owner_id != account.id or payload.get("tv") != account.token_version:
        raise HTTPException(status_code=401, detail="Catalogue Portal session is no longer valid")
    account.active_org_id = workspace.id
    account.active_workspace_id = workspace.id
    return account


async def require_catalogue_role(account: CatalogueAccount, db: AsyncSession, allowed_roles: set[str]):
    # Accounts own one isolated workspace. View-only roles are intentionally not provisioned yet.
    if "editor" not in allowed_roles and "admin" not in allowed_roles and "owner" not in allowed_roles:
        raise HTTPException(status_code=403, detail={"message": "Insufficient catalogue workspace permissions", "type": "forbidden"})
    workspace = (await db.execute(select(CatalogueWorkspace).where(CatalogueWorkspace.owner_id == account.id))).scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=403, detail={"message": "Catalogue workspace access denied", "type": "forbidden"})
    return type("CatalogueMembership", (), {"organization_id": workspace.id, "role": "owner"})()


async def signup_catalogue_account(body: CatalogueSignup, db: AsyncSession) -> dict[str, Any]:
    existing = (await db.execute(select(CatalogueAccount).where(CatalogueAccount.email == body.email))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail={"message": "This email already has a Catalogue Portal account", "type": "conflict"})
    account = CatalogueAccount(email=body.email, display_name=body.display_name.strip(), password_hash=hash_password(body.password))
    db.add(account)
    await db.flush()
    workspace = CatalogueWorkspace(name=body.workspace_name.strip(), owner_id=account.id)
    db.add(workspace)
    await db.flush()
    return {"tokens": _tokens(account, workspace), "user": {"id": str(account.id), "email": account.email, "display_name": account.display_name}, "workspace": {"id": str(workspace.id), "name": workspace.name}}


async def login_catalogue_account(body: CatalogueLogin, db: AsyncSession) -> dict[str, Any]:
    account = (await db.execute(select(CatalogueAccount).where(CatalogueAccount.email == body.email))).scalar_one_or_none()
    if not account or not verify_password(body.password, account.password_hash):
        raise HTTPException(status_code=401, detail={"message": "Email or password is incorrect", "type": "invalid_credentials"})
    workspace = (await db.execute(select(CatalogueWorkspace).where(CatalogueWorkspace.owner_id == account.id))).scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=403, detail="Catalogue workspace not found")
    return {"tokens": _tokens(account, workspace), "user": {"id": str(account.id), "email": account.email, "display_name": account.display_name}, "workspace": {"id": str(workspace.id), "name": workspace.name}}


async def refresh_catalogue_tokens(body: CatalogueRefresh, db: AsyncSession) -> dict[str, Any]:
    payload = _decode(body.refresh_token, "refresh")
    try:
        account_id = uuid.UUID(payload["sub"])
        workspace_id = uuid.UUID(payload["workspace_id"])
    except (KeyError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=401, detail="Invalid Catalogue Portal token payload") from exc
    account = (await db.execute(
        select(CatalogueAccount).where(CatalogueAccount.id == account_id).with_for_update()
    )).scalar_one_or_none()
    workspace = await db.get(CatalogueWorkspace, workspace_id)
    if not account or not workspace or workspace.owner_id != account.id or payload.get("tv") != account.token_version:
        raise HTTPException(status_code=401, detail="Catalogue Portal session is no longer valid")
    # Rotate under a row lock so concurrent reuse can only succeed once.
    account.token_version += 1
    await db.flush()
    return {"tokens": _tokens(account, workspace)}
