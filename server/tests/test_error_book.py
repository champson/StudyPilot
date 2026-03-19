import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.error_book import ErrorBook


@pytest.mark.asyncio
async def test_list_errors_empty(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['student_token']}"}
    resp = await client.get("/api/v1/student/errors", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["total"] == 0


@pytest.mark.asyncio
async def test_error_summary(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['student_token']}"}
    resp = await client.get("/api/v1/student/errors/summary", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "total" in data
    assert "by_subject" in data


@pytest.mark.asyncio
async def test_error_detail_not_found(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['student_token']}"}
    resp = await client.get("/api/v1/student/errors/999", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_recall_error(client: AsyncClient, seed_data: dict, db_session: AsyncSession):
    # Create an error book entry
    error = ErrorBook(
        student_id=seed_data["profile"].id,
        subject_id=seed_data["subjects"][0].id,
        question_content={"text": "1+1=?"},
        knowledge_points=["basic_math"],
        entry_reason="upload",
    )
    db_session.add(error)
    await db_session.flush()

    headers = {"Authorization": f"Bearer {seed_data['student_token']}"}
    resp = await client.post(
        f"/api/v1/student/errors/{error.id}/recall",
        headers=headers,
        json={"result": "correct"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["is_recalled"] is True
    assert data["recall_count"] == 1
