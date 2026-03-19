from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.knowledge import StudentKnowledgeStatus
from app.models.student_profile import StudentProfile
from app.schemas.student_profile import (
    OnboardingSubmit,
    StudentProfileCreate,
    StudentProfileUpdate,
)


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
) -> StudentProfile:
    profile = await get_profile(db, student_id)
    if profile.onboarding_completed:
        raise AppError(
            "ONBOARDING_ALREADY_COMPLETED", "入学问卷已提交", status_code=409
        )

    profile.onboarding_data = data.model_dump()
    profile.onboarding_completed = True

    # Initialize knowledge statuses for weak subjects
    for subject_id in data.weak_subjects:
        status = StudentKnowledgeStatus(
            student_id=student_id,
            knowledge_point_id=subject_id,  # placeholder mapping
            status="初步接触",
            last_update_reason="onboarding_weak_subject",
        )
        db.add(status)

    await db.flush()
    return profile


async def get_onboarding_status(db: AsyncSession, student_id: int) -> bool:
    profile = await get_profile(db, student_id)
    return profile.onboarding_completed
