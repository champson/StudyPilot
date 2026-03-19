import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_profile(client: AsyncClient, seed_data: dict):
    resp = await client.get(
        "/api/v1/student/profile",
        headers={"Authorization": f"Bearer {seed_data['student_token']}"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["grade"] == "高二"


@pytest.mark.asyncio
async def test_update_profile(client: AsyncClient, seed_data: dict):
    resp = await client.patch(
        "/api/v1/student/profile",
        headers={"Authorization": f"Bearer {seed_data['student_token']}"},
        json={"textbook_version": "人教版A"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["textbook_version"] == "人教版A"


@pytest.mark.asyncio
async def test_onboarding_status(client: AsyncClient, seed_data: dict):
    resp = await client.get(
        "/api/v1/student/onboarding/status",
        headers={"Authorization": f"Bearer {seed_data['student_token']}"},
    )
    assert resp.status_code == 200
    # seed_data creates profile with onboarding_completed=True
    assert resp.json()["data"]["onboarding_completed"] is True


@pytest.mark.asyncio
async def test_submit_onboarding_duplicate(client: AsyncClient, seed_data: dict):
    # seed_data already has onboarding_completed=True, so submitting again should fail
    headers = {"Authorization": f"Bearer {seed_data['student_token']}"}
    resp = await client.post(
        "/api/v1/student/onboarding/submit",
        headers=headers,
        json={"weak_subjects": [], "low_score_subjects": []},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_profile_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/student/profile")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_profile_requires_student_role(client: AsyncClient, seed_data: dict):
    resp = await client.get(
        "/api/v1/student/profile",
        headers={"Authorization": f"Bearer {seed_data['admin_token']}"},
    )
    assert resp.status_code == 403
