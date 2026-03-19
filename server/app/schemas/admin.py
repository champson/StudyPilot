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
    corrected_by: int

    model_config = {"from_attributes": True}


class OcrCorrectionRequest(BaseModel):
    upload_id: int
    corrected_content: dict
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
