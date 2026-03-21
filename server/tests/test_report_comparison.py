import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report import WeeklyReport
from app.services.report import get_previous_week_report


def _make_report(
    student_id: int,
    report_week: str,
    usage_days: int = 5,
    total_minutes: int = 300,
    task_completion_rate: float = 0.8,
) -> WeeklyReport:
    return WeeklyReport(
        student_id=student_id,
        report_week=report_week,
        usage_days=usage_days,
        total_minutes=total_minutes,
        student_view_content={
            "task_completion_rate": task_completion_rate,
            "subject_trends": [],
            "high_risk_knowledge_points": [],
            "repeated_error_points": [],
            "next_stage_suggestions": ["保持节奏"],
        },
        parent_view_content={
            "task_completion_rate": task_completion_rate,
            "subject_risks": [],
            "trend_description": "本周表现稳定",
            "action_suggestions": ["继续加油"],
            "avg_daily_minutes": total_minutes // max(usage_days, 1),
            "risk_summary": {
                "high_risk_points": [],
                "repeated_errors": [],
            },
            "parent_support_suggestions": [
                "孩子本周学习投入积极，建议给予肯定和鼓励。",
                "周末可适当提醒孩子进行错题回顾。",
            ],
        },
        share_summary={"trend_overview": "稳定"},
    )


@pytest.mark.asyncio
async def test_weekly_report_with_previous(
    client: AsyncClient, seed_data: dict, db_session: AsyncSession
):
    sid = seed_data["profile"].id
    current = _make_report(sid, "2026-W12", usage_days=5, total_minutes=300)
    previous = _make_report(sid, "2026-W11", usage_days=3, total_minutes=200)
    db_session.add_all([current, previous])
    await db_session.flush()

    headers = {"Authorization": f"Bearer {seed_data['student_token']}"}
    resp = await client.get(
        "/api/v1/student/report/weekly?week=2026-W12", headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["usage_days"] == 5
    assert data["previous_usage_days"] == 3
    assert data["previous_total_minutes"] == 200
    assert data["previous_task_completion_rate"] is not None


@pytest.mark.asyncio
async def test_weekly_report_no_previous(
    client: AsyncClient, seed_data: dict, db_session: AsyncSession
):
    sid = seed_data["profile"].id
    current = _make_report(sid, "2026-W12")
    db_session.add(current)
    await db_session.flush()

    headers = {"Authorization": f"Bearer {seed_data['student_token']}"}
    resp = await client.get(
        "/api/v1/student/report/weekly?week=2026-W12", headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["previous_usage_days"] is None
    assert data["previous_total_minutes"] is None
    assert data["previous_task_completion_rate"] is None


@pytest.mark.asyncio
async def test_week_boundary_w01(db_session: AsyncSession, seed_data: dict):
    """W01 should look back to the last ISO week of the previous year."""
    sid = seed_data["profile"].id
    # 2025-12-29 is Monday of ISO week 2025-W01? No.
    # Dec 28, 2025 is a Sunday. isocalendar() -> (2025, 52, 7) for a non-leap year.
    # So previous week of 2026-W01 should be 2025-W52.
    prev_report = _make_report(sid, "2025-W52", usage_days=4, total_minutes=250)
    db_session.add(prev_report)
    await db_session.flush()

    result = await get_previous_week_report(db_session, sid, "2026-W01")
    assert result is not None
    assert result.report_week == "2025-W52"


@pytest.mark.asyncio
async def test_parent_report_support_suggestions(
    client: AsyncClient, seed_data: dict, db_session: AsyncSession
):
    sid = seed_data["profile"].id
    report = _make_report(sid, "2026-W12")
    db_session.add(report)
    await db_session.flush()

    headers = {"Authorization": f"Bearer {seed_data['parent_token']}"}
    resp = await client.get(
        "/api/v1/parent/report/weekly?week=2026-W12", headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "parent_support_suggestions" in data
    assert len(data["parent_support_suggestions"]) >= 1


@pytest.mark.asyncio
async def test_parent_report_risk_summary(
    client: AsyncClient, seed_data: dict, db_session: AsyncSession
):
    sid = seed_data["profile"].id
    report = _make_report(sid, "2026-W12")
    db_session.add(report)
    await db_session.flush()

    headers = {"Authorization": f"Bearer {seed_data['parent_token']}"}
    resp = await client.get(
        "/api/v1/parent/report/weekly?week=2026-W12", headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "risk_summary" in data
    assert "high_risk_points" in data["risk_summary"]
    assert "repeated_errors" in data["risk_summary"]


@pytest.mark.asyncio
async def test_parent_report_avg_daily_minutes(
    client: AsyncClient, seed_data: dict, db_session: AsyncSession
):
    sid = seed_data["profile"].id
    report = _make_report(sid, "2026-W12", usage_days=5, total_minutes=300)
    db_session.add(report)
    await db_session.flush()

    headers = {"Authorization": f"Bearer {seed_data['parent_token']}"}
    resp = await client.get(
        "/api/v1/parent/report/weekly?week=2026-W12", headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["avg_daily_minutes"] == 60  # 300 / 5
