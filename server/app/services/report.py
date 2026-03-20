from datetime import UTC, date, datetime, timedelta
from typing import Any

import jwt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import AppError
from app.models.error_book import ErrorBook
from app.models.knowledge import KnowledgeTree, StudentKnowledgeStatus
from app.models.plan import DailyPlan
from app.models.report import SubjectRiskState, WeeklyReport
from app.models.student_profile import StudentProfile
from app.models.subject import Subject
from app.services.knowledge import (
    NEEDS_CONSOLIDATION,
    REPEATED_MISTAKES,
)


def _week_bounds(report_week: str | None = None) -> tuple[str, date, date]:
    if report_week:
        year_str, week_str = report_week.split("-W")
        week_start = date.fromisocalendar(int(year_str), int(week_str), 1)
    else:
        today = date.today()
        iso = today.isocalendar()
        report_week = f"{iso.year}-W{iso.week:02d}"
        week_start = date.fromisocalendar(iso.year, iso.week, 1)
    return report_week, week_start, week_start + timedelta(days=6)


def _risk_trend(risk_level: str) -> str:
    if risk_level == "高风险":
        return "declining"
    if risk_level == "中度风险":
        return "declining"
    if risk_level == "轻度风险":
        return "stable"
    return "improving"


def _suggestions_from_report(
    subject_trends: list[dict[str, Any]],
    high_risk_points: list[dict[str, Any]],
) -> list[str]:
    suggestions: list[str] = []
    declining_subjects = [
        item["subject_name"] for item in subject_trends if item["trend"] == "declining"
    ]
    if declining_subjects:
        suggestions.append(f"优先补强 {declining_subjects[0]}，先回顾错题再做一组小练习。")
    if high_risk_points:
        point = high_risk_points[0]
        suggestions.append(f"围绕「{point['name']}」做一次专项复盘，避免同类错误重复出现。")
    if not suggestions:
        suggestions.append("保持当前节奏，本周继续按计划完成每日复盘。")
    return suggestions


