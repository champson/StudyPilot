import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_parent_risk_overview(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['parent_token']}"}
    resp = await client.get("/api/v1/parent/profile/risk", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "risks" in data


@pytest.mark.asyncio
async def test_parent_trend(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['parent_token']}"}
    resp = await client.get("/api/v1/parent/profile/trend", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "weeks" in data


@pytest.mark.asyncio
async def test_parent_supplement(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['parent_token']}"}
    resp = await client.post(
        "/api/v1/parent/profile/supplement",
        headers=headers,
        json={"textbook_version": "沪教版"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_parent_exam_record(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['parent_token']}"}
    resp = await client.post(
        "/api/v1/parent/exam/record",
        headers=headers,
        json={
            "exam_type": "月考",
            "exam_date": "2026-03-15",
            "subject_id": 1,
            "score": 85.5,
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["created_by"] == "parent"


@pytest.mark.asyncio
async def test_parent_cannot_access_student_endpoints(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['parent_token']}"}
    resp = await client.get("/api/v1/student/profile", headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_student_cannot_access_parent_endpoints(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['student_token']}"}
    resp = await client.get("/api/v1/parent/profile/risk", headers=headers)
    assert resp.status_code == 403
