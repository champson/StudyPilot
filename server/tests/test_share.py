import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report import WeeklyReport


@pytest.mark.asyncio
async def test_share_validate_invalid(client: AsyncClient):
    resp = await client.get("/api/v1/share/invalid-token/validate")
    assert resp.status_code == 200
    assert resp.json()["data"]["valid"] is False


@pytest.mark.asyncio
async def test_share_content_invalid(client: AsyncClient):
    resp = await client.get("/api/v1/share/invalid-token")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_SHARE_TOKEN_INVALID"


@pytest.mark.asyncio
async def test_share_flow(client: AsyncClient, seed_data: dict, db_session: AsyncSession):
    # Create a weekly report first
    report = WeeklyReport(
        student_id=seed_data["profile"].id,
        report_week="2026-W11",
        usage_days=5,
        total_minutes=300,
        student_view_content={"summary": "Good week"},
        parent_view_content={"summary": "Parent view"},
        share_summary={"summary": "Shared view"},
    )
    db_session.add(report)
    await db_session.flush()

    headers = {"Authorization": f"Bearer {seed_data['student_token']}"}
    share_resp = await client.post(
        "/api/v1/student/report/share?week=2026-W11", headers=headers
    )
    assert share_resp.status_code == 200
    share_url = share_resp.json()["data"]["share_url"]
    token = share_url.split("/")[-1]

    # Validate
    validate_resp = await client.get(f"/api/v1/share/{token}/validate")
    assert validate_resp.status_code == 200
    assert validate_resp.json()["data"]["valid"] is True

    # Get content
    content_resp = await client.get(f"/api/v1/share/{token}")
    assert content_resp.status_code == 200
    assert content_resp.json()["data"]["report_week"] == "2026-W11"
