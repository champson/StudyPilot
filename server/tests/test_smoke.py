"""End-to-end smoke test covering the core student happy path."""

import io

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_full_student_happy_path(client: AsyncClient, seed_data: dict):
    """
    Complete student workflow:
    1. Auth - verify token works
    2. Profile - check exists
    3. Plan - generate + update task status
    4. Upload - upload material
    5. QA - chat (sync)
    6. Errors - list + summary
    7. Knowledge - status
    8. Report - weekly (expect 404 if none generated)
    9. Admin - verify admin can see metrics
    """
    student_headers = {"Authorization": f"Bearer {seed_data['student_token']}"}
    admin_headers = {"Authorization": f"Bearer {seed_data['admin_token']}"}

    # --- Step 1: Auth ---
    resp = await client.get("/api/v1/auth/me", headers=student_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["role"] == "student"

    # --- Step 2: Profile ---
    resp = await client.get("/api/v1/student/profile", headers=student_headers)
    assert resp.status_code == 200
    profile = resp.json()["data"]
    assert profile["grade"] == "高二"
    assert profile["onboarding_completed"] is True

    # --- Step 3: Plan generation ---
    resp = await client.post(
        "/api/v1/student/plan/generate",
        headers=student_headers,
        json={"available_minutes": 90},
    )
    assert resp.status_code == 200
    plan = resp.json()["data"]
    assert len(plan["tasks"]) >= 1
    task_id = plan["tasks"][0]["id"]

    # Get today plan
    resp = await client.get("/api/v1/student/plan/today", headers=student_headers)
    assert resp.status_code == 200

    # Update task status: pending → entered → executed → completed
    for status in ["entered", "executed", "completed"]:
        resp = await client.patch(
            f"/api/v1/student/plan/tasks/{task_id}",
            headers=student_headers,
            json={"status": status},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == status

    # Verify completed_at is set
    assert resp.json()["data"]["completed_at"] is not None

    # --- Step 4: Upload ---
    resp = await client.post(
        "/api/v1/student/material/upload",
        headers=student_headers,
        files={"file": ("test.jpg", io.BytesIO(b"fake-image-content"), "image/jpeg")},
        data={"upload_type": "homework", "subject_id": str(seed_data["subjects"][1].id)},
    )
    assert resp.status_code == 202
    upload_id = resp.json()["data"]["resource_id"]

    # Check upload list
    resp = await client.get("/api/v1/student/material/list", headers=student_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["total"] >= 1

    # Check OCR status
    resp = await client.get(
        f"/api/v1/student/material/{upload_id}/ocr-status",
        headers=student_headers,
    )
    assert resp.status_code == 200

    # --- Step 5: QA Chat ---
    resp = await client.post(
        "/api/v1/student/qa/chat",
        headers=student_headers,
        json={
            "message": "这道数学题怎么解？",
            "subject_id": seed_data["subjects"][1].id,
        },
    )
    assert resp.status_code == 200
    qa_data = resp.json()["data"]
    session_id = qa_data["session_id"]
    assert qa_data["user_message"]["role"] == "user"
    assert qa_data["assistant_message"]["role"] == "assistant"

    # QA History
    resp = await client.get("/api/v1/student/qa/history", headers=student_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["total"] >= 1

    # Session detail
    resp = await client.get(
        f"/api/v1/student/qa/sessions/{session_id}",
        headers=student_headers,
    )
    assert resp.status_code == 200
    assert len(resp.json()["data"]["messages"]) >= 2

    # --- Step 6: Error Book ---
    resp = await client.get("/api/v1/student/errors", headers=student_headers)
    assert resp.status_code == 200

    resp = await client.get("/api/v1/student/errors/summary", headers=student_headers)
    assert resp.status_code == 200
    assert "total" in resp.json()["data"]

    # --- Step 7: Knowledge Status ---
    resp = await client.get("/api/v1/student/knowledge/status", headers=student_headers)
    assert resp.status_code == 200

    # --- Step 8: Report ---
    resp = await client.get("/api/v1/student/report/weekly", headers=student_headers)
    # May be 404 if no report generated yet — that's expected
    assert resp.status_code in (200, 404)

    # Weekly summary list
    resp = await client.get(
        "/api/v1/student/report/weekly/summary", headers=student_headers
    )
    assert resp.status_code == 200

    # --- Step 9: Admin Metrics ---
    resp = await client.get("/api/v1/admin/metrics/today", headers=admin_headers)
    assert resp.status_code == 200
    metrics = resp.json()["data"]
    assert metrics["plans_generated"] >= 1

    resp = await client.get("/api/v1/admin/metrics/health", headers=admin_headers)
    assert resp.status_code == 200

    resp = await client.get("/api/v1/admin/metrics/model-calls", headers=admin_headers)
    assert resp.status_code == 200

    # Admin corrections list
    resp = await client.get("/api/v1/admin/corrections/pending", headers=admin_headers)
    assert resp.status_code == 200

    # --- Step 10: Parent can view report (linked student) ---
    parent_headers = {"Authorization": f"Bearer {seed_data['parent_token']}"}
    resp = await client.get("/api/v1/parent/profile/risk", headers=parent_headers)
    assert resp.status_code == 200

    resp = await client.get("/api/v1/parent/profile/trend", headers=parent_headers)
    assert resp.status_code == 200
