import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Test standard health check endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "ai-qa-service"}


@pytest.mark.asyncio
async def test_actuator_health_check(client: AsyncClient):
    """Test actuator-compatible health check endpoint."""
    response = await client.get("/actuator/health")
    assert response.status_code == 200
    assert response.json()["status"] == "UP"
