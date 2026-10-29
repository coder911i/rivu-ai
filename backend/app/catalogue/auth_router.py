"""Standalone Catalogue Portal signup, login, refresh, and session endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalogue.auth import (
    CatalogueLogin,
    CatalogueRefresh,
    CatalogueSignup,
    get_current_catalogue_user,
    login_catalogue_account,
    refresh_catalogue_tokens,
    signup_catalogue_account,
)
from app.catalogue.auth_db import get_catalogue_session
from app.catalogue.auth_models import CatalogueAccount, CatalogueWorkspace

router = APIRouter()


@router.post("/signup", status_code=201)
async def signup(body: CatalogueSignup, db: AsyncSession = Depends(get_catalogue_session)):
    return await signup_catalogue_account(body, db)


@router.post("/login")
async def login(body: CatalogueLogin, db: AsyncSession = Depends(get_catalogue_session)):
    return await login_catalogue_account(body, db)


@router.post("/refresh")
async def refresh(body: CatalogueRefresh, db: AsyncSession = Depends(get_catalogue_session)):
    return await refresh_catalogue_tokens(body, db)


@router.get("/me")
async def me(account: CatalogueAccount = Depends(get_current_catalogue_user), db: AsyncSession = Depends(get_catalogue_session)):
    workspace = await db.get(CatalogueWorkspace, account.active_workspace_id)
    return {
        "user": {"id": str(account.id), "email": account.email, "display_name": account.display_name},
        "workspace": {"id": str(workspace.id), "name": workspace.name} if workspace else None,
    }


@router.post("/logout")
async def logout(account: CatalogueAccount = Depends(get_current_catalogue_user), db: AsyncSession = Depends(get_catalogue_session)):
    account.token_version += 1
    await db.flush()
    return {"status": "signed_out"}
