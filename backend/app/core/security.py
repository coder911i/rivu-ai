"""JWT-based authentication and password hashing utilities."""

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import jwt
from jwt import InvalidTokenError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.core.config import settings
from app.core.database import get_session

logger = structlog.get_logger(__name__)

# PBKDF2-SHA256 avoids bcrypt/passlib backend compatibility problems.
_pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


def create_access_token(subject: str | UUID, extra: dict[str, Any] | None = None) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(subject), "iat": now, "exp": expire, "type": "access", **(extra or {})}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str | UUID, extra: dict[str, Any] | None = None) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": str(subject), "iat": now, "exp": expire, "type": "refresh", **(extra or {})}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_session),
):
    """Dependency that returns the currently authenticated user."""
    from app.models.user import User
    from sqlalchemy import select

    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    user_id = payload.get("sub")
    org_id = payload.get("org_id")
    if not user_id or not org_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    try:
        active_org_id = UUID(str(org_id))
        user_uuid = UUID(str(user_id))
    except (TypeError, ValueError, AttributeError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload") from exc

    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is not active")
    if payload.get("tv", 0) != user.token_version:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session has been revoked")

    # Bind every request to the workspace explicitly encoded in the access token.
    from app.models.organization import Membership
    membership_result = await db.execute(
        select(Membership.id).where(
            Membership.user_id == user.id,
            Membership.organization_id == active_org_id,
            Membership.accepted_at.is_not(None),
        )
    )
    if membership_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Workspace access denied")
    user.active_org_id = active_org_id
    return user


async def get_current_active_user(current_user=Depends(get_current_user)):
    return current_user


async def get_user_membership(user, db):
    """Return membership for the explicitly selected workspace in the access token."""
    from sqlalchemy import select
    from app.models.organization import Membership

    active_org_id = getattr(user, "active_org_id", None)
    if active_org_id is None:
        raise HTTPException(status_code=403, detail={"message": "No active workspace", "type": "forbidden"})
    result = await db.execute(
        select(Membership).where(
            Membership.user_id == user.id,
            Membership.organization_id == active_org_id,
            Membership.accepted_at.is_not(None),
        )
    )
    membership = result.scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=403, detail={"message": "Workspace access denied", "type": "forbidden"})
    return membership


async def require_org_role(user, db, allowed_roles: set[str]):
    """Centralized organization role check used by mutating endpoints."""
    membership = await get_user_membership(user, db)
    if membership.role not in allowed_roles:
        raise HTTPException(
            status_code=403,
            detail={"message": "Insufficient organization permissions", "type": "forbidden"},
        )
    return membership


def verify_google_id_token(token: str, client_id: str | None = None) -> dict[str, Any]:
    """Verify a Google ID token's signature, issuer, expiration, and audience.

    Never trusts client claims; only uses payload verified by Google's public keys.
    """
    from google.oauth2 import id_token as google_id_token
    from google.auth.transport import requests as google_requests
    from google.auth.exceptions import GoogleAuthError

    target_client_id = client_id or settings.GOOGLE_CLIENT_ID
    if not target_client_id:
        logger.error("google_auth_client_id_not_configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"message": "Google authentication is not configured on this server", "type": "auth_not_configured"},
        )

    try:
        id_info = google_id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            audience=target_client_id,
        )
    except (GoogleAuthError, ValueError) as exc:
        logger.warning("google_token_verification_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Invalid, expired, or malformed Google ID token", "type": "invalid_google_token"},
        ) from exc

    issuer = id_info.get("iss")
    if issuer not in ("accounts.google.com", "https://accounts.google.com"):
        logger.warning("google_token_invalid_issuer", issuer=issuer)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Invalid Google token issuer", "type": "invalid_issuer"},
        )

    return id_info
