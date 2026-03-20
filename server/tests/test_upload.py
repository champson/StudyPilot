import io

import pytest
from httpx import AsyncClient
from starlette.datastructures import UploadFile

from app.services.upload import handle_upload


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


@pytest.mark.asyncio
async def test_upload_sync_fallback_runs_inline(db_session, seed_data, tmp_path, monkeypatch):
    called = {}

    async def fake_inline(db, upload, *, raise_on_error=False):
        called["upload_id"] = upload.id
        upload.ocr_status = "completed"
        upload.ocr_result = {"ok": True}
        await db.flush()

    monkeypatch.setattr("app.services.upload.settings.OCR_SYNC_FALLBACK", True)
    monkeypatch.setattr("app.services.upload.run_ocr_pipeline_inline", fake_inline)
    monkeypatch.setattr("app.services.upload.settings.UPLOAD_DIR", str(tmp_path))

    upload_file = UploadFile(filename="test.png", file=io.BytesIO(b"fake-image"))
    upload = await handle_upload(
        db_session,
        seed_data["profile"].id,
        upload_file,
        "homework",
        seed_data["subjects"][1].id,
    )

    assert called["upload_id"] == upload.id
    assert upload.ocr_status == "completed"
    assert upload.ocr_result == {"ok": True}
