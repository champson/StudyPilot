import pytest

from app.core.redis import set_redis_client_for_testing
from app.llm.model_router import ModelRouter, get_model_router, reset_model_router


class FakeRedis:
    def __init__(self, data=None):
        self.data = data or {}

    async def get(self, key):
        return self.data.get(key)


@pytest.mark.asyncio
async def test_model_router_reads_mode_from_redis():
    router = ModelRouter(
        "config/model_config.yaml",
        redis_client=FakeRedis({"system:run_mode": "best"}),
    )
    assert await router.current_mode() == "best"


@pytest.mark.asyncio
async def test_get_model_router_uses_shared_redis_client():
    set_redis_client_for_testing(FakeRedis({"system:run_mode": "best"}))
    reset_model_router()
    try:
        router = get_model_router()
        assert await router.current_mode() == "best"
    finally:
        reset_model_router()
        set_redis_client_for_testing(None)


@pytest.mark.asyncio
async def test_model_router_falls_back_to_alternate_mode(monkeypatch):
    router = ModelRouter(
        "config/model_config.yaml",
        redis_client=FakeRedis({"system:run_mode": "normal"}),
    )
    calls = []

    async def fake_call(cfg, messages, **kwargs):
        calls.append(cfg["model"])
        if len(calls) == 1:
            raise RuntimeError("primary failed")
        return "{}", {"input_tokens": 12, "output_tokens": 8}

    monkeypatch.setattr(router, "_call_with_config", fake_call)

    content, meta = await router.invoke("planning", [{"role": "user", "content": "test"}])
    assert content == "{}"
    assert meta["mode"] == "best"
    assert meta["is_fallback"] is True
    assert len(calls) == 2
