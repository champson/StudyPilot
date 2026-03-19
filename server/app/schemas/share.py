from datetime import datetime

from pydantic import BaseModel


class ShareContentOut(BaseModel):
    student_nickname: str | None = None
    report_week: str
    summary: dict
    expires_at: datetime | None = None


class ShareValidateOut(BaseModel):
    valid: bool
    report_week: str | None = None
    expires_at: datetime | None = None
