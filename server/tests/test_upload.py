import io

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_upload_material(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['student_token']}"}
    file_content = b"test file content"
    resp = await client.post(
        "/api/v1/student/material/upload",
        headers=headers,
        files={"file": ("test.jpg", io.BytesIO(file_content), "image/jpeg")},
        data={"upload_type": "homework", "subject_id": "1"},
    )
    assert resp.status_code == 202
    data = resp.json()["data"]
    assert data["status"] == "pending"
    assert data["resource_id"] is not None
    assert "poll_url" in data


@pytest.mark.asyncio
async def test_list_materials(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['student_token']}"}
    resp = await client.get("/api/v1/student/material/list", headers=headers)
    assert resp.status_code == 200
    assert "items" in resp.json()["data"]


@pytest.mark.asyncio
async def test_ocr_status(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['student_token']}"}
    # Upload first
    upload_resp = await client.post(
        "/api/v1/student/material/upload",
        headers=headers,
        files={"file": ("test.jpg", io.BytesIO(b"content"), "image/jpeg")},
        data={"upload_type": "notes"},
    )
    upload_id = upload_resp.json()["data"]["resource_id"]

    resp = await client.get(
        f"/api/v1/student/material/{upload_id}/ocr-status", headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["ocr_status"] == "pending"
