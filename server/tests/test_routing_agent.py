import pytest

from app.llm.agents.routing import classify_intent


class FakeRouter:
    async def invoke(self, *args, **kwargs):
        return '{"intent":"follow_up","confidence":0.91,"route_to":"tutoring"}', {}


@pytest.mark.asyncio
async def test_routing_agent_parses_llm_json(monkeypatch):
    monkeypatch.setattr("app.llm.agents.routing.get_model_router", lambda: FakeRouter())
    result = await classify_intent(
        message="那下一步呢？",
        has_attachments=False,
        session_context="已有会话追问",
    )
    assert result["intent"] == "follow_up"
    assert result["route_to"] == "tutoring"


@pytest.mark.asyncio
async def test_routing_agent_uses_heuristic_on_failure(monkeypatch):
    class BrokenRouter:
        async def invoke(self, *args, **kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr("app.llm.agents.routing.get_model_router", lambda: BrokenRouter())
    result = await classify_intent(
        message="帮我看看这张题图",
        has_attachments=True,
        session_context="新会话",
    )
    assert result["intent"] == "upload_question"
