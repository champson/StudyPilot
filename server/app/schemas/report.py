from datetime import datetime

from pydantic import BaseModel


class WeeklyReportOut(BaseModel):
    id: int
    student_id: int
    report_week: str
    usage_days: int | None = None
    total_minutes: int | None = None
    content: dict
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
