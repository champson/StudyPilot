import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plan import DailyPlan, PlanTask
from app.models.system import ManualCorrection
from app.models.upload import StudyUpload


@pytest.mark.asyncio
async def test_correction_detail_ocr(
    client: AsyncClient, seed_data: dict, db_session: AsyncSession
):
    upload = StudyUpload(
        student_id=seed_data["profile"].id,
        original_url="/uploads/test.jpg",
        upload_type="homework",
        file_hash="test-upload-hash",
        ocr_status="failed",
        ocr_result={"text": "original ocr"},
        ocr_error="recognition failed",
    )
    db_session.add(upload)
    await db_session.flush()

    correction = ManualCorrection(
        target_type="ocr",
        target_id=upload.id,
        original_content={"text": "original ocr"},
        corrected_content={"text": "corrected ocr"},
        corrected_by=seed_data["admin"].id,
        status="pending",
    )
    db_session.add(correction)
    await db_session.flush()

    headers = {"Authorization": f"Bearer {seed_data['admin_token']}"}
    resp = await client.get(
        f"/api/v1/admin/corrections/{correction.id}", headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["target_type"] == "ocr"
    assert data["context"] is not None
    assert data["context"]["original_url"] == "/uploads/test.jpg"
    assert data["context"]["ocr_error"] == "recognition failed"


@pytest.mark.asyncio
async def test_correction_detail_knowledge(
    client: AsyncClient, seed_data: dict, db_session: AsyncSession
):
    from app.models.knowledge import StudentKnowledgeStatus

    kp = seed_data["knowledge_points"][0]
    status = StudentKnowledgeStatus(
        student_id=seed_data["profile"].id,
        knowledge_point_id=kp.id,
        status="需要巩固",
    )
    db_session.add(status)
    await db_session.flush()

    correction = ManualCorrection(
        target_type="knowledge",
        target_id=status.id,
        original_content={
            "status": "需要巩固",
            "student_id": seed_data["profile"].id,
            "knowledge_point_id": kp.id,
        },
        corrected_content={"status": "基本掌握"},
        corrected_by=seed_data["admin"].id,
        status="pending",
    )
    db_session.add(correction)
    await db_session.flush()

    headers = {"Authorization": f"Bearer {seed_data['admin_token']}"}
    resp = await client.get(
        f"/api/v1/admin/corrections/{correction.id}", headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["target_type"] == "knowledge"
    assert data["context"]["knowledge_point_name"] == kp.name


@pytest.mark.asyncio
async def test_correction_detail_not_found(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['admin_token']}"}
    resp = await client.get("/api/v1/admin/corrections/99999", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_correction_logs_pagination(
    client: AsyncClient, seed_data: dict, db_session: AsyncSession
):
    for i in range(3):
        c = ManualCorrection(
            target_type="ocr",
            target_id=i + 1,
            corrected_content={"text": f"fix {i}"},
            corrected_by=seed_data["admin"].id,
            status="resolved",
        )
        db_session.add(c)
    await db_session.flush()

    headers = {"Authorization": f"Bearer {seed_data['admin_token']}"}
    resp = await client.get(
        "/api/v1/admin/corrections/logs?page=1&page_size=2", headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 3
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_pending_count_by_type(
    client: AsyncClient, seed_data: dict, db_session: AsyncSession
):
    for target_type in ["ocr", "ocr", "knowledge", "plan"]:
        c = ManualCorrection(
            target_type=target_type,
            target_id=1,
            corrected_content={"text": "fix"},
            corrected_by=seed_data["admin"].id,
            status="pending",
        )
        db_session.add(c)
    await db_session.flush()

    headers = {"Authorization": f"Bearer {seed_data['admin_token']}"}
    resp = await client.get("/api/v1/admin/corrections/pending/count", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["ocr"] == 2
    assert data["knowledge"] == 1
    assert data["plan"] == 1
    assert data["total"] == 4


@pytest.mark.asyncio
async def test_correct_plan(
    client: AsyncClient, seed_data: dict, db_session: AsyncSession
):
    from datetime import date

    plan = DailyPlan(
        student_id=seed_data["profile"].id,
        plan_date=date.today(),
        learning_mode="weekday_followup",
        available_minutes=60,
        source="generic_fallback",
        recommended_subjects={"subjects": []},
        plan_content={"tasks": []},
    )
    db_session.add(plan)
    await db_session.flush()

    task = PlanTask(
        plan_id=plan.id,
        subject_id=seed_data["subjects"][0].id,
        task_type="review",
        task_content={"description": "复习课文"},
        sequence=1,
        estimated_minutes=20,
    )
    db_session.add(task)
    await db_session.flush()

    headers = {"Authorization": f"Bearer {seed_data['admin_token']}"}
    resp = await client.post(
        "/api/v1/admin/corrections/plan",
        headers=headers,
        json={
            "plan_id": plan.id,
            "corrected_tasks": [
                {"id": task.id, "task_type": "practice", "sequence": 1}
            ],
            "reason": "调整任务类型",
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["target_type"] == "plan"
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_resolve_plan_correction(
    client: AsyncClient, seed_data: dict, db_session: AsyncSession
):
    from datetime import date

    plan = DailyPlan(
        student_id=seed_data["profile"].id,
        plan_date=date.today(),
        learning_mode="weekday_followup",
        available_minutes=60,
        source="generic_fallback",
        recommended_subjects={"subjects": []},
        plan_content={"tasks": []},
    )
    db_session.add(plan)
    await db_session.flush()

    task = PlanTask(
        plan_id=plan.id,
        subject_id=seed_data["subjects"][0].id,
        task_type="review",
        task_content={"description": "复习"},
        sequence=1,
        estimated_minutes=20,
    )
    db_session.add(task)
    await db_session.flush()

    correction = ManualCorrection(
        target_type="plan",
        target_id=plan.id,
        original_content={"tasks": [{"id": task.id, "task_type": "review", "sequence": 1}]},
        corrected_content={
            "tasks": [{"id": task.id, "task_type": "practice", "sequence": 1}]
        },
        corrected_by=seed_data["admin"].id,
        status="pending",
    )
    db_session.add(correction)
    await db_session.flush()

    headers = {"Authorization": f"Bearer {seed_data['admin_token']}"}
    resp = await client.post(
        f"/api/v1/admin/corrections/{correction.id}/resolve",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "resolved"

    # Verify task was updated
    await db_session.refresh(task)
    assert task.task_type == "practice"


@pytest.mark.asyncio
async def test_resolve_plan_unmatched_tasks(
    client: AsyncClient, seed_data: dict, db_session: AsyncSession
):
    from datetime import date

    plan = DailyPlan(
        student_id=seed_data["profile"].id,
        plan_date=date.today(),
        learning_mode="weekday_followup",
        available_minutes=60,
        source="generic_fallback",
        recommended_subjects={"subjects": []},
        plan_content={"tasks": []},
    )
    db_session.add(plan)
    await db_session.flush()

    correction = ManualCorrection(
        target_type="plan",
        target_id=plan.id,
        original_content={"tasks": []},
        corrected_content={
            "tasks": [{"id": 99999, "task_type": "practice"}]
        },
        corrected_by=seed_data["admin"].id,
        status="pending",
    )
    db_session.add(correction)
    await db_session.flush()

    headers = {"Authorization": f"Bearer {seed_data['admin_token']}"}
    resp = await client.post(
        f"/api/v1/admin/corrections/{correction.id}/resolve",
        headers=headers,
    )
    assert resp.status_code == 400
    assert "无法匹配" in resp.json()["error"]["message"]
