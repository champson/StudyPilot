import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_student_cannot_access_without_token(client: AsyncClient):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_expired_token_rejected(client: AsyncClient, seed_data: dict):
    from datetime import timedelta

    from app.core.security import create_access_token

    expired_token = create_access_token(
        {"sub": "1", "user_id": seed_data["student_user"].id, "role": "student", "student_id": 1},
        expires_delta=timedelta(seconds=-10),
    )
    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_TOKEN_EXPIRED"


@pytest.mark.asyncio
async def test_invalid_jwt_rejected(client: AsyncClient):
    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid.jwt.token"},
    )
    assert resp.status_code == 401
