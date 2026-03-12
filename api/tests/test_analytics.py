"""Tests for analytics endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.database import AnalysisResult, CalibrationMeasurement, Device
from src.models.enums import DeviceType, MeasurementStatus


@pytest.fixture
async def sample_device(db_session: AsyncSession) -> Device:
    device = Device(
        id="DEVICE-ANALYTICS-001",
        name="Analytics Test Pressure Gauge",
        device_type=DeviceType.PRESSURE,
        serial_number="SN-ANA-001",
        manufacturer="TestMfg",
        model="Model-X",
        location="Lab A",
    )
    db_session.add(device)
    await db_session.commit()
    await db_session.refresh(device)
    return device


@pytest.fixture
async def measurements_with_analysis(
    db_session: AsyncSession, sample_device: Device
) -> list[CalibrationMeasurement]:
    measurements = []
    for i in range(5):
        m = CalibrationMeasurement(
            id=str(uuid.uuid4()),
            device_id=sample_device.id,
            measurement_type=DeviceType.PRESSURE,
            measured_value=100.0 + i * 0.1,
            reference_value=100.0,
            uncertainty=0.5,
            unit="bar",
            operator_id="op-001",
            status=MeasurementStatus.VALIDATED if i < 4 else MeasurementStatus.ANOMALY,
        )
        db_session.add(m)
        measurements.append(m)

    await db_session.flush()

    for i, m in enumerate(measurements):
        is_anomaly = i == 4
        result = AnalysisResult(
            id=str(uuid.uuid4()),
            measurement_id=m.id,
            z_score=0.2 * (i + 1),
            is_anomaly=is_anomaly,
            deviation_pct=abs(m.measured_value - m.reference_value) / m.reference_value * 100,
            confidence=0.95,
            model_version="1.0.0",
            details={"threshold": 3.0},
        )
        db_session.add(result)

    await db_session.commit()
    return measurements


class TestAnalyticsSummary:
    async def test_summary_returns_200(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/analytics/summary")
        assert response.status_code == 200

    async def test_summary_structure(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/analytics/summary")
        data = response.json()
        assert "total_measurements" in data
        assert "validated_count" in data
        assert "anomaly_count" in data
        assert "anomaly_rate_pct" in data
        assert "device_count" in data

    async def test_summary_counts_measurements(
        self, client: AsyncClient, measurements_with_analysis: list
    ) -> None:
        response = await client.get("/api/v1/analytics/summary")
        data = response.json()
        assert data["total_measurements"] >= 5
        assert data["validated_count"] >= 4
        assert data["anomaly_count"] >= 1

    async def test_summary_anomaly_rate_calculated(
        self, client: AsyncClient, measurements_with_analysis: list
    ) -> None:
        response = await client.get("/api/v1/analytics/summary")
        data = response.json()
        if data["total_measurements"] > 0:
            expected_rate = data["anomaly_count"] / data["total_measurements"] * 100
            assert abs(data["anomaly_rate_pct"] - expected_rate) < 0.01

    async def test_summary_requires_auth_in_prod(
        self, operator_client: AsyncClient
    ) -> None:
        """Operator can view analytics."""
        response = await operator_client.get("/api/v1/analytics/summary")
        assert response.status_code == 200

    async def test_summary_viewer_can_access(
        self, viewer_client: AsyncClient
    ) -> None:
        response = await viewer_client.get("/api/v1/analytics/summary")
        assert response.status_code == 200


class TestDeviceTrend:
    async def test_trend_returns_200_for_existing_device(
        self,
        client: AsyncClient,
        sample_device: Device,
        measurements_with_analysis: list,
    ) -> None:
        response = await client.get(f"/api/v1/analytics/devices/{sample_device.id}/trend")
        assert response.status_code == 200

    async def test_trend_structure(
        self,
        client: AsyncClient,
        sample_device: Device,
        measurements_with_analysis: list,
    ) -> None:
        response = await client.get(f"/api/v1/analytics/devices/{sample_device.id}/trend")
        data = response.json()
        assert "device_id" in data
        assert "points" in data
        assert isinstance(data["points"], list)

    async def test_trend_points_have_required_fields(
        self,
        client: AsyncClient,
        sample_device: Device,
        measurements_with_analysis: list,
    ) -> None:
        response = await client.get(f"/api/v1/analytics/devices/{sample_device.id}/trend")
        data = response.json()
        if data["points"]:
            point = data["points"][0]
            assert "timestamp" in point
            assert "measured_value" in point
            assert "reference_value" in point

    async def test_trend_unknown_device_returns_404(
        self, client: AsyncClient
    ) -> None:
        response = await client.get("/api/v1/analytics/devices/NONEXISTENT-DEVICE/trend")
        assert response.status_code == 404

    async def test_trend_device_id_in_response(
        self,
        client: AsyncClient,
        sample_device: Device,
        measurements_with_analysis: list,
    ) -> None:
        response = await client.get(f"/api/v1/analytics/devices/{sample_device.id}/trend")
        data = response.json()
        assert data["device_id"] == sample_device.id

    async def test_trend_viewer_can_access(
        self,
        viewer_client: AsyncClient,
        sample_device: Device,
        measurements_with_analysis: list,
    ) -> None:
        response = await viewer_client.get(
            f"/api/v1/analytics/devices/{sample_device.id}/trend"
        )
        assert response.status_code == 200


class TestAnomalies:
    async def test_anomalies_returns_200(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/analytics/anomalies")
        assert response.status_code == 200

    async def test_anomalies_is_list(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/analytics/anomalies")
        data = response.json()
        assert isinstance(data, list)

    async def test_anomalies_contain_flagged_measurements(
        self, client: AsyncClient, measurements_with_analysis: list
    ) -> None:
        response = await client.get("/api/v1/analytics/anomalies")
        data = response.json()
        assert len(data) >= 1

    async def test_anomaly_entry_has_required_fields(
        self, client: AsyncClient, measurements_with_analysis: list
    ) -> None:
        response = await client.get("/api/v1/analytics/anomalies")
        data = response.json()
        if data:
            entry = data[0]
            assert "measurement_id" in entry
            assert "device_id" in entry
            assert "z_score" in entry
            assert "deviation_pct" in entry

    async def test_anomalies_filter_by_device(
        self,
        client: AsyncClient,
        sample_device: Device,
        measurements_with_analysis: list,
    ) -> None:
        response = await client.get(
            f"/api/v1/analytics/anomalies?device_id={sample_device.id}"
        )
        assert response.status_code == 200
        data = response.json()
        for entry in data:
            assert entry["device_id"] == sample_device.id

    async def test_anomalies_viewer_can_access(
        self, viewer_client: AsyncClient
    ) -> None:
        response = await viewer_client.get("/api/v1/analytics/anomalies")
        assert response.status_code == 200

    async def test_anomalies_empty_when_no_anomalies(
        self, client: AsyncClient
    ) -> None:
        """Empty db or all-validated → returns empty list, not error."""
        response = await client.get(
            "/api/v1/analytics/anomalies?device_id=NO-SUCH-DEVICE-XYZ"
        )
        assert response.status_code == 200
        assert response.json() == []
