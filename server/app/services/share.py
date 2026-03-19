import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError
from app.models.report import WeeklyReport
from app.models.user import User


def decode_share_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SHARE_TOKEN_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise AppError("SHARE_EXPIRED", "分享链接已过期", status_code=410)
    except jwt.InvalidTokenError:
        raise AppError("SHARE_INVALID", "无效的分享链接", status_code=400)

    if payload.get("type") != "share":
        raise AppError("SHARE_INVALID", "无效的分享链接", status_code=400)
    if not payload.get("report_week"):
        raise AppError("SHARE_INVALID", "分享链接缺少周报信息", status_code=400)
    return payload


async def get_share_content(db: AsyncSession, token: str) -> dict:
    payload = decode_share_token(token)
    student_id = payload["student_id"]
    report_week = payload["report_week"]

    result = await db.execute(
        select(WeeklyReport).where(
            WeeklyReport.student_id == student_id,
            WeeklyReport.report_week == report_week,
        )
    )
    report = result.scalar_one_or_none()
    if not report:
        raise AppError("REPORT_NOT_FOUND", "周报不存在", status_code=404)

    # Get student nickname (desensitized)
    from app.models.student_profile import StudentProfile

    profile_result = await db.execute(
        select(StudentProfile).where(StudentProfile.id == student_id)
    )
    profile = profile_result.scalar_one_or_none()
    nickname = None
    if profile:
        user_result = await db.execute(
            select(User).where(User.id == profile.user_id)
        )
        user = user_result.scalar_one_or_none()
        if user and user.nickname:
            # Desensitize: show first char + ***
            nickname = user.nickname[0] + "***" if len(user.nickname) > 1 else user.nickname

    # Extract share_summary fields matching api-contract ShareContent
    summary = report.share_summary or {}

    return {
        "student_name": nickname,
        "report_week": report.report_week,
        "usage_days": report.usage_days,
        "total_minutes": report.total_minutes,
        "trend_overview": summary.get("trend_overview"),
        "subject_risk_overview": summary.get("subject_risk_overview", []),
        "next_stage_suggestions_summary": summary.get("next_stage_suggestions_summary"),
        "expires_at": report.share_expires_at,
    }


async def validate_share_token(token: str) -> dict:
    try:
        payload = decode_share_token(token)
        return {
            "valid": True,
            "report_week": payload.get("report_week"),
            "expires_at": payload.get("exp"),
        }
    except AppError:
        return {"valid": False, "report_week": None, "expires_at": None}
