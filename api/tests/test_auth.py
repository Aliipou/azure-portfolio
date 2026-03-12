"""Tests for authentication and authorization."""

from __future__ import annotations

import json

import pytest
from httpx import AsyncClient, ASGITransport

from src.main import app


@pytest.mark.asyncio
async def test_unauthenticated_request_returns_401() -> None:
    """Requests without auth header should return 401 in non-dev mode."""
    from unittest.mock import patch
    with patch("src.config.settings.dev_mode", False):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            response = await c.get("/api/v1/measurements")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_dev_mode_accepts_x_dev_user(client: AsyncClient) -> None:
    response = await client.get("/healthz")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_viewer_cannot_post_device(viewer_client: AsyncClient) -> None:
    """Viewer role cannot create devices (Admin only)."""
    payload = {
        "name": "Test Device",
        "serial_number": "SN-VIEWER-001",
        "device_type": "pressure",
        "location": "Lab",
        "tenant_id": "tenant-001",
    }
    response = await viewer_client.post("/api/v1/devices", json=payload)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_viewer_cannot_create_measurement(viewer_client: AsyncClient) -> None:
    """Viewer role cannot ingest measurements (Operator/Admin only)."""
    import uuid
    from datetime import datetime, timezone
    payload = {
        "device_id": str(uuid.uuid4()),
        "measured_value": 100.0,
        "reference_value": 100.0,
        "uncertainty": 0.1,
        "unit": "Pa",
        "operator_name": "Viewer Attempt",
        "measured_at": datetime.now(timezone.utc).isoformat(),
    }
    response = await viewer_client.post("/api/v1/measurements", json=payload)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_invalid_dev_user_header_returns_400() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Dev-User": "not-valid-json"},
    ) as c:
        response = await c.get("/api/v1/measurements")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_admin_can_create_device(client: AsyncClient) -> None:
    import uuid
    payload = {
        "name": "Admin Created Device",
        "serial_number": f"SN-ADMIN-{uuid.uuid4().hex[:6].upper()}",
        "device_type": "temperature",
        "location": "Lab B",
        "tenant_id": "tenant-admin-001",
    }
    response = await client.post("/api/v1/devices", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Admin Created Device"
    assert body["device_type"] == "temperature"
