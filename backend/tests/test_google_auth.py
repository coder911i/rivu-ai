"""Automated tests for Google OAuth authentication flow."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from google.auth.exceptions import GoogleAuthError

from app.main import app
from app.core.config import settings
from app.core.database import get_session
from app.api.v1.endpoints.auth import get_session as auth_get_session
from app.core.security import decode_token, hash_password, verify_google_id_token
from app.models.user import User
from app.models.organization import Organization, Membership
from app.schemas.auth import GoogleAuthRequest


class FakeDatabaseSession:
    """In-memory AsyncSession simulator for authentication tests."""

    def __init__(self):
        self.users: dict[uuid.UUID, User] = {}
        self.organizations: dict[uuid.UUID, Organization] = {}
        self.memberships: list[Membership] = []

    def add(self, entity):
        if isinstance(entity, User):
            if not getattr(entity, "id", None):
                entity.id = uuid.uuid4()
            self.users[entity.id] = entity
        elif isinstance(entity, Organization):
            if not getattr(entity, "id", None):
                entity.id = uuid.uuid4()
            self.organizations[entity.id] = entity
        elif isinstance(entity, Membership):
            if not getattr(entity, "id", None):
                entity.id = uuid.uuid4()
            self.memberships.append(entity)

    async def flush(self):
        pass

    async def commit(self):
        pass

    async def rollback(self):
        pass

    async def execute(self, statement):
        compiled = str(statement)
        params = statement.compile().params if hasattr(statement, "compile") else {}

        # 1. Lookup User by google_id
        if "users.google_id =" in compiled or "google_id" in params:
            val = next((v for k, v in params.items() if "google_id" in k), None)
            found = [u for u in self.users.values() if getattr(u, "google_id", None) == val]
            return SimpleNamespace(scalar_one_or_none=lambda: found[0] if found else None)

        # 2. Lookup User by email
        if "users.email =" in compiled or "email_1" in params or "email" in params:
            val = next((v for k, v in params.items() if "email" in k), None)
            found = [u for u in self.users.values() if u.email == val]
            return SimpleNamespace(scalar_one_or_none=lambda: found[0] if found else None)

        # 3. Lookup User by username
        if "users.username =" in compiled or "username_1" in params or "username" in params:
            val = next((v for k, v in params.items() if "username" in k), None)
            found = [u for u in self.users.values() if u.username == val]
            return SimpleNamespace(scalar_one_or_none=lambda: found[0] if found else None)

        # 4. Lookup Organization by slug
        if "organizations.slug =" in compiled or "slug_1" in params or "slug" in params:
            val = next((v for k, v in params.items() if "slug" in k), None)
            found = [o for o in self.organizations.values() if o.slug == val]
            return SimpleNamespace(scalar_one_or_none=lambda: found[0] if found else None)

        # 5. Lookup Membership + Organization for user
        if "memberships" in compiled and "organizations" in compiled:
            user_id = next((v for k, v in params.items() if "user_id" in k), None)
            matching_memberships = [
                m for m in self.memberships
                if str(m.user_id) == str(user_id) and m.accepted_at is not None
            ]
            if matching_memberships:
                m = matching_memberships[0]
                org = self.organizations.get(m.organization_id)
                row = SimpleNamespace(Membership=m, Organization=org)
                return SimpleNamespace(
                    first=lambda: row,
                    all=lambda: [row],
                    scalar_one_or_none=lambda: row,
                )
            return SimpleNamespace(first=lambda: None, all=lambda: [], scalar_one_or_none=lambda: None)

        return SimpleNamespace(scalar_one_or_none=lambda: None, first=lambda: None, all=lambda: [])


@pytest.fixture
def fake_db():
    session = FakeDatabaseSession()
    return session


@pytest.fixture(autouse=True)
def override_db(fake_db):
    async def _get_test_session():
        yield fake_db

    app.dependency_overrides[get_session] = _get_test_session
    app.dependency_overrides[auth_get_session] = _get_test_session
    yield fake_db
    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(auth_get_session, None)


@pytest.mark.asyncio
async def test_google_auth_new_user_success(override_db):
    """A new Google user gets an account, personal workspace, and valid JWTs."""
    db = override_db
    mock_id_info = {
        "iss": "https://accounts.google.com",
        "sub": "100200300400500",
        "email": "alex.chen@example.com",
        "email_verified": True,
        "name": "Alex Chen",
        "picture": "https://lh3.googleusercontent.com/photo.jpg",
    }

    with patch("google.oauth2.id_token.verify_oauth2_token", return_value=mock_id_info):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/auth/google", json={"id_token": "valid.google.jwt"})

    assert response.status_code == 200
    data = response.json()

    assert data["user"]["email"] == "alex.chen@example.com"
    assert data["user"]["full_name"] == "Alex Chen"
    assert "id" in data["user"]
    assert "tokens" in data
    assert "access_token" in data["tokens"]
    assert "refresh_token" in data["tokens"]
    assert data["tokens"]["token_type"] == "bearer"
    assert "organization" in data
    assert "id" in data["organization"]

    # Verify access token structure and claims
    access_payload = decode_token(data["tokens"]["access_token"])
    assert access_payload["type"] == "access"
    assert access_payload["sub"] == data["user"]["id"]
    assert access_payload["org_id"] == data["organization"]["id"]
    assert access_payload["tv"] == 0

    # Verify user in database
    user = next(iter(db.users.values()))
    assert user.google_id == "100200300400500"
    assert user.email == "alex.chen@example.com"
    assert user.email_verified is True
    assert user.status == "active"
    assert user.password_hash is None

    # Verify organization and membership
    org = next(iter(db.organizations.values()))
    assert org.owner_id == user.id
    assert len(db.memberships) == 1
    assert db.memberships[0].role == "owner"


@pytest.mark.asyncio
async def test_google_auth_credential_alias(override_db):
    """The endpoint accepts both 'id_token' and 'credential' field names."""
    mock_id_info = {
        "iss": "https://accounts.google.com",
        "sub": "999888777",
        "email": "gis.user@example.com",
        "email_verified": True,
        "name": "GIS User",
    }

    with patch("google.oauth2.id_token.verify_oauth2_token", return_value=mock_id_info):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/auth/google", json={"credential": "gsi.credential.jwt"})

    assert response.status_code == 200
    data = response.json()
    assert data["user"]["email"] == "gis.user@example.com"


@pytest.mark.asyncio
async def test_google_auth_existing_google_user_login(override_db):
    """An existing Google user logs in without creating duplicate users or workspaces."""
    db = override_db
    existing_user_id = uuid.uuid4()
    org_id = uuid.uuid4()

    existing_user = User(
        id=existing_user_id,
        email="existing@example.com",
        username="existing_user",
        full_name="Existing User",
        google_id="1122334455",
        password_hash=None,
        email_verified=True,
        status="active",
        token_version=1,
        refresh_token_version=2,
    )
    existing_org = Organization(
        id=org_id,
        name="Existing Workspace",
        slug="existing-workspace",
        owner_id=existing_user_id,
    )
    existing_membership = Membership(
        organization_id=org_id,
        user_id=existing_user_id,
        role="owner",
        accepted_at=datetime.now(timezone.utc),
    )
    db.add(existing_user)
    db.add(existing_org)
    db.add(existing_membership)

    mock_id_info = {
        "iss": "https://accounts.google.com",
        "sub": "1122334455",
        "email": "existing@example.com",
        "email_verified": True,
        "name": "Existing User",
    }

    with patch("google.oauth2.id_token.verify_oauth2_token", return_value=mock_id_info):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/auth/google", json={"id_token": "valid.token"})

    assert response.status_code == 200
    data = response.json()
    assert data["user"]["id"] == str(existing_user_id)
    assert data["organization"]["id"] == str(org_id)
    # Ensure no duplicate user or org was added
    assert len(db.users) == 1
    assert len(db.organizations) == 1


@pytest.mark.asyncio
async def test_google_auth_existing_email_password_account_linking(override_db):
    """An existing email/password user safely links to their Google identity upon verified Google login."""
    db = override_db
    user_id = uuid.uuid4()
    org_id = uuid.uuid4()

    existing_user = User(
        id=user_id,
        email="linkme@example.com",
        username="linkme",
        full_name="Link Me",
        password_hash=hash_password("OriginalPassword123"),
        google_id=None,
        email_verified=True,
        status="active",
    )
    org = Organization(id=org_id, name="Link Me's Workspace", slug="linkme-workspace", owner_id=user_id)
    membership = Membership(organization_id=org_id, user_id=user_id, role="owner", accepted_at=datetime.now(timezone.utc))
    db.add(existing_user)
    db.add(org)
    db.add(membership)

    mock_id_info = {
        "iss": "https://accounts.google.com",
        "sub": "google-sub-9999",
        "email": "linkme@example.com",
        "email_verified": True,
        "name": "Link Me Google",
    }

    with patch("google.oauth2.id_token.verify_oauth2_token", return_value=mock_id_info):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/auth/google", json={"id_token": "valid.token"})

    assert response.status_code == 200
    data = response.json()
    assert data["user"]["id"] == str(user_id)
    # Verify google_id was safely linked
    assert existing_user.google_id == "google-sub-9999"
    # Ensure original password remains untouched
    assert existing_user.password_hash is not None


@pytest.mark.asyncio
async def test_google_auth_rejects_unverified_email(override_db):
    """Never automatically link or authenticate accounts based on unverified email."""
    mock_id_info = {
        "iss": "https://accounts.google.com",
        "sub": "unverified-sub",
        "email": "unverified@example.com",
        "email_verified": False,
    }

    with patch("google.oauth2.id_token.verify_oauth2_token", return_value=mock_id_info):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/auth/google", json={"id_token": "token"})

    assert response.status_code == 400
    assert response.json()["detail"]["type"] == "unverified_email"


@pytest.mark.asyncio
async def test_google_auth_rejects_suspended_user(override_db):
    """Suspended users cannot authenticate via Google."""
    db = override_db
    user_id = uuid.uuid4()
    suspended_user = User(
        id=user_id,
        email="suspended@example.com",
        username="suspended",
        google_id="suspended-sub",
        status="suspended",
        password_hash=None,
    )
    db.add(suspended_user)

    mock_id_info = {
        "iss": "https://accounts.google.com",
        "sub": "suspended-sub",
        "email": "suspended@example.com",
        "email_verified": True,
    }

    with patch("google.oauth2.id_token.verify_oauth2_token", return_value=mock_id_info):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/auth/google", json={"id_token": "token"})

    assert response.status_code == 403
    assert response.json()["detail"]["message"] == "Account has been suspended"


@pytest.mark.asyncio
async def test_google_auth_rejects_inactive_user(override_db):
    """Inactive accounts are rejected."""
    db = override_db
    inactive_user = User(
        id=uuid.uuid4(),
        email="inactive@example.com",
        username="inactive",
        google_id="inactive-sub",
        status="inactive",
        password_hash=None,
    )
    db.add(inactive_user)

    mock_id_info = {
        "iss": "https://accounts.google.com",
        "sub": "inactive-sub",
        "email": "inactive@example.com",
        "email_verified": True,
    }

    with patch("google.oauth2.id_token.verify_oauth2_token", return_value=mock_id_info):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/auth/google", json={"id_token": "token"})

    assert response.status_code == 403
    assert response.json()["detail"]["message"] == "Account is not active"


@pytest.mark.asyncio
async def test_google_auth_activates_pending_verification_user(override_db):
    """A user in 'pending_verification' status is activated after verified Google sign-in."""
    db = override_db
    user_id = uuid.uuid4()
    org_id = uuid.uuid4()

    pending_user = User(
        id=user_id,
        email="pending@example.com",
        username="pending_user",
        status="pending_verification",
        email_verified=False,
        email_verification_token_hash="fakehash",
        password_hash=hash_password("Password123"),
    )
    org = Organization(id=org_id, name="Pending Workspace", slug="pending-workspace", owner_id=user_id)
    membership = Membership(organization_id=org_id, user_id=user_id, role="owner", accepted_at=datetime.now(timezone.utc))
    db.add(pending_user)
    db.add(org)
    db.add(membership)

    mock_id_info = {
        "iss": "https://accounts.google.com",
        "sub": "pending-google-sub",
        "email": "pending@example.com",
        "email_verified": True,
    }

    with patch("google.oauth2.id_token.verify_oauth2_token", return_value=mock_id_info):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/auth/google", json={"id_token": "token"})

    assert response.status_code == 200
    assert pending_user.status == "active"
    assert pending_user.email_verified is True
    assert pending_user.email_verification_token_hash is None


@pytest.mark.asyncio
async def test_google_auth_rejects_invalid_token():
    """An invalid token raises 401 Unauthorized."""
    with patch("google.oauth2.id_token.verify_oauth2_token", side_effect=ValueError("Token expired")):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/auth/google", json={"id_token": "expired.jwt"})

    assert response.status_code == 401
    assert response.json()["detail"]["type"] == "invalid_google_token"


@pytest.mark.asyncio
async def test_google_auth_rejects_wrong_issuer():
    """Tokens from issuers other than accounts.google.com are rejected."""
    mock_id_info = {
        "iss": "https://malicious-issuer.com",
        "sub": "fake-sub",
        "email": "user@example.com",
        "email_verified": True,
    }
    with patch("google.oauth2.id_token.verify_oauth2_token", return_value=mock_id_info):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/auth/google", json={"id_token": "evil.token"})

    assert response.status_code == 401
    assert response.json()["detail"]["type"] == "invalid_issuer"


@pytest.mark.asyncio
async def test_google_auth_rejects_empty_payload():
    """Request without token raises 422 Unprocessable Entity."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/auth/google", json={})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_google_user_cannot_login_with_empty_or_arbitrary_password(override_db):
    """Users created via Google who have no password_hash cannot be authenticated via /login."""
    db = override_db
    user_id = uuid.uuid4()
    google_only_user = User(
        id=user_id,
        email="googleonly@example.com",
        username="googleonly",
        google_id="google-sub-123",
        password_hash=None,
        email_verified=True,
        status="active",
    )
    db.add(google_only_user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/auth/login", json={
            "email": "googleonly@example.com",
            "password": "AnyPassword123!",
        })

    assert response.status_code == 401
    assert response.json()["detail"]["type"] == "unauthorized"
