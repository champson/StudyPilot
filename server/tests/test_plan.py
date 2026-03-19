import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_generate_plan(client: AsyncClient, seed_data: dict):
    resp = await client.post(
        "/api/v1/student/plan/generate",
        headers={"Authorization": f"Bearer {seed_data['student_token']}"},
        json={"available_minutes": 120},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["source"] == "stub"
    assert len(data["tasks"]) == 3


@pytest.mark.asyncio
async def test_generate_plan_duplicate(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['student_token']}"}
    await client.post(
        "/api/v1/student/plan/generate",
        headers=headers,
        json={"available_minutes": 120},
    )
    resp = await client.post(
        "/api/v1/student/plan/generate",
        headers=headers,
        json={"available_minutes": 120},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_get_today_plan(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['student_token']}"}
    # Generate first
    await client.post(
        "/api/v1/student/plan/generate",
        headers=headers,
        json={"available_minutes": 120},
    )
    resp = await client.get("/api/v1/student/plan/today", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"] is not None


@pytest.mark.asyncio
async def test_update_task_status(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['student_token']}"}
    gen_resp = await client.post(
        "/api/v1/student/plan/generate",
        headers=headers,
        json={"available_minutes": 120},
    )
    task_id = gen_resp.json()["data"]["tasks"][0]["id"]

    # pending -> entered
    resp = await client.patch(
        f"/api/v1/student/plan/tasks/{task_id}",
        headers=headers,
        json={"status": "entered"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "entered"

    # entered -> completed (skip executed)
    resp = await client.patch(
        f"/api/v1/student/plan/tasks/{task_id}",
        headers=headers,
        json={"status": "completed"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "completed"
    assert resp.json()["data"]["completed_at"] is not None


@pytest.mark.asyncio
async def test_task_status_no_backward(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['student_token']}"}
    gen_resp = await client.post(
        "/api/v1/student/plan/generate",
        headers=headers,
        json={"available_minutes": 120},
    )
    task_id = gen_resp.json()["data"]["tasks"][0]["id"]

    # Advance to completed
    await client.patch(
        f"/api/v1/student/plan/tasks/{task_id}",
        headers=headers,
        json={"status": "completed"},
    )

    # Try to go back
    resp = await client.patch(
        f"/api/v1/student/plan/tasks/{task_id}",
        headers=headers,
        json={"status": "entered"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_update_plan_mode(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['student_token']}"}
    await client.post(
        "/api/v1/student/plan/generate",
        headers=headers,
        json={"available_minutes": 120},
    )
    resp = await client.patch(
        "/api/v1/student/plan/mode",
        headers=headers,
        json={"learning_mode": "周末复习"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["learning_mode"] == "周末复习"
