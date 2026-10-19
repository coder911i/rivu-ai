"""Authentication endpoints: signup, login, logout, me."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import re
import structlog

from app.core.database import get_session
from app.core.security import (
    hash_password, verify_password, create_access_token,
    create_refresh_token, decode_token, get_current_user
)
from app.core.config import settings
from app.models.user import User
from app.models.organization import Organization, Membership
from app.schemas.auth import SignupRequest, LoginRequest, TokenResponse, UserResponse

router = APIRouter()
logger = structlog.get_logger(__name__)


def _make_org_slug(username: str) -> str:
    slug = re.sub(r"[^a-z0-9]", "-", username.lower())
    return slug.strip("-")[:100]


@router.post("/signup", response_model=dict, status_code=status.HTTP_201_CREATED)
async def signup(body: SignupRequest, db: AsyncSession = Depends(get_session)):
    """Create a new user account and default organization."""
    # Check email uniqueness
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail={"message": "Email already registered", "type": "conflict"})

    # Check username uniqueness
    existing_uname = await db.execute(select(User).where(User.username == body.username))
    if existing_uname.scalar_one_or_none():
        raise HTTPException(status_code=409, detail={"message": "Username already taken", "type": "conflict"})

    # Create user
    user = User(
        email=body.email,
        username=body.username,
        full_name=body.full_name,
        password_hash=hash_password(body.password),
        status="active",
    )
    db.add(user)
    await db.flush()  # get user.id

    # Create default personal organization
    base_slug = _make_org_slug(body.username)
    slug = base_slug
    # ensure slug uniqueness
    counter = 1
    while True:
        existing_slug = await db.execute(select(Organization).where(Organization.slug == slug))
        if not existing_slug.scalar_one_or_none():
            break
        slug = f"{base_slug}-{counter}"
        counter += 1

    org = Organization(
        name=f"{body.full_name or body.username}'s Workspace",
        slug=slug,
        owner_id=user.id,
        plan="free",
    )
    db.add(org)
    await db.flush()

    # Owner membership
    membership = Membership(
        organization_id=org.id,
        user_id=user.id,
        role="owner",
        accepted_at=datetime.now(timezone.utc),
    )
    db.add(membership)
    await db.commit()

    # Generate tokens
    access_token = create_access_token(user.id, {"org_id": str(org.id), "tv": user.token_version})
    refresh_token = create_refresh_token(user.id, {"rtv": user.refresh_token_version})

    logger.info("user_signup", user_id=str(user.id), email=user.email)

    return {
        "user": {
            "id": str(user.id),
            "email": user.email,
            "username": user.username,
            "full_name": user.full_name,
        },
        "organization": {
            "id": str(org.id),
            "name": org.name,
            "slug": org.slug,
        },
        "tokens": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        },
    }


@router.post("/login", response_model=dict)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_session)):
    """Login with email and password."""
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Invalid email or password", "type": "unauthorized"},
        )

    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Account is not active", "type": "forbidden"},
        )

    # Get primary org
    membership_result = await db.execute(
        select(Membership, Organization)
        .join(Organization, Organization.id == Membership.organization_id)
        .where(Membership.user_id == user.id, Membership.accepted_at.is_not(None))
        .order_by(Membership.created_at.asc())
        .limit(1)
    )
    row = membership_result.first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"message": "No workspace membership", "type": "forbidden"})
    org_id = str(row.Organization.id)
    org_name = row.Organization.name if row else None

    # Update last login
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    access_token = create_access_token(user.id, {"org_id": org_id, "tv": user.token_version})
    refresh_token = create_refresh_token(user.id, {"rtv": user.refresh_token_version})

    logger.info("user_login", user_id=str(user.id))

    return {
        "user": {
            "id": str(user.id),
            "email": user.email,
            "username": user.username,
            "full_name": user.full_name,
        },
        "organization": {
            "id": org_id,
            "name": org_name,
        },
        "tokens": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        },
    }


@router.post("/refresh", response_model=dict)
async def refresh_token(body: dict, db: AsyncSession = Depends(get_session)):
    """Exchange a valid refresh token for a new access token."""
    token = body.get("refresh_token")
    if not token:
        raise HTTPException(status_code=400, detail={"message": "refresh_token is required", "type": "validation_error"})
    payload = decode_token(token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail={"message": "Invalid refresh token", "type": "unauthorized"})
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail={"message": "Invalid refresh token", "type": "unauthorized"})
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or user.status != "active":
        raise HTTPException(status_code=401, detail={"message": "Account is not active", "type": "unauthorized"})
    if payload.get("rtv", 0) != user.refresh_token_version:
        raise HTTPException(status_code=401, detail={"message": "Refresh token has been revoked or rotated", "type": "unauthorized"})
    membership_result = await db.execute(
        select(Membership, Organization)
        .join(Organization, Organization.id == Membership.organization_id)
        .where(Membership.user_id == user.id, Membership.accepted_at.is_not(None))
        .order_by(Membership.created_at.asc())
        .limit(1)
    )
    row = membership_result.first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"message": "No workspace membership", "type": "forbidden"})
    org_id = str(row.Organization.id)
    # Rotate refresh tokens on every use; replaying the previous token is rejected.
    user.refresh_token_version += 1
    await db.commit()
    return {
        "tokens": {
            "access_token": create_access_token(user.id, {"org_id": org_id, "tv": user.token_version}),
            "refresh_token": create_refresh_token(user.id, {"rtv": user.refresh_token_version}),
            "token_type": "bearer",
            "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }
    }


@router.get("/me", response_model=dict)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Get currently authenticated user profile and organizations."""
    memberships = await db.execute(
        select(Membership, Organization)
        .join(Organization, Organization.id == Membership.organization_id)
        .where(Membership.user_id == current_user.id)
    )

    orgs = [
        {
            "id": str(row.Organization.id),
            "name": row.Organization.name,
            "slug": row.Organization.slug,
            "role": row.Membership.role,
        }
        for row in memberships.all()
    ]

    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "username": current_user.username,
        "full_name": current_user.full_name,
        "status": current_user.status,
        "created_at": current_user.created_at.isoformat(),
        "organizations": orgs,
    }
