import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.qa import QaMessage
from app.services.qa import chat_stream


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
    # Verify SSE events are structured JSON
    import json

    body = resp.text
    lines = [line for line in body.split("\n") if line.startswith("data: ")]
    # Should have chunk events, knowledge_points, strategy, and [DONE]
    assert len(lines) >= 4
    # Last line is [DONE]
    assert lines[-1] == "data: [DONE]"
    # Check a chunk event
    first_event = json.loads(lines[0].removeprefix("data: "))
    assert first_event["type"] == "chunk"
    assert "content" in first_event
    # Check knowledge_points event
    kp_line = [line for line in lines if "knowledge_points" in line]
    assert len(kp_line) == 1
    kp_event = json.loads(kp_line[0].removeprefix("data: "))
    assert kp_event["type"] == "knowledge_points"
    assert isinstance(kp_event["data"], list)


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


@pytest.mark.asyncio
async def test_chat_stream_does_not_switch_to_fallback_after_partial_output(
    db_session, seed_data, monkeypatch
):
    async def fake_classify_intent(**kwargs):
        return {"intent": "concept_question", "route_to": "tutoring"}

    class FakeRouter:
        def invoke_stream(self, *args, **kwargs):
            async def gen():
                yield "先看题干"
                yield "，先列条件"
                raise RuntimeError("stream interrupted")

            return gen()

    async def fake_assess_and_apply(*args, **kwargs):
        return None

    monkeypatch.setattr("app.services.qa.classify_intent", fake_classify_intent)
    monkeypatch.setattr("app.services.qa.get_model_router", lambda: FakeRouter())
    monkeypatch.setattr("app.services.qa._assess_and_apply", fake_assess_and_apply)

    session, stream = await chat_stream(
        db_session,
        student_id=seed_data["profile"].id,
        session_id=None,
        message="这题怎么做",
        subject_id=seed_data["subjects"][1].id,
        task_id=None,
        attachments=[],
    )
    events = [event async for event in stream]
    body = "".join(events)

    assert "先别急着直接求答案" not in body
    assert "先看题干" in body
    assert "data: [DONE]" in body

    result = await db_session.execute(
        select(QaMessage)
        .where(QaMessage.session_id == session.id, QaMessage.role == "assistant")
        .order_by(QaMessage.id.desc())
    )
    assistant_message = result.scalars().first()
    assert assistant_message is not None
    assert assistant_message.content == "先看题干，先列条件"
