from datetime import UTC, datetime, timedelta

import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError
from app.models.report import WeeklyReport


async def get_weekly_report(
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


async def list_weekly_summaries(
    db: AsyncSession, student_id: int
) -> list[WeeklyReport]:
    result = await db.execute(
        select(WeeklyReport)
        .where(WeeklyReport.student_id == student_id)
        .order_by(WeeklyReport.created_at.desc())
    )
    return result.scalars().all()


async def create_share_link(
    db: AsyncSession, student_id: int, report_week: str | None = None
) -> dict:
    report = await get_weekly_report(db, student_id, report_week)

    expires_at = datetime.now(UTC) + timedelta(days=settings.SHARE_TOKEN_EXPIRE_DAYS)
    payload = {
        "type": "share",
        "student_id": student_id,
        "report_week": report.report_week,
        "exp": expires_at,
    }
    token = jwt.encode(payload, settings.SHARE_TOKEN_SECRET, algorithm="HS256")

    report.share_token = token
    report.share_expires_at = expires_at
    await db.flush()

    return {
        "share_url": f"/api/v1/share/{token}",
        "expires_at": expires_at,
    }
