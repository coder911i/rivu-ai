"""JWT-based authentication and password hashing utilities."""

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.core.config import settings
from app.core.database import get_session

logger = structlog.get_logger(__name__)

# Password hashing. PBKDF2-SHA256 avoids the bcrypt/passlib backend compatibility
# issue where newer bcrypt releases can reject otherwise valid short passwords.
_pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


def create_access_token(subject: str | UUID, extra: dict[str, Any] | None = None) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(subject),
        "iat": now,
        "exp": expire,
        "type": "access",
        **(extra or {}),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str | UUID) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(subject),
        "iat": now,
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as e:
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
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is not active")

    return user


async def get_current_active_user(current_user=Depends(get_current_user)):
    return current_user


async def get_user_membership(user, db):
    """Return the user's primary organization membership."""
    from sqlalchemy import select
    from app.models.organization import Membership
    result = await db.execute(
        select(Membership).where(Membership.user_id == user.id).order_by(Membership.created_at.asc()).limit(1)
    )
    membership = result.scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=403, detail={"message": "No organization membership", "type": "forbidden"})
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
