"""API integration tests for /api/v1/catalogue endpoints."""

import io
import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.catalogue.auth import get_current_catalogue_user
from app.catalogue.auth_db import get_catalogue_session


from unittest.mock import AsyncMock, Mock

async def dummy_session():
    mock_session = AsyncMock()
    class EmptyResult:
        def scalar_one_or_none(self):
            return None
        def scalars(self):
            return self
        def all(self):
            return []
    mock_session.execute = AsyncMock(return_value=EmptyResult())
    mock_session.add = Mock()
    yield mock_session

app.dependency_overrides[get_catalogue_session] = dummy_session


class MockUser:
    id = uuid.uuid4()
    email = "merchandiser@waterting.com"
    username = "merchandiser"
    status = "active"
    active_org_id = uuid.uuid4()
    active_workspace_id = active_org_id


class MockMembership:
    id = uuid.uuid4()
    organization_id = MockUser.active_org_id
    user_id = MockUser.id
    role = "editor"


@pytest.mark.asyncio
async def test_catalogue_unauthenticated_access_blocked():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Upload requires auth
        res = await client.post("/api/v1/catalogue/upload")
        assert res.status_code == 401

        # Map requires auth
        res = await client.post("/api/v1/catalogue/map", json={"raw_records": [], "mappings": []})
        assert res.status_code == 401

        # Export requires auth
        res = await client.post("/api/v1/catalogue/export", json={"products": []})
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_catalogue_upload_and_mapping_pipeline(monkeypatch):
    async def mock_require_catalogue_role(user, db, roles):
        return MockMembership()

    monkeypatch.setattr("app.catalogue.router.require_catalogue_role", mock_require_catalogue_role)
    app.dependency_overrides[get_current_catalogue_user] = lambda: MockUser()

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. Fetch available templates
            tmpl_res = await client.get("/api/v1/catalogue/templates")
            assert tmpl_res.status_code == 200
            templates = tmpl_res.json()
            assert any(t["id"] == "shopify" for t in templates)
            assert any(t["id"] == "standard_ecommerce" for t in templates)

            # 2. Upload CSV catalogue
            csv_content = ("Part Number,Product Name,MSRP,Stock,Brand\n" + "\n".join(
                f"WDG-{i:03d},Product {i},$45.00,100,WaterTing" for i in range(1, 13)
            ) + "\n").encode("utf-8")

            files = {"file": ("catalogue.csv", io.BytesIO(csv_content), "text/csv")}
            up_res = await client.post("/api/v1/catalogue/upload", files=files)
            assert up_res.status_code == 200
            upload_data = up_res.json()

            assert upload_data["row_count"] == 12
            assert len(upload_data["raw_records"]) == upload_data["row_count"]
            assert "Part Number" in upload_data["columns"]
            suggested = upload_data["suggested_mappings"]
            assert len(suggested) >= 4

            # 3. Apply field mappings
            map_payload = {
                "raw_records": upload_data["raw_records"],
                "mappings": suggested,
                "template_id": "shopify",
            }
            map_res = await client.post("/api/v1/catalogue/map", json=map_payload)
            assert map_res.status_code == 200
            map_data = map_res.json()
            products = map_data["products"]
            assert len(products) == 12
            assert products[0]["sku"] == "WDG-001"
            assert products[0]["price"] == 45.0
            assert map_data["validation_summary"]["valid_records"] == 12

            # 4. Preview Export
            exp_preview_res = await client.post(
                "/api/v1/catalogue/export/preview",
                json={
                    "products": products,
                    "template_id": "shopify",
                    "format": "xlsx",
                },
            )
            assert exp_preview_res.status_code == 200
            prev_data = exp_preview_res.json()
            assert "Handle" in prev_data["output_columns"]
            assert prev_data["total_records"] == 12

            # 5. Export XLSX file
            exp_res = await client.post(
                "/api/v1/catalogue/export",
                json={
                    "products": products,
                    "template_id": "shopify",
                    "format": "xlsx",
                },
            )
            assert exp_res.status_code == 200
            assert "application/vnd.openxmlformats" in exp_res.headers["content-type"]
            assert len(exp_res.content) > 0

            # 6. Export CSV file
            exp_csv_res = await client.post(
                "/api/v1/catalogue/export",
                json={
                    "products": products,
                    "template_id": "standard_ecommerce",
                    "format": "csv",
                },
            )
            assert exp_csv_res.status_code == 200
            assert "text/csv" in exp_csv_res.headers["content-type"]
            assert "WDG-001" in exp_csv_res.text
            assert "WDG-012" in exp_csv_res.text
    finally:
        app.dependency_overrides.pop(get_current_catalogue_user, None)
