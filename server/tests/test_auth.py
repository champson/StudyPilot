import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_token_login_student(client: AsyncClient, seed_data: dict):
    resp = await client.post(
        "/api/v1/auth/token-login",
        json={"token": "test-student-token", "role": "student"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["token_type"] == "bearer"
    assert data["user"]["role"] == "student"
    assert data["user"]["student_id"] is not None


@pytest.mark.asyncio
async def test_token_login_invalid(client: AsyncClient, seed_data: dict):
    resp = await client.post(
        "/api/v1/auth/token-login",
        json={"token": "bad-token", "role": "student"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_INVALID_TOKEN"


@pytest.mark.asyncio
async def test_admin_login_success(client: AsyncClient, seed_data: dict):
    resp = await client.post(
        "/api/v1/auth/admin-login",
        json={"username": "admin", "password": "testpass"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["user"]["role"] == "admin"


@pytest.mark.asyncio
async def test_admin_login_wrong_password(client: AsyncClient, seed_data: dict):
    resp = await client.post(
        "/api/v1/auth/admin-login",
        json={"username": "admin", "password": "wrong"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_WRONG_PASSWORD"


@pytest.mark.asyncio
async def test_me_endpoint(client: AsyncClient, seed_data: dict):
    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {seed_data['student_token']}"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["role"] == "student"
    assert data["student_id"] is not None


@pytest.mark.asyncio
async def test_me_no_auth(client: AsyncClient):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient, seed_data: dict):
    resp = await client.post(
        "/api/v1/auth/refresh",
        headers={"Authorization": f"Bearer {seed_data['student_token']}"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["access_token"] != seed_data["student_token"]


@pytest.mark.asyncio
async def test_parent_login(client: AsyncClient, seed_data: dict):
    resp = await client.post(
        "/api/v1/auth/token-login",
        json={"token": "test-parent-token", "role": "parent"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["user"]["role"] == "parent"
    assert data["user"]["student_id"] is not None
