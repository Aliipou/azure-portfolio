"""Measurement processor: fetch → upload raw → detect anomaly → persist result."""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from src.anomaly_detector import AnomalyDetector
from src.storage import upload_raw_measurement

logger = structlog.get_logger(__name__)
_detector = AnomalyDetector()


async def process_measurement(
    measurement_id: str,
    device_id: str,
    measured_value: float,
    reference_value: float,
    uncertainty: float,
    unit: str,
    db: AsyncSession,
) -> None:
    """
    Full processing pipeline for a single measurement:
    1. Upload raw data to Blob Storage
    2. Run anomaly detection
    3. Persist AnalysisResult
    4. Update measurement status
    """
    from sqlalchemy import select
    from src.models.database import AnalysisResult, CalibrationMeasurement
    from src.models.enums import MeasurementStatus

    log = logger.bind(measurement_id=measurement_id, device_id=device_id)
    log.info("processing_start")

    # 1. Upload raw JSON to Blob Storage
    raw_url = await upload_raw_measurement(
        measurement_id=measurement_id,
        device_id=device_id,
        data={
            "measurement_id": measurement_id,
            "device_id": device_id,
            "measured_value": measured_value,
            "reference_value": reference_value,
            "uncertainty": uncertainty,
            "unit": unit,
        },
    )

    # 2. Anomaly detection
    result = _detector.analyze(measured_value, reference_value, uncertainty)
    log.info(
        "anomaly_result",
        is_anomaly=result.is_anomaly,
        z_score=result.anomaly_score,
        deviation_pct=result.deviation_pct,
    )

    # 3. Fetch measurement from DB
    meas_result = await db.execute(
        select(CalibrationMeasurement).where(
            CalibrationMeasurement.id == uuid.UUID(measurement_id)
        )
    )
    measurement = meas_result.scalar_one_or_none()
    if measurement is None:
        log.warning("measurement_not_found")
        return

    # 4. Persist AnalysisResult
    analysis = AnalysisResult(
        measurement_id=uuid.UUID(measurement_id),
        anomaly_score=result.anomaly_score,
        is_anomaly=result.is_anomaly,
        deviation_pct=result.deviation_pct,
        confidence=result.confidence,
        model_version=result.model_version,
        details=result.details,
    )
    db.add(analysis)

    # 5. Update measurement
    measurement.status = (
        MeasurementStatus.ANOMALY if result.is_anomaly else MeasurementStatus.VALIDATED
    )
    measurement.raw_data_url = raw_url

    await db.commit()
    log.info("processing_complete", status=measurement.status)
