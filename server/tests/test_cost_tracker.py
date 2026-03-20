from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.cost_tracker import estimate_cost, log_model_call
from app.models.system import ModelCallLog


@pytest.mark.asyncio
async def test_estimate_cost():
    cost = estimate_cost("qwen-max", 1000, 500)
    assert float(cost) > 0


@pytest.mark.asyncio
async def test_log_model_call_persists(
    db_session: AsyncSession, seed_data: dict
):
    request_id = uuid4()
    await log_model_call(
        db_session,
        request_id=request_id,
        student_id=seed_data["profile"].id,
        agent_name="planning",
        mode="normal",
        provider="dashscope",
        model="qwen-max",
        latency_ms=120,
        input_tokens=100,
        output_tokens=50,
        is_fallback=False,
        success=True,
    )

    result = await db_session.execute(
        select(ModelCallLog).where(ModelCallLog.request_id == request_id)
    )
    log = result.scalar_one()
    assert log.agent_name == "planning"
    assert float(log.estimated_cost) > 0
