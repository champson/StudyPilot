from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.report import SubjectRiskState, WeeklyReport
from app.models.student_profile import ExamRecord, StudentProfile
from app.schemas.parent import ExamRecordRequest, SupplementRequest


async def get_parent_weekly_report(
    db: AsyncSession, student_id: int, week: str | None = None
) -> WeeklyReport:
    query = select(WeeklyReport).where(WeeklyReport.student_id == student_id)
    if week:
        query = query.where(WeeklyReport.report_week == week)
    else:
        query = query.order_by(WeeklyReport.created_at.desc())

    result = await db.execute(query)
    report = result.scalars().first()
    if not report:
        raise AppError("REPORT_NOT_FOUND", "周报不存在", status_code=404)
    return report


async def get_risk_overview(db: AsyncSession, student_id: int) -> list[dict]:
    result = await db.execute(
        select(SubjectRiskState)
        .where(SubjectRiskState.student_id == student_id)
        .order_by(SubjectRiskState.effective_week.desc())
    )
    risks = result.scalars().all()
    return [
        {
            "subject_id": r.subject_id,
            "risk_level": r.risk_level,
            "effective_week": r.effective_week,
        }
        for r in risks
    ]


async def get_trend(db: AsyncSession, student_id: int) -> list[dict]:
    result = await db.execute(
        select(WeeklyReport)
        .where(WeeklyReport.student_id == student_id)
        .order_by(WeeklyReport.report_week.asc())
    )
    reports = result.scalars().all()
    return [
        {
            "week": r.report_week,
            "usage_days": r.usage_days,
            "total_minutes": r.total_minutes,
        }
        for r in reports
    ]


async def supplement_profile(
    db: AsyncSession, student_id: int, data: SupplementRequest
) -> StudentProfile:
    result = await db.execute(
        select(StudentProfile).where(StudentProfile.id == student_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise AppError("PROFILE_NOT_FOUND", "学生档案不存在", status_code=404)

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(profile, key, value)
    await db.flush()
    return profile


async def record_exam(
    db: AsyncSession, student_id: int, data: ExamRecordRequest
) -> ExamRecord:
    record = ExamRecord(
        student_id=student_id,
        exam_type=data.exam_type,
        exam_date=data.exam_date,
        subject_id=data.subject_id,
        score=data.score,
        full_score=data.full_score,
        class_rank=data.class_rank,
        grade_rank=data.grade_rank,
        created_by="parent",
    )
    db.add(record)
    await db.flush()
    return record
