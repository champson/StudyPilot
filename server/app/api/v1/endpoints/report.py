from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_student_id, require_student
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import SuccessResponse
from app.schemas.report import ShareLinkOut, WeeklyReportOut, WeeklyReportSummary
from app.services import report as svc

router = APIRouter(prefix="/student/report", tags=["report"])


@router.get("/weekly", response_model=SuccessResponse[WeeklyReportOut])
async def get_weekly_report(
    week: str | None = None,
    student_id: int = Depends(get_student_id),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_student),
):
    report = await svc.get_weekly_report(db, student_id, week)
    # Unpack structured fields from student_view_content JSONB
    content = report.student_view_content or {}
    return SuccessResponse(
        data=WeeklyReportOut(
            id=report.id,
            student_id=report.student_id,
            report_week=report.report_week,
            usage_days=report.usage_days,
            total_minutes=report.total_minutes,
            task_completion_rate=content.get("task_completion_rate"),
            subject_trends=content.get("subject_trends", []),
            high_risk_knowledge_points=content.get("high_risk_knowledge_points", []),
            repeated_error_points=content.get("repeated_error_points", []),
            next_stage_suggestions=content.get("next_stage_suggestions", []),
            class_rank=content.get("class_rank"),
            grade_rank=content.get("grade_rank"),
            share_token=report.share_token,
            created_at=report.created_at,
        )
    )


@router.get("/weekly/summary", response_model=SuccessResponse[list[WeeklyReportSummary]])
async def get_weekly_summaries(
    student_id: int = Depends(get_student_id),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_student),
):
    reports = await svc.list_weekly_summaries(db, student_id)
    return SuccessResponse(
        data=[
            WeeklyReportSummary(
                report_week=r.report_week,
                usage_days=r.usage_days,
                total_minutes=r.total_minutes,
                created_at=r.created_at,
            )
            for r in reports
        ]
    )


@router.post("/share", response_model=SuccessResponse[ShareLinkOut])
async def create_share_link(
    week: str | None = None,
    student_id: int = Depends(get_student_id),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_student),
):
    result = await svc.create_share_link(db, student_id, week)
    return SuccessResponse(data=ShareLinkOut(**result))
