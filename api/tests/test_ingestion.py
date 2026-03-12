"""Tests for measurement ingestion endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


def _measurement_payload(device_id: str | None = None) -> dict[str, object]:
    return {
        "device_id": device_id or str(uuid.uuid4()),
        "measured_value": 101.5,
        "reference_value": 100.0,
        "uncertainty": 0.1,
        "unit": "Pa",
        "temperature_c": 22.0,
        "humidity_pct": 50.0,
        "operator_name": "Technician A",
        "measured_at": datetime.now(timezone.utc).isoformat(),
    }


@pytest.mark.asyncio
async def test_create_measurement_happy_path(client: AsyncClient) -> None:
    with patch("src.services.ingestion.IngestionService._enqueue", new=AsyncMock()):
        response = await client.post("/api/v1/measurements", json=_measurement_payload())
    assert response.status_code == 202
    body = response.json()
    assert "id" in body
    assert body["status"] == "received"
    assert body["measured_value"] == 101.5


@pytest.mark.asyncio
async def test_create_measurement_missing_required_field(client: AsyncClient) -> None:
    payload = _measurement_payload()
    del payload["uncertainty"]
    response = await client.post("/api/v1/measurements", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_measurement_zero_uncertainty_rejected(client: AsyncClient) -> None:
    payload = _measurement_payload()
    payload["uncertainty"] = 0.0
    response = await client.post("/api/v1/measurements", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_measurements_returns_list(client: AsyncClient) -> None:
    with patch("src.services.ingestion.IngestionService._enqueue", new=AsyncMock()):
        await client.post("/api/v1/measurements", json=_measurement_payload())

    response = await client.get("/api/v1/measurements")
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert "total" in body
    assert isinstance(body["items"], list)


@pytest.mark.asyncio
async def test_get_measurement_by_id(client: AsyncClient) -> None:
    with patch("src.services.ingestion.IngestionService._enqueue", new=AsyncMock()):
        create_resp = await client.post("/api/v1/measurements", json=_measurement_payload())
    measurement_id = create_resp.json()["id"]

    response = await client.get(f"/api/v1/measurements/{measurement_id}")
    assert response.status_code == 200
    assert response.json()["id"] == measurement_id


@pytest.mark.asyncio
async def test_get_nonexistent_measurement_returns_404(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/measurements/{uuid.uuid4()}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_operator_can_create_measurement(operator_client: AsyncClient) -> None:
    with patch("src.services.ingestion.IngestionService._enqueue", new=AsyncMock()):
        response = await operator_client.post("/api/v1/measurements", json=_measurement_payload())
    assert response.status_code == 202


@pytest.mark.asyncio
async def test_pagination_skip_limit(client: AsyncClient) -> None:
    response = await client.get("/api/v1/measurements?skip=0&limit=5")
    assert response.status_code == 200
    body = response.json()
    assert body["page_size"] == 5
