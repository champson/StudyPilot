from datetime import datetime

from pydantic import BaseModel


class SubjectRiskOverview(BaseModel):
    subject_name: str
    risk_level: str


class ShareContentOut(BaseModel):
    student_name: str | None = None
    report_week: str
    usage_days: int | None = None
    total_minutes: int | None = None
    trend_overview: str | None = None
    subject_risk_overview: list[SubjectRiskOverview] = []
    next_stage_suggestions_summary: str | None = None
    expires_at: datetime | None = None


class ShareValidateOut(BaseModel):
    valid: bool
    report_week: str | None = None
    expires_at: datetime | None = None
