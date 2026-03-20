from datetime import date, datetime

from pydantic import BaseModel, Field


class StudentProfileOut(BaseModel):
    id: int
    user_id: int
    grade: str
    textbook_version: str | None = None
    class_rank: int | None = None
    grade_rank: int | None = None
    subject_combination: list = []
    upcoming_exams: list | None = []
    current_progress: dict | None = {}
    onboarding_completed: bool
    onboarding_data: dict | None = {}
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StudentProfileCreate(BaseModel):
    grade: str
    textbook_version: str | None = None
    subject_combination: list = Field(default_factory=list)


class StudentProfileUpdate(BaseModel):
    grade: str | None = None
    textbook_version: str | None = None
    class_rank: int | None = None
    grade_rank: int | None = None
    subject_combination: list | None = None
    upcoming_exams: list | None = None
    current_progress: dict | None = None


class OnboardingSubmit(BaseModel):
    grade: str | None = None
    textbook_version: str | dict | None = None
    subject_combination: list[str | int] = Field(default_factory=list)
    weak_subjects: list[int | str] = Field(default_factory=list)
    low_score_subjects: list[int | str] = Field(default_factory=list)
    recent_exam_scores: dict[str, float] = Field(default_factory=dict)
    error_types_by_subject: dict[str, list[str]] = Field(default_factory=dict)
    available_minutes_weekday: int = 120
    available_minutes_weekend: int = 180
    daily_study_minutes: int | None = None
    study_goals: str | None = None
    upcoming_exam_date: date | None = None
    extra: dict = Field(default_factory=dict)


class InitializedSubjectRiskOut(BaseModel):
    subject_id: int | None = None
    subject_code: str
    risk_level: str


class OnboardingSubmitOut(BaseModel):
    onboarding_completed: bool
    initialized_knowledge_points: int
    initialized_subject_risks: list[InitializedSubjectRiskOut] = Field(default_factory=list)


class OnboardingStatusOut(BaseModel):
    onboarding_completed: bool


class ExamRecordCreate(BaseModel):
    exam_type: str
    exam_date: date
    subject_id: int
    score: float | None = None
    full_score: float | None = 100
    class_rank: int | None = None
    grade_rank: int | None = None


class ExamRecordOut(BaseModel):
    id: int
    student_id: int
    exam_type: str
    exam_date: date
    subject_id: int
    score: float | None = None
    full_score: float | None = None
    class_rank: int | None = None
    grade_rank: int | None = None
    created_at: datetime
    created_by: str | None = None

    model_config = {"from_attributes": True}
