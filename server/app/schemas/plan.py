from datetime import date, datetime

from pydantic import BaseModel


class PlanTaskOut(BaseModel):
    id: int
    plan_id: int
    subject_id: int
    task_type: str
    task_content: dict
    sequence: int
    estimated_minutes: int | None = None
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_minutes: int | None = None

    model_config = {"from_attributes": True}


class DailyPlanOut(BaseModel):
    id: int
    student_id: int
    plan_date: date
    learning_mode: str
    system_recommended_mode: str | None = None
    available_minutes: int
    source: str
    is_history_inferred: bool
    recommended_subjects: dict
    plan_content: dict
    status: str
    created_at: datetime
    tasks: list[PlanTaskOut] = []

    model_config = {"from_attributes": True}


class PlanGenerateRequest(BaseModel):
    available_minutes: int = 120
    learning_mode: str | None = None


class PlanModeUpdate(BaseModel):
    learning_mode: str


class TaskStatusUpdate(BaseModel):
    status: str
