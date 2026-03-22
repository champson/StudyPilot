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
    schedule_resp = await client.post(
        f"/api/v1/student/errors/{error.id}/recall",
        headers=headers,
    )
    assert schedule_resp.status_code == 200
    assert schedule_resp.json()["data"]["recall_scheduled"] is True

    resp = await client.post(
        f"/api/v1/student/errors/{error.id}/recall-result",
        headers=headers,
        json={"result": "success"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["is_recalled"] is True
    assert data["recall_count"] == 1
    assert data["last_recall_result"] == "success"


@pytest.mark.asyncio
async def test_batch_recall_schedule_only(
    client: AsyncClient, seed_data: dict, db_session: AsyncSession
):
    errors = [
        ErrorBook(
            student_id=seed_data["profile"].id,
            subject_id=seed_data["subjects"][0].id,
            question_content={"text": f"1+{idx}= ?"},
            knowledge_points=["basic_math"],
            entry_reason="upload",
        )
        for idx in range(2)
    ]
    db_session.add_all(errors)
    await db_session.flush()

    headers = {"Authorization": f"Bearer {seed_data['student_token']}"}
    resp = await client.post(
        "/api/v1/student/errors/batch-recall",
        headers=headers,
        json={"error_ids": [errors[0].id, errors[1].id]},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["scheduled_count"] == 2
    assert data["error_ids"] == [errors[0].id, errors[1].id]

    await db_session.refresh(errors[0])
    await db_session.refresh(errors[1])
    assert errors[0].recall_count == 0
    assert errors[1].recall_count == 0


@pytest.mark.asyncio
async def test_failed_recall_keeps_error_pending(
    client: AsyncClient, seed_data: dict, db_session: AsyncSession
):
    error = ErrorBook(
        student_id=seed_data["profile"].id,
        subject_id=seed_data["subjects"][1].id,
        question_content={"text": "导数定义"},
        knowledge_points=[
            {
                "id": seed_data["knowledge_points"][1].id,
                "name": "导数定义",
            }
        ],
        entry_reason="upload",
    )
    db_session.add(error)
    await db_session.flush()

    headers = {"Authorization": f"Bearer {seed_data['student_token']}"}
    resp = await client.post(
        f"/api/v1/student/errors/{error.id}/recall-result",
        headers=headers,
        json={"result": "fail"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["is_recalled"] is False
    assert data["last_recall_result"] == "fail"
