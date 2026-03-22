from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plan import DailyPlan, PlanTask
from app.models.system import ManualCorrection


@pytest.mark.asyncio
async def test_admin_metrics_today(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['admin_token']}"}
    resp = await client.get("/api/v1/admin/metrics/today", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "active_students" in data
    assert "plans_generated" in data


@pytest.mark.asyncio
async def test_admin_model_calls(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['admin_token']}"}
    resp = await client.get("/api/v1/admin/metrics/model-calls", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "total" in data


@pytest.mark.asyncio
async def test_admin_corrections_pending(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['admin_token']}"}
    resp = await client.get("/api/v1/admin/corrections/pending", headers=headers)
    assert resp.status_code == 200
    assert "items" in resp.json()["data"]


@pytest.mark.asyncio
async def test_student_cannot_access_admin(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['student_token']}"}
    resp = await client.get("/api/v1/admin/metrics/today", headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_parent_cannot_access_admin(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['parent_token']}"}
    resp = await client.get("/api/v1/admin/metrics/today", headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_switch_system_mode(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['admin_token']}"}
    resp = await client.post(
        "/api/v1/admin/system/mode",
        headers=headers,
        json={"mode": "best"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["mode"] == "best"

    get_resp = await client.get("/api/v1/admin/system/mode", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["mode"] == "best"


@pytest.mark.asyncio
async def test_resolve_plan_correction_marks_manual_adjusted(
    client: AsyncClient, seed_data: dict, db_session: AsyncSession
):
    plan = DailyPlan(
        student_id=seed_data["profile"].id,
        plan_date=date.today(),
        learning_mode="workday_follow",
        system_recommended_mode="workday_follow",
        available_minutes=90,
        source="history_inferred",
        is_history_inferred=True,
        recommended_subjects=[],
        plan_content={"tasks": []},
        status="generated",
    )
    db_session.add(plan)
    await db_session.flush()

    task_one = PlanTask(
        plan_id=plan.id,
        subject_id=seed_data["subjects"][0].id,
        task_type="lecture",
        task_content={"title": "任务1", "description": "A", "knowledge_point_ids": []},
        sequence=1,
        status="pending",
    )
    task_two = PlanTask(
        plan_id=plan.id,
        subject_id=seed_data["subjects"][1].id,
        task_type="practice",
        task_content={"title": "任务2", "description": "B", "knowledge_point_ids": []},
        sequence=2,
        status="pending",
    )
    db_session.add_all([task_one, task_two])
    await db_session.flush()

    correction = ManualCorrection(
        target_type="plan",
        target_id=plan.id,
        original_content={"tasks": []},
        corrected_content={
            "tasks": [
                {"id": task_two.id, "sequence": 1},
                {"id": task_one.id, "sequence": 2},
            ]
        },
        corrected_by=seed_data["admin"].id,
        status="pending",
    )
    db_session.add(correction)
    await db_session.commit()

    headers = {"Authorization": f"Bearer {seed_data['admin_token']}"}
    resp = await client.post(
        f"/api/v1/admin/corrections/{correction.id}/resolve",
        headers=headers,
        json={},
    )
    assert resp.status_code == 200

    await db_session.refresh(plan)
    assert plan.source == "manual_adjusted"
    assert plan.is_history_inferred is False
    assert [task["sequence"] for task in plan.plan_content["tasks"]] == [1, 2]
