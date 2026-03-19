import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_textbook_versions(client: AsyncClient):
    resp = await client.get("/api/v1/config/textbook-versions")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)
    assert len(data) > 0
    assert "id" in data[0]
    assert "name" in data[0]
