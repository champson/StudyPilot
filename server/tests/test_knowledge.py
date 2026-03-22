import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import StudentKnowledgeStatus


@pytest.mark.asyncio
async def test_knowledge_status_empty(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['student_token']}"}
    resp = await client.get("/api/v1/student/knowledge/status", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 0
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_knowledge_status_filter(
    client: AsyncClient, seed_data: dict, db_session: AsyncSession
):
    db_session.add(
        StudentKnowledgeStatus(
            student_id=seed_data["profile"].id,
            knowledge_point_id=seed_data["knowledge_points"][2].id,
            status="反复失误",
        )
    )
    await db_session.flush()

    headers = {"Authorization": f"Bearer {seed_data['student_token']}"}
    resp = await client.get(
        (
            "/api/v1/student/knowledge/status"
            f"?subject_id={seed_data['subjects'][3].id}&status=反复失误&min_importance=0"
        ),
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 1
    assert data["by_status"]["反复失误"] == 1
    assert data["items"][0]["knowledge_point_id"] == seed_data["knowledge_points"][2].id
