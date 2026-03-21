from datetime import date, datetime

from pydantic import BaseModel


class SubjectRisk(BaseModel):
    subject_id: int
    subject_name: str
    risk_level: str
    effective_week: str


class RiskPoint(BaseModel):
    name: str
    subject_name: str


class RepeatedError(BaseModel):
    name: str
    error_count: int


class RiskSummary(BaseModel):
    high_risk_points: list[RiskPoint] = []
    repeated_errors: list[RepeatedError] = []


class ParentWeeklyReportOut(BaseModel):
    report_week: str
    student_name: str | None = None
    usage_days: int | None = None
    total_minutes: int | None = None
    task_completion_rate: float | None = None
    subject_risks: list[SubjectRisk] = []
    trend_description: str | None = None
    action_suggestions: list[str] = []
    class_rank: int | None = None
    grade_rank: int | None = None
    share_token: str | None = None
    created_at: datetime
    # Phase 5 enhancements
    avg_daily_minutes: int | None = None
    risk_summary: RiskSummary | None = None
    parent_support_suggestions: list[str] = []
    previous_usage_days: int | None = None
    previous_total_minutes: int | None = None
    previous_task_completion_rate: float | None = None

    model_config = {"from_attributes": True}


class RiskOverviewOut(BaseModel):
    student_id: int
    risks: list[dict]


class TrendOut(BaseModel):
    student_id: int
    weeks: list[dict]


class SupplementRequest(BaseModel):
    grade: str | None = None
    textbook_version: str | None = None
    subject_combination: list | None = None


class ExamRecordRequest(BaseModel):
    exam_type: str
    exam_date: date
    subject_id: int
    score: float | None = None
    full_score: float | None = 100
    class_rank: int | None = None
    grade_rank: int | None = None
