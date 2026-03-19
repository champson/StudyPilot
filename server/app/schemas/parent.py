from datetime import date, datetime

from pydantic import BaseModel


class ParentWeeklyReportOut(BaseModel):
    id: int
    student_id: int
    report_week: str
    usage_days: int | None = None
    total_minutes: int | None = None
    content: dict
    created_at: datetime

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
