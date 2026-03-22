from datetime import datetime

from pydantic import BaseModel


class SystemModeOut(BaseModel):
    mode: str


class SystemModeUpdate(BaseModel):
    mode: str


class CorrectionOut(BaseModel):
    id: int
    target_type: str
    target_id: int
    original_content: dict | None = None
    corrected_content: dict
    correction_reason: str | None = None
    corrected_by: int | None = None
    status: str = "pending"
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class OcrCorrectionRequest(BaseModel):
    upload_id: int
    corrected_content: dict
    reason: str | None = None


class ResolveCorrectionRequest(BaseModel):
    corrected_content: dict | None = None
    reason: str | None = None


class KnowledgeCorrectionRequest(BaseModel):
    student_id: int
    knowledge_point_id: int
    new_status: str
    reason: str | None = None


class MetricsTodayOut(BaseModel):
    active_students: int
    plans_generated: int
    uploads: int
    qa_sessions: int


class HealthOut(BaseModel):
    database: str
    redis: str
    celery: str


class ModelCallsOut(BaseModel):
    total: int
    by_agent: list[dict]
    by_provider: list[dict]


# --- Phase 5: Metrics ---


class CostTrendOut(BaseModel):
    period: str
    total_cost: float
    daily_avg_cost: float
    by_model: list[dict]
    trend: list[dict]


class FallbackStatsOut(BaseModel):
    period: str
    total_calls: int
    fallback_count: int
    fallback_rate: float
    by_reason: list[dict]
    trend: list[dict]


class ErrorStatsOut(BaseModel):
    period: str
    total_errors: int
    by_type: list[dict]
    by_agent: list[dict]
    trend: list[dict]


class LatencyStatsOut(BaseModel):
    period: str
    avg_latency_ms: int
    p95_latency_ms: int
    p99_latency_ms: int
    by_agent: list[dict]


# --- Phase 5: Corrections ---


class CorrectionDetailOut(CorrectionOut):
    context: dict | None = None


class PendingCountByTypeOut(BaseModel):
    ocr: int = 0
    knowledge: int = 0
    plan: int = 0
    qa: int = 0
    total: int = 0


class PlanCorrectionRequest(BaseModel):
    plan_id: int
    corrected_tasks: list[dict]
    reason: str | None = None
