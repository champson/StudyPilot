from datetime import date, datetime

from pydantic import BaseModel, Field


class RecommendedSubjectOut(BaseModel):
    subject_id: int
    subject_name: str | None = None
    reasons: list[str] = Field(default_factory=list)


class PlanTaskOut(BaseModel):
    id: int
    plan_id: int
    subject_id: int
    subject_name: str | None = None
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
    recommended_subjects: list[RecommendedSubjectOut] = Field(default_factory=list)
    plan_content: dict
    status: str
    warning: str | None = None
    created_at: datetime
    tasks: list[PlanTaskOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class PlanGenerateRequest(BaseModel):
    available_minutes: int = 120
    learning_mode: str | None = None
    force_regenerate: bool = False


class PlanModeUpdate(BaseModel):
    learning_mode: str


class TaskStatusUpdate(BaseModel):
    status: str
