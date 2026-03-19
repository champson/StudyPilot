import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_chat_sync(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['student_token']}"}
    resp = await client.post(
        "/api/v1/student/qa/chat",
        headers=headers,
        json={"message": "这道题怎么做？", "subject_id": 1},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["session_id"] is not None
    assert data["user_message"]["role"] == "user"
    assert data["assistant_message"]["role"] == "assistant"


@pytest.mark.asyncio
async def test_chat_stream(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['student_token']}"}
    resp = await client.post(
        "/api/v1/student/qa/chat/stream",
        headers=headers,
        json={"message": "解释一下"},
    )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_qa_history(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['student_token']}"}
    # Create a session first
    await client.post(
        "/api/v1/student/qa/chat",
        headers=headers,
        json={"message": "test"},
    )
    resp = await client.get("/api/v1/student/qa/history", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["total"] >= 1


@pytest.mark.asyncio
async def test_session_detail(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['student_token']}"}
    chat_resp = await client.post(
        "/api/v1/student/qa/chat",
        headers=headers,
        json={"message": "test detail"},
    )
    session_id = chat_resp.json()["data"]["session_id"]

    resp = await client.get(
        f"/api/v1/student/qa/sessions/{session_id}", headers=headers
    )
    assert resp.status_code == 200
    assert len(resp.json()["data"]["messages"]) == 2
