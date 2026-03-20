from datetime import date, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.error_book import ErrorBook
from app.models.knowledge import StudentKnowledgeStatus
from app.models.plan import DailyPlan, PlanTask
from app.models.report import SubjectRiskState, WeeklyReport
from app.services import report as report_service
from app.services.knowledge import NEEDS_CONSOLIDATION, current_week_string
from app.services.report import upsert_weekly_report


@pytest.mark.asyncio
async def test_upsert_weekly_report_generates_summary(
    db_session: AsyncSession, seed_data: dict
):
    report_week = current_week_string(date.today() - timedelta(days=7))
    week_start = date.fromisocalendar(
        int(report_week.split("-W")[0]),
        int(report_week.split("-W")[1]),
        1,
    )

    plan = DailyPlan(
        student_id=seed_data["profile"].id,
        plan_date=week_start,
        learning_mode="weekend_review",
        system_recommended_mode="weekend_review",
        available_minutes=90,
        source="history_inferred",
        is_history_inferred=True,
        recommended_subjects=[],
        plan_content={"reasoning": "test"},
        status="generated",
    )
    db_session.add(plan)
    await db_session.flush()

    db_session.add(
        PlanTask(
            plan_id=plan.id,
            subject_id=seed_data["subjects"][1].id,
            task_type="review",
            task_content={"description": "复习定义域"},
            sequence=1,
            estimated_minutes=30,
            status="completed",
            duration_minutes=25,
        )
    )
    db_session.add(
        SubjectRiskState(
            student_id=seed_data["profile"].id,
            subject_id=seed_data["subjects"][1].id,
            risk_level="中度风险",
            effective_week=report_week,
        )
    )
    db_session.add(
        StudentKnowledgeStatus(
            student_id=seed_data["profile"].id,
            knowledge_point_id=seed_data["knowledge_points"][0].id,
            status=NEEDS_CONSOLIDATION,
            last_update_reason="test",
        )
    )
    db_session.add(
        ErrorBook(
            student_id=seed_data["profile"].id,
            subject_id=seed_data["subjects"][1].id,
            question_content={"summary": "函数定义域理解错误"},
            knowledge_points=[{"id": seed_data["knowledge_points"][0].id}],
            entry_reason="wrong",
        )
    )
    await db_session.flush()

    report = await upsert_weekly_report(db_session, seed_data["profile"].id, report_week)
    assert report.usage_days == 1
    assert report.total_minutes == 25
    assert report.student_view_content["task_completion_rate"] == 1.0

    result = await db_session.execute(
        select(WeeklyReport).where(WeeklyReport.id == report.id)
    )
    persisted = result.scalar_one()
    assert persisted.share_summary["subject_risk_overview"]


def test_week_bounds_defaults_to_current_iso_week_on_sunday(monkeypatch):
    class FakeDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 3, 22)

    monkeypatch.setattr(report_service, "date", FakeDate)
    report_week, week_start, week_end = report_service._week_bounds()

    assert report_week == "2026-W12"
    assert week_start == FakeDate(2026, 3, 16)
    assert week_end == FakeDate(2026, 3, 22)
