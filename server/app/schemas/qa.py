from datetime import date, datetime

from pydantic import BaseModel


class QaMessageOut(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    attachments: list | None = []
    intent: str | None = None
    related_question_id: int | None = None
    knowledge_points: list | None = []
    tutoring_strategy: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class QaSessionOut(BaseModel):
    id: int
    student_id: int
    session_date: date
    task_id: int | None = None
    subject_id: int | None = None
    status: str
    structured_summary: dict | None = None
    created_at: datetime
    closed_at: datetime | None = None
    messages: list[QaMessageOut] = []

    model_config = {"from_attributes": True}


class QaSessionListItem(BaseModel):
    id: int
    session_date: date
    subject_id: int | None = None
    status: str
    created_at: datetime
    message_count: int = 0

    model_config = {"from_attributes": True}


class ChatRequest(BaseModel):
    session_id: int | None = None
    message: str
    subject_id: int | None = None
    task_id: int | None = None
    attachments: list = []


class ChatResponse(BaseModel):
    session_id: int
    user_message: QaMessageOut
    assistant_message: QaMessageOut
