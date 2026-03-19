from datetime import date, datetime

from pydantic import BaseModel


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
    subject_combination: list = []


class StudentProfileUpdate(BaseModel):
    grade: str | None = None
    textbook_version: str | None = None
    class_rank: int | None = None
    grade_rank: int | None = None
    subject_combination: list | None = None
    upcoming_exams: list | None = None
    current_progress: dict | None = None


class OnboardingSubmit(BaseModel):
    weak_subjects: list[int] = []
    low_score_subjects: list[int] = []
    available_minutes_weekday: int = 120
    available_minutes_weekend: int = 180
    study_goals: str | None = None
    extra: dict = {}


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