async def build_weekly_report_payload(
    db: AsyncSession, student_id: int, report_week: str | None = None
) -> dict[str, Any]:
    report_week, week_start, week_end = _week_bounds(report_week)

    profile_result = await db.execute(
        select(StudentProfile).where(StudentProfile.id == student_id)
    )
    profile = profile_result.scalar_one_or_none()
    if profile is None:
        raise AppError("PROFILE_NOT_FOUND", "学生档案不存在", status_code=404)

    plan_result = await db.execute(
        select(DailyPlan)
        .options(selectinload(DailyPlan.tasks))
        .where(
            DailyPlan.student_id == student_id,
            DailyPlan.is_deleted == False,  # noqa: E712
            DailyPlan.plan_date >= week_start,
            DailyPlan.plan_date <= week_end,
        )
    )
    plans = plan_result.scalars().all()
    usage_days = len({plan.plan_date for plan in plans})
    all_tasks = [task for plan in plans for task in plan.tasks]
    completed_tasks = [task for task in all_tasks if task.status == "completed"]
    task_completion_rate = (
        round(len(completed_tasks) / len(all_tasks), 4) if all_tasks else 0.0
    )
    total_minutes = int(
        sum(
            task.duration_minutes or task.estimated_minutes or 0
            for task in completed_tasks
        )
    )

    subject_result = await db.execute(select(Subject))
    subject_map = {subject.id: subject.name for subject in subject_result.scalars().all()}

    risk_result = await db.execute(
        select(SubjectRiskState).where(
            SubjectRiskState.student_id == student_id,
            SubjectRiskState.effective_week == report_week,
        )
    )
    subject_trends = [
        {
            "subject_name": subject_map.get(risk.subject_id, ""),
            "risk_level": risk.risk_level,
            "trend": _risk_trend(risk.risk_level),
        }
        for risk in risk_result.scalars().all()
    ]

    knowledge_result = await db.execute(
        select(KnowledgeTree.name, Subject.name, StudentKnowledgeStatus.status)
        .join(
            StudentKnowledgeStatus,
            StudentKnowledgeStatus.knowledge_point_id == KnowledgeTree.id,
        )
        .join(Subject, KnowledgeTree.subject_id == Subject.id)
        .where(
            StudentKnowledgeStatus.student_id == student_id,
            StudentKnowledgeStatus.status.in_([NEEDS_CONSOLIDATION, REPEATED_MISTAKES]),
        )
        .order_by(StudentKnowledgeStatus.last_updated_at.desc())
        .limit(5)
    )
    high_risk_points = [
        {"name": row[0], "subject_name": row[1], "status": row[2]}
        for row in knowledge_result.all()
    ]

    error_result = await db.execute(
        select(ErrorBook.question_content, func.count(ErrorBook.id))
        .where(
            ErrorBook.student_id == student_id,
            ErrorBook.is_deleted == False,  # noqa: E712
            ErrorBook.created_at >= datetime.combine(week_start, datetime.min.time(), tzinfo=UTC),
            ErrorBook.created_at <= datetime.combine(week_end, datetime.max.time(), tzinfo=UTC),
        )
        .group_by(ErrorBook.question_content)
        .order_by(func.count(ErrorBook.id).desc())
        .limit(5)
    )
    repeated_error_points = []
    for question_content, count in error_result.all():
        summary = ""
        if isinstance(question_content, dict):
            summary = question_content.get("summary") or question_content.get("description") or ""
        repeated_error_points.append({"name": summary or "错题", "error_count": count})

    suggestions = _suggestions_from_report(subject_trends, high_risk_points)

    student_view_content = {
        "task_completion_rate": task_completion_rate,
        "subject_trends": subject_trends,
        "high_risk_knowledge_points": high_risk_points,
        "repeated_error_points": repeated_error_points,
        "next_stage_suggestions": suggestions,
        "class_rank": profile.class_rank,
        "grade_rank": profile.grade_rank,
    }
    parent_view_content = {
        "student_name": None,
        "task_completion_rate": task_completion_rate,
        "subject_risks": [
            {
                "subject_id": next(
                    (
                        subject_id
                        for subject_id, name in subject_map.items()
                        if name == item["subject_name"]
                    ),
                    None,
                ),
                "subject_name": item["subject_name"],
                "risk_level": item["risk_level"],
                "effective_week": report_week,
            }
            for item in subject_trends
        ],
        "trend_description": suggestions[0] if suggestions else None,
        "action_suggestions": suggestions,
    }
    share_summary = {
        "trend_overview": suggestions[0] if suggestions else "本周整体节奏稳定。",
        "subject_risk_overview": [
            {"subject_name": item["subject_name"], "risk_level": item["risk_level"]}
            for item in subject_trends
        ],
        "next_stage_suggestions_summary": suggestions[0] if suggestions else None,
    }

    return {
        "report_week": report_week,
        "usage_days": usage_days,
        "total_minutes": total_minutes,
        "student_view_content": student_view_content,
        "parent_view_content": parent_view_content,
        "share_summary": share_summary,
    }


async def upsert_weekly_report(
    db: AsyncSession, student_id: int, report_week: str | None = None
) -> WeeklyReport:
    payload = await build_weekly_report_payload(db, student_id, report_week)
    result = await db.execute(
        select(WeeklyReport).where(
            WeeklyReport.student_id == student_id,
            WeeklyReport.report_week == payload["report_week"],
        )
    )
    report = result.scalar_one_or_none()
    if report is None:
        report = WeeklyReport(
            student_id=student_id,
            report_week=payload["report_week"],
            usage_days=payload["usage_days"],
            total_minutes=payload["total_minutes"],
            student_view_content=payload["student_view_content"],
            parent_view_content=payload["parent_view_content"],
            share_summary=payload["share_summary"],
        )
        db.add(report)
    else:
        report.usage_days = payload["usage_days"]
        report.total_minutes = payload["total_minutes"]
        report.student_view_content = payload["student_view_content"]
        report.parent_view_content = payload["parent_view_content"]
        report.share_summary = payload["share_summary"]
    await db.flush()
    return report


async def generate_weekly_reports(
    db: AsyncSession, report_week: str | None = None
) -> list[WeeklyReport]:
    result = await db.execute(
        select(StudentProfile.id).where(StudentProfile.onboarding_completed == True)  # noqa: E712
    )
    student_ids = [row[0] for row in result.all()]
    reports = []
    for student_id in student_ids:
        reports.append(await upsert_weekly_report(db, student_id, report_week))
    return reports


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
        "share_token": token,
    }
