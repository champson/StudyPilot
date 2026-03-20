from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system import ModelCallLog

MODEL_PRICING = {
    "qwen-vl-max": {"input": 0.020, "output": 0.020},
    "qwen-max": {"input": 0.020, "output": 0.060},
    "qwen-turbo": {"input": 0.002, "output": 0.006},
    "deepseek-chat": {"input": 0.001, "output": 0.002},
    "claude-sonnet-4-20250514": {"input": 0.021, "output": 0.105},
    "gpt-4o": {"input": 0.035, "output": 0.105},
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = MODEL_PRICING.get(model, {"input": 0.0, "output": 0.0})
    return (
        input_tokens * pricing["input"] + output_tokens * pricing["output"]
    ) / 1000


async def log_model_call(
    db: AsyncSession,
    *,
    request_id: UUID,
    student_id: int | None,
    agent_name: str,
    mode: str,
    provider: str,
    model: str,
    latency_ms: int,
    input_tokens: int,
    output_tokens: int,
    is_fallback: bool,
    success: bool,
    error_message: str | None = None,
) -> ModelCallLog:
    log = ModelCallLog(
        request_id=request_id,
        student_id=student_id,
        agent_name=agent_name,
        mode=mode,
        provider=provider,
        model=model,
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        is_fallback=is_fallback,
        success=success,
        error_message=error_message,
        estimated_cost=estimate_cost(model, input_tokens, output_tokens),
    )
    db.add(log)
    await db.flush()
    return log
