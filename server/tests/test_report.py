import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_weekly_report_not_found(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['student_token']}"}
    resp = await client.get("/api/v1/student/report/weekly", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_weekly_summaries_empty(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['student_token']}"}
    resp = await client.get("/api/v1/student/report/weekly/summary", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"] == []
