"""Tests for health check endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_liveness_returns_200(client: AsyncClient) -> None:
    response = await client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert "version" in body
    assert "environment" in body


@pytest.mark.asyncio
async def test_liveness_no_auth_required(client: AsyncClient) -> None:
    """Liveness probe must work without authentication."""
    from httpx import AsyncClient as RawClient
    from httpx import ASGITransport
    from src.main import app
    async with RawClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        response = await c.get("/healthz")
    assert response.status_code == 200
