from datetime import datetime

from pydantic import BaseModel


class SubjectTrend(BaseModel):
    subject_name: str
    risk_level: str
    trend: str  # "improving" | "stable" | "declining"


class HighRiskKnowledgePoint(BaseModel):
    name: str
    subject_name: str
    status: str


class RepeatedErrorPoint(BaseModel):
    name: str
    error_count: int


class WeeklyReportOut(BaseModel):
    """Student view of weekly report, matching api-contract WeeklyReportStudent."""
    id: int
    student_id: int
    report_week: str
    usage_days: int | None = None
    total_minutes: int | None = None
    task_completion_rate: float | None = None
    subject_trends: list[SubjectTrend] = []
    high_risk_knowledge_points: list[HighRiskKnowledgePoint] = []
    repeated_error_points: list[RepeatedErrorPoint] = []
    next_stage_suggestions: list[str] = []
    class_rank: int | None = None
    grade_rank: int | None = None
    share_token: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class WeeklyReportSummary(BaseModel):
    report_week: str
    usage_days: int | None = None
    total_minutes: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ShareLinkOut(BaseModel):
    share_url: str
    expires_at: datetime
    share_token: str | None = None
