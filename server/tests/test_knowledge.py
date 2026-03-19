import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_knowledge_status_empty(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['student_token']}"}
    resp = await client.get("/api/v1/student/knowledge/status", headers=headers)
    assert resp.status_code == 200
    assert isinstance(resp.json()["data"], list)


@pytest.mark.asyncio
async def test_knowledge_status_filter(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['student_token']}"}
    resp = await client.get(
        "/api/v1/student/knowledge/status?subject_id=1", headers=headers
    )
    assert resp.status_code == 200
