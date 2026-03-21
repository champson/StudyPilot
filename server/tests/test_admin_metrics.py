import uuid
from datetime import datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system import ModelCallLog


async def _insert_call_log(
    db: AsyncSession,
    *,
    agent_name: str = "planning",
    provider: str = "dashscope",
    model: str = "qwen-turbo",
    latency_ms: int = 1200,
    success: bool = True,
    is_fallback: bool = False,
    estimated_cost: float = 0.05,
    error_message: str | None = None,
    created_at: datetime | None = None,
) -> ModelCallLog:
    log = ModelCallLog(
        request_id=uuid.uuid4(),
        agent_name=agent_name,
        mode="normal",
        provider=provider,
        model=model,
        latency_ms=latency_ms,
        input_tokens=100,
        output_tokens=50,
        is_fallback=is_fallback,
        success=success,
        estimated_cost=estimated_cost,
        error_message=error_message,
    )
    if created_at:
        log.created_at = created_at
    db.add(log)
    await db.flush()
    return log


@pytest.mark.asyncio
async def test_cost_trend_empty(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['admin_token']}"}
    resp = await client.get("/api/v1/admin/metrics/costs?period=today", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total_cost"] == 0
    assert data["daily_avg_cost"] == 0
    assert data["by_model"] == []
    assert data["trend"] == []


@pytest.mark.asyncio
async def test_cost_trend_with_data(
    client: AsyncClient, seed_data: dict, db_session: AsyncSession
):
    await _insert_call_log(db_session, estimated_cost=1.50, model="qwen-turbo")
    await _insert_call_log(db_session, estimated_cost=2.50, model="gpt-4o")

    headers = {"Authorization": f"Bearer {seed_data['admin_token']}"}
    resp = await client.get("/api/v1/admin/metrics/costs?period=today", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total_cost"] == 4.0
    assert len(data["by_model"]) == 2
    # gpt-4o should be first (higher cost)
    assert data["by_model"][0]["model"] == "gpt-4o"


@pytest.mark.asyncio
async def test_fallback_stats_empty(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['admin_token']}"}
    resp = await client.get("/api/v1/admin/metrics/fallbacks?period=today", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total_calls"] == 0
    assert data["fallback_count"] == 0
    assert data["fallback_rate"] == 0


@pytest.mark.asyncio
async def test_fallback_stats_with_data(
    client: AsyncClient, seed_data: dict, db_session: AsyncSession
):
    await _insert_call_log(db_session, is_fallback=False)
    await _insert_call_log(db_session, is_fallback=False)
    await _insert_call_log(
        db_session, is_fallback=True, error_message="request timed out"
    )
    await _insert_call_log(
        db_session, is_fallback=True, error_message="429 rate limit exceeded"
    )

    headers = {"Authorization": f"Bearer {seed_data['admin_token']}"}
    resp = await client.get("/api/v1/admin/metrics/fallbacks?period=today", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total_calls"] == 4
    assert data["fallback_count"] == 2
    assert data["fallback_rate"] == 0.5
    reasons = {r["reason"] for r in data["by_reason"]}
    assert "timeout" in reasons
    assert "rate_limit" in reasons


@pytest.mark.asyncio
async def test_error_stats_with_data(
    client: AsyncClient, seed_data: dict, db_session: AsyncSession
):
    await _insert_call_log(db_session, success=True)
    await _insert_call_log(
        db_session, success=False, error_message="model generation failed"
    )
    await _insert_call_log(
        db_session, success=False, error_message="request timed out"
    )

    headers = {"Authorization": f"Bearer {seed_data['admin_token']}"}
    resp = await client.get("/api/v1/admin/metrics/errors?period=today", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total_errors"] == 2
    types = {t["type"] for t in data["by_type"]}
    assert "model_error" in types
    assert "timeout" in types


@pytest.mark.asyncio
async def test_latency_stats_empty(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['admin_token']}"}
    resp = await client.get("/api/v1/admin/metrics/latency?period=today", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["avg_latency_ms"] == 0
    assert data["p95_latency_ms"] == 0
    assert data["p99_latency_ms"] == 0


@pytest.mark.asyncio
async def test_invalid_period_returns_400(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['admin_token']}"}
    for endpoint in ["costs", "fallbacks", "errors", "latency"]:
        resp = await client.get(
            f"/api/v1/admin/metrics/{endpoint}?period=invalid", headers=headers
        )
        assert resp.status_code == 400, f"{endpoint} should reject invalid period"


@pytest.mark.asyncio
async def test_student_cannot_access_metrics(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['student_token']}"}
    resp = await client.get("/api/v1/admin/metrics/costs?period=today", headers=headers)
    assert resp.status_code == 403
