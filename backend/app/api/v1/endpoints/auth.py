"""Authentication endpoints: signup, login, logout, me."""

from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import re
import structlog

from app.core.database import get_session
from app.core.email import send_email
from app.core.security import (
    hash_password, verify_password, create_access_token,
    create_refresh_token, decode_token, get_current_user
)
from app.core.config import settings
from app.models.user import User
from app.models.organization import Organization, Membership
from app.schemas.auth import SignupRequest, LoginRequest, TokenResponse, UserResponse, EmailTokenRequest, PasswordResetRequest, PasswordResetCompleteRequest

router = APIRouter()
logger = structlog.get_logger(__name__)


def _make_org_slug(username: str) -> str:
    slug = re.sub(r"[^a-z0-9]", "-", username.lower())
    return slug.strip("-")[:100]



def _hash_email_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _smtp_is_configured() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_FROM_EMAIL)


async def _send_account_email(user: User, token: str, *, purpose: str) -> None:
    frontend = settings.FRONTEND_URL.rstrip("/")
    if purpose == "verify":
        url = f"{frontend}/verify-email?token={quote(token)}"
        subject = "Verify your Rivu account"
        text_body = f"Hi {user.full_name or user.username},\n\nVerify your Rivu account using this link (expires in 24 hours):\n{url}\n"
    else:
        url = f"{frontend}/reset-password?token={quote(token)}"
        subject = "Reset your Rivu password"
        text_body = f"Hi {user.full_name or user.username},\n\nReset your Rivu password using this link (expires in 30 minutes):\n{url}\nIf you did not request this, ignore this email.\n"
    await send_email(user.email, subject, text_body)


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
    verification_token = secrets.token_urlsafe(32) if settings.REQUIRE_EMAIL_VERIFICATION else None
    user = User(
        email=body.email,
        username=body.username,
        full_name=body.full_name,
        password_hash=hash_password(body.password),
        status="pending_verification" if settings.REQUIRE_EMAIL_VERIFICATION else "active",
        email_verified=not settings.REQUIRE_EMAIL_VERIFICATION,
        email_verification_token_hash=_hash_email_token(verification_token) if verification_token else None,
        email_verification_expires_at=datetime.now(timezone.utc) + timedelta(hours=24) if verification_token else None,
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

    logger.info("user_signup", user_id=str(user.id), email=user.email)

    if settings.REQUIRE_EMAIL_VERIFICATION:
        try:
            await _send_account_email(user, verification_token, purpose="verify")
        except Exception as exc:
            logger.error("verification_email_failed", user_id=str(user.id), error=str(exc))
            raise HTTPException(status_code=503, detail={"message": "Account created but verification email could not be sent. Configure SMTP or request another verification email.", "type": "email_delivery_unavailable"}) from exc
        return {
            "user": {"id": str(user.id), "email": user.email, "username": user.username, "full_name": user.full_name},
            "organization": {"id": str(org.id), "name": org.name, "slug": org.slug},
            "verification_required": True,
            "message": "Check your email to verify your Rivu account.",
        }

    access_token = create_access_token(user.id, {"org_id": str(org.id), "tv": user.token_version})
    refresh_token = create_refresh_token(user.id, {"rtv": user.refresh_token_version})

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



@router.post("/verify-email", response_model=dict)
async def verify_email(body: EmailTokenRequest, db: AsyncSession = Depends(get_session)):
    """Verify an email address using a single-use, time-limited token."""
    result = await db.execute(
        select(User).where(User.email_verification_token_hash == _hash_email_token(body.token))
    )
    user = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if not user or not user.email_verification_expires_at or user.email_verification_expires_at <= now:
        raise HTTPException(status_code=400, detail={"message": "Verification link is invalid or expired", "type": "invalid_token"})
    user.email_verified = True
    if user.status == "pending_verification":
        user.status = "active"
    user.email_verification_token_hash = None
    user.email_verification_expires_at = None
    await db.commit()
    return {"message": "Email verified successfully. You can now sign in."}


@router.post("/resend-verification", response_model=dict)
async def resend_verification(body: PasswordResetRequest, db: AsyncSession = Depends(get_session)):
    """Resend verification without revealing whether an email is registered."""
    if not _smtp_is_configured():
        raise HTTPException(status_code=503, detail={"message": "Email delivery is not configured", "type": "email_delivery_unavailable"})
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user and not user.email_verified:
        token = secrets.token_urlsafe(32)
        user.email_verification_token_hash = _hash_email_token(token)
        user.email_verification_expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        await db.commit()
        try:
            await _send_account_email(user, token, purpose="verify")
        except Exception as exc:
            logger.error("verification_email_failed", user_id=str(user.id), error=str(exc))
            raise HTTPException(status_code=503, detail={"message": "Email delivery is temporarily unavailable", "type": "email_delivery_unavailable"}) from exc
    return {"message": "If the account exists and needs verification, an email will be sent."}


@router.post("/password-reset/request", response_model=dict)
async def request_password_reset(body: PasswordResetRequest, db: AsyncSession = Depends(get_session)):
    """Issue a short-lived password reset link without disclosing account existence."""
    if not _smtp_is_configured():
        raise HTTPException(status_code=503, detail={"message": "Email delivery is not configured", "type": "email_delivery_unavailable"})
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user and user.status != "suspended":
        token = secrets.token_urlsafe(32)
        user.password_reset_token_hash = _hash_email_token(token)
        user.password_reset_expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
        await db.commit()
        try:
            await _send_account_email(user, token, purpose="reset")
        except Exception as exc:
            logger.error("password_reset_email_failed", user_id=str(user.id), error=str(exc))
            raise HTTPException(status_code=503, detail={"message": "Email delivery is temporarily unavailable", "type": "email_delivery_unavailable"}) from exc
    return {"message": "If the account exists, a password reset email will be sent."}


@router.post("/password-reset/complete", response_model=dict)
async def complete_password_reset(body: PasswordResetCompleteRequest, db: AsyncSession = Depends(get_session)):
    """Consume a one-time reset token and revoke all existing sessions."""
    result = await db.execute(
        select(User).where(User.password_reset_token_hash == _hash_email_token(body.token))
    )
    user = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if not user or not user.password_reset_expires_at or user.password_reset_expires_at <= now:
        raise HTTPException(status_code=400, detail={"message": "Password reset link is invalid or expired", "type": "invalid_token"})
    user.password_hash = hash_password(body.new_password)
    user.token_version += 1
    user.refresh_token_version += 1
    user.password_reset_token_hash = None
    user.password_reset_expires_at = None
    await db.commit()
    return {"message": "Password updated successfully. Please sign in again."}


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
    result = await db.execute(select(User).where(User.id == user_id).with_for_update())
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


@router.post("/logout", response_model=dict)
async def logout(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Revoke this user's access and refresh tokens for all active sessions."""
    current_user.token_version += 1
    current_user.refresh_token_version += 1
    await db.commit()
    return {"message": "Logged out successfully"}


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
