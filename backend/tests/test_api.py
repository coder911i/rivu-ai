from unittest.mock import AsyncMock
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.core.config import Settings
from app.core.database import get_session
from app.core.security import create_access_token

async def dummy_session():
    mock_session = AsyncMock()
    yield mock_session

app.dependency_overrides[get_session] = dummy_session


@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "rivu-api"
        assert "version" in data


@pytest.mark.asyncio
async def test_root_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "Rivu" in data["product"]
        assert "version" in data


@pytest.mark.asyncio
async def test_security_headers():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.headers.get("x-content-type-options") == "nosniff"
        assert response.headers.get("x-frame-options") == "DENY"
        assert response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
        assert "default-src" in response.headers.get("content-security-policy", "")


@pytest.mark.asyncio
async def test_api_cache_control_header():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/projects/")
        assert response.headers.get("cache-control") == "no-store"


@pytest.mark.asyncio
async def test_protected_routes_require_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/projects/")
        assert response.status_code == 401

        response = await client.post("/api/v1/projects/", json={"name": "Test"})
        assert response.status_code == 401

        response = await client.get(
            "/api/v1/projects/",
            headers={"Authorization": "Bearer invalid_or_malformed_token"},
        )
        assert response.status_code == 401


def test_production_security_guardrails():
    # Production with default secret should fail
    insecure_settings = Settings(
        APP_ENV="production",
        DEBUG=False,
        JWT_SECRET="CHANGE_THIS_IN_PRODUCTION_RANDOM_SECRET",
        AUTO_CREATE_SCHEMA=False,
        S3_USE_SSL=True,
        S3_ENDPOINT="https://s3.amazonaws.com",
        S3_ACCESS_KEY="valid-key",
        S3_SECRET_KEY="valid-secret-key",
    )
    with pytest.raises(RuntimeError, match="JWT_SECRET must be a long random secret in production"):
        insecure_settings.validate_production_security()

    # Production with DEBUG=True should fail
    debug_prod_settings = Settings(
        APP_ENV="production",
        DEBUG=True,
        JWT_SECRET="a" * 64,
        AUTO_CREATE_SCHEMA=False,
        S3_USE_SSL=True,
        S3_ENDPOINT="https://s3.amazonaws.com",
        S3_ACCESS_KEY="valid-key",
        S3_SECRET_KEY="valid-secret-key",
    )
    with pytest.raises(RuntimeError, match="DEBUG must be false in production"):
        debug_prod_settings.validate_production_security()


@pytest.mark.asyncio
async def test_cors_headers_for_allowed_origin():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.options(
            "/api/v1/auth/login",
            headers={
                "Origin": "https://rivu-ai-murex.vercel.app",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )
        assert response.headers.get("access-control-allow-origin") == "https://rivu-ai-murex.vercel.app"


@pytest.mark.asyncio
async def test_auth_signup_validation_weak_password():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Missing uppercase and number
        response = await client.post(
            "/api/v1/auth/signup",
            json={"email": "tester@example.com", "username": "validuser", "password": "weakpassword"},
        )
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_auth_refresh_missing_token():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/auth/refresh", json={})
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_dataset_and_report_endpoints_require_auth():
    test_uuid = "00000000-0000-0000-0000-000000000001"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r_profile = await client.get(f"/api/v1/datasets/{test_uuid}/profile")
        assert r_profile.status_code == 401

        r_quality = await client.get(f"/api/v1/datasets/{test_uuid}/quality")
        assert r_quality.status_code == 401

        r_report = await client.get(f"/api/v1/reports/{test_uuid}/pdf")
        assert r_report.status_code == 401


def test_file_format_detection_and_rejection():
    from app.ingestion.parser import detect_file_format
    from app.core.exceptions import ValidationError

    assert detect_file_format("data.csv", "text/csv") == "csv"
    assert detect_file_format("sheet.XLSX", "application/vnd.ms-excel") == "xlsx"
    assert detect_file_format("records.json", "application/json") == "json"
    assert detect_file_format("warehouse.parquet", "application/octet-stream") == "parquet"

    with pytest.raises(ValidationError, match="Unsupported file format"):
        detect_file_format("malware.exe", "application/octet-stream")

