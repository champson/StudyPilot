import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_admin_metrics_today(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['admin_token']}"}
    resp = await client.get("/api/v1/admin/metrics/today", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "active_students" in data
    assert "plans_generated" in data


@pytest.mark.asyncio
async def test_admin_model_calls(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['admin_token']}"}
    resp = await client.get("/api/v1/admin/metrics/model-calls", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "total" in data


@pytest.mark.asyncio
async def test_admin_corrections_pending(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['admin_token']}"}
    resp = await client.get("/api/v1/admin/corrections/pending", headers=headers)
    assert resp.status_code == 200
    assert "items" in resp.json()["data"]


@pytest.mark.asyncio
async def test_student_cannot_access_admin(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['student_token']}"}
    resp = await client.get("/api/v1/admin/metrics/today", headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_parent_cannot_access_admin(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['parent_token']}"}
    resp = await client.get("/api/v1/admin/metrics/today", headers=headers)
    assert resp.status_code == 403
