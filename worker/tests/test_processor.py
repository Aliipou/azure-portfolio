"""Tests for the measurement processor."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestProcessor:
    @pytest.mark.asyncio
    async def test_process_measurement_normal(self) -> None:
        """Normal measurement: status set to VALIDATED."""
        measurement_id = str(uuid.uuid4())
        device_id = str(uuid.uuid4())

        mock_measurement = MagicMock()
        mock_measurement.id = uuid.UUID(measurement_id)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_measurement]
        mock_result.scalar_one_or_none.return_value = mock_measurement

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch("src.processor.upload_raw_measurement", new=AsyncMock(return_value="file:///tmp/test.json")):
            with patch("src.processor._detector") as mock_det:
                from src.anomaly_detector import AnomalyResult
                mock_det.analyze.return_value = AnomalyResult(
                    anomaly_score=0.5,
                    is_anomaly=False,
                    deviation_pct=0.1,
                    confidence=0.95,
                    model_version="1.0.0",
                    details={"z_score": 0.5, "threshold": 3.0, "uncertainty": 0.5, "absolute_deviation": 0.25},
                )
                from src.processor import process_measurement
                await process_measurement(
                    measurement_id=measurement_id,
                    device_id=device_id,
                    measured_value=100.25,
                    reference_value=100.0,
                    uncertainty=0.5,
                    unit="Pa",
                    db=mock_db,
                )

        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_measurement_anomaly(self) -> None:
        """Anomaly measurement: status set to ANOMALY."""
        measurement_id = str(uuid.uuid4())
        device_id = str(uuid.uuid4())

        mock_measurement = MagicMock()
        mock_measurement.id = uuid.UUID(measurement_id)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_measurement

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch("src.processor.upload_raw_measurement", new=AsyncMock(return_value="file:///tmp/test.json")):
            with patch("src.processor._detector") as mock_det:
                from src.anomaly_detector import AnomalyResult
                from src.models.enums import MeasurementStatus
                mock_det.analyze.return_value = AnomalyResult(
                    anomaly_score=5.0,
                    is_anomaly=True,
                    deviation_pct=8.0,
                    confidence=0.99,
                    model_version="1.0.0",
                    details={"z_score": 5.0, "threshold": 3.0, "uncertainty": 0.5, "absolute_deviation": 2.5},
                )
                from src.processor import process_measurement
                await process_measurement(
                    measurement_id=measurement_id,
                    device_id=device_id,
                    measured_value=102.5,
                    reference_value=100.0,
                    uncertainty=0.5,
                    unit="Pa",
                    db=mock_db,
                )

        assert mock_measurement.status == MeasurementStatus.ANOMALY

    @pytest.mark.asyncio
    async def test_process_measurement_not_found(self) -> None:
        """Measurement not in DB: logs warning, does not crash."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch("src.processor.upload_raw_measurement", new=AsyncMock(return_value="file:///x")):
            with patch("src.processor._detector") as mock_det:
                from src.anomaly_detector import AnomalyResult
                mock_det.analyze.return_value = AnomalyResult(0.0, False, 0.0, 1.0, "1.0.0", {})
                from src.processor import process_measurement
                await process_measurement(
                    measurement_id=str(uuid.uuid4()),
                    device_id=str(uuid.uuid4()),
                    measured_value=100.0,
                    reference_value=100.0,
                    uncertainty=0.5,
                    unit="Pa",
                    db=mock_db,
                )
        # Should not commit since measurement not found
        mock_db.commit.assert_not_called()
