from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ErrorBookOut(BaseModel):
    id: int
    student_id: int
    subject_id: int
    question_content: dict
    question_image_url: str | None = None
    knowledge_points: list = []
    error_type: str | None = None
    entry_reason: str
    content_hash: str | None = None
    is_explained: bool
    is_recalled: bool
    last_recall_at: datetime | None = None
    last_recall_result: str | None = None
    recall_count: int
    source_upload_id: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ErrorSubjectSummary(BaseModel):
    subject_id: int
    subject_name: str
    count: int
    unrecalled: int


class ErrorSummaryOut(BaseModel):
    total: int
    unrecalled: int
    by_subject: list[ErrorSubjectSummary]
    by_error_type: dict[str, int]


class RecallResult(BaseModel):
    result: Literal["success", "fail"]


class RecallScheduleOut(BaseModel):
    error_id: int
    recall_scheduled: bool
    message: str


class BatchRecallRequest(BaseModel):
    error_ids: list[int] = Field(min_length=1, max_length=20)


class BatchRecallOut(BaseModel):
    scheduled_count: int
    error_ids: list[int]
