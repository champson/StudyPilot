from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.student_profile import StudentProfile
from app.models.subject import Subject
from app.schemas.student_profile import (
    OnboardingSubmit,
    StudentProfileCreate,
    StudentProfileUpdate,
)
from app.services.knowledge import batch_init_from_onboarding


async def get_profile(db: AsyncSession, student_id: int) -> StudentProfile:
    result = await db.execute(
        select(StudentProfile).where(StudentProfile.id == student_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise AppError("PROFILE_NOT_FOUND", "学生档案不存在", status_code=404)
    return profile


async def create_profile(
    db: AsyncSession, user_id: int, data: StudentProfileCreate
) -> StudentProfile:
    existing = await db.execute(
        select(StudentProfile).where(StudentProfile.user_id == user_id)
    )
    if existing.scalar_one_or_none():
        raise AppError("PROFILE_EXISTS", "档案已存在", status_code=409)

    profile = StudentProfile(
        user_id=user_id,
        grade=data.grade,
        textbook_version=data.textbook_version,
        subject_combination=data.subject_combination,
    )
    db.add(profile)
    await db.flush()
    return profile


async def update_profile(
    db: AsyncSession, student_id: int, data: StudentProfileUpdate
) -> StudentProfile:
    profile = await get_profile(db, student_id)
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(profile, key, value)
    await db.flush()
    return profile


async def submit_onboarding(
    db: AsyncSession, student_id: int, data: OnboardingSubmit
) -> dict:
    profile = await get_profile(db, student_id)
    if profile.onboarding_completed:
        raise AppError(
            "ONBOARDING_ALREADY_COMPLETED",
            "入学问卷已完成，如需修改请联系管理员",
            status_code=409,
            detail={"completed_at": profile.updated_at.isoformat() if profile.updated_at else None},
        )

    payload = data.model_dump(mode="json")
    profile.onboarding_data = payload

    if data.grade:
        profile.grade = data.grade
    if isinstance(data.textbook_version, str):
        profile.textbook_version = data.textbook_version
    if data.subject_combination:
        profile.subject_combination = list(data.subject_combination)
    if data.upcoming_exam_date:
        profile.upcoming_exams = [{"date": data.upcoming_exam_date.isoformat()}]

    weak_subject_ids = await _resolve_subject_ids(db, data.weak_subjects)
    low_score_subject_ids = await _resolve_subject_ids(db, data.low_score_subjects)
    recent_exam_scores = await _resolve_exam_scores(db, data.recent_exam_scores)
    for subject_id in low_score_subject_ids:
        recent_exam_scores.setdefault(subject_id, 59.0)

    init_result = await batch_init_from_onboarding(
        db,
        student_id=student_id,
        weak_subject_ids=weak_subject_ids,
        recent_exam_scores=recent_exam_scores,
    )

    profile.onboarding_completed = True
    await db.flush()
    return {
        "onboarding_completed": True,
        "initialized_knowledge_points": init_result["initialized_knowledge_points"],
        "initialized_subject_risks": init_result["initialized_subject_risks"],
    }


async def get_onboarding_status(db: AsyncSession, student_id: int) -> bool:
    profile = await get_profile(db, student_id)
    return profile.onboarding_completed


async def _resolve_subject_ids(
    db: AsyncSession, refs: list[int | str]
) -> list[int]:
    if not refs:
        return []
    result = await db.execute(select(Subject))
    subjects = result.scalars().all()
    by_id = {str(subject.id): subject.id for subject in subjects}
    by_code = {subject.code: subject.id for subject in subjects}
    by_name = {subject.name: subject.id for subject in subjects}

    resolved: list[int] = []
    for ref in refs:
        key = str(ref)
        subject_id = by_id.get(key) or by_code.get(key) or by_name.get(key)
        if subject_id is not None and subject_id not in resolved:
            resolved.append(subject_id)
    return resolved


async def _resolve_exam_scores(
    db: AsyncSession, raw_scores: dict[str, float]
) -> dict[int, float]:
    if not raw_scores:
        return {}
    result = await db.execute(select(Subject))
    subjects = result.scalars().all()
    by_code = {subject.code: subject.id for subject in subjects}
    by_name = {subject.name: subject.id for subject in subjects}
    by_id = {str(subject.id): subject.id for subject in subjects}

    resolved: dict[int, float] = {}
    for ref, score in raw_scores.items():
        subject_id = by_id.get(str(ref)) or by_code.get(ref) or by_name.get(ref)
        if subject_id is not None:
            resolved[subject_id] = float(score)
    return resolved
