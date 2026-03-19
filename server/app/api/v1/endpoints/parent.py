from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_student_id, require_parent
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import SuccessResponse
from app.schemas.parent import (
    ExamRecordRequest,
    ParentWeeklyReportOut,
    RiskOverviewOut,
    SupplementRequest,
    TrendOut,
)
from app.schemas.report import ShareLinkOut
from app.schemas.student_profile import ExamRecordOut, StudentProfileOut
from app.services import parent as svc
from app.services import report as report_svc

router = APIRouter(prefix="/parent", tags=["parent"])


@router.get("/report/weekly", response_model=SuccessResponse[ParentWeeklyReportOut])
async def get_weekly_report(
    week: str | None = None,
    student_id: int = Depends(get_student_id),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_parent),
):
    report = await svc.get_parent_weekly_report(db, student_id, week)
    return SuccessResponse(
        data=ParentWeeklyReportOut(
            id=report.id,
            student_id=report.student_id,
            report_week=report.report_week,
            usage_days=report.usage_days,
            total_minutes=report.total_minutes,
            content=report.parent_view_content,
            created_at=report.created_at,
        )
    )


@router.post("/report/share", response_model=SuccessResponse[ShareLinkOut])
async def create_share_link(
    week: str | None = None,
    student_id: int = Depends(get_student_id),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_parent),
):
    result = await report_svc.create_share_link(db, student_id, week)
    return SuccessResponse(data=ShareLinkOut(**result))


@router.get("/profile/risk", response_model=SuccessResponse[RiskOverviewOut])
async def get_risk_overview(
    student_id: int = Depends(get_student_id),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_parent),
):
    risks = await svc.get_risk_overview(db, student_id)
    return SuccessResponse(data=RiskOverviewOut(student_id=student_id, risks=risks))


@router.get("/profile/trend", response_model=SuccessResponse[TrendOut])
async def get_trend(
    student_id: int = Depends(get_student_id),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_parent),
):
    weeks = await svc.get_trend(db, student_id)
    return SuccessResponse(data=TrendOut(student_id=student_id, weeks=weeks))


@router.post("/profile/supplement", response_model=SuccessResponse[StudentProfileOut])
async def supplement_profile(
    body: SupplementRequest,
    student_id: int = Depends(get_student_id),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_parent),
):
    profile = await svc.supplement_profile(db, student_id, body)
    return SuccessResponse(data=StudentProfileOut.model_validate(profile))


@router.post("/exam/record", response_model=SuccessResponse[ExamRecordOut])
async def record_exam(
    body: ExamRecordRequest,
    student_id: int = Depends(get_student_id),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_parent),
):
    record = await svc.record_exam(db, student_id, body)
    return SuccessResponse(data=ExamRecordOut.model_validate(record))
