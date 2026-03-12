"""Analytics service: aggregations, trends, anomaly queries."""

from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.logging import get_logger
from src.models.database import AnalysisResult, CalibrationMeasurement, Device
from src.models.enums import MeasurementStatus
from src.models.schemas import (
    AnomalyEntry,
    AnalyticsSummary,
    DeviceTrend,
    TrendPoint,
)

logger = get_logger(__name__)


class AnalyticsService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_summary(self) -> AnalyticsSummary:
        # Total measurements
        total_result = await self._db.execute(
            select(func.count()).select_from(CalibrationMeasurement)
        )
        total = total_result.scalar_one()

        # Total devices
        device_result = await self._db.execute(select(func.count()).select_from(Device))
        total_devices = device_result.scalar_one()

        # Anomaly count
        anomaly_result = await self._db.execute(
            select(func.count()).select_from(CalibrationMeasurement).where(
                CalibrationMeasurement.status == MeasurementStatus.ANOMALY
            )
        )
        anomaly_count = anomaly_result.scalar_one()

        # Avg deviation
        avg_result = await self._db.execute(
            select(func.avg(AnalysisResult.deviation_pct)).select_from(AnalysisResult)
        )
        avg_deviation = float(avg_result.scalar_one() or 0)

        # By device type
        type_result = await self._db.execute(
            select(Device.device_type, func.count(CalibrationMeasurement.id))
            .join(CalibrationMeasurement, Device.id == CalibrationMeasurement.device_id)
            .group_by(Device.device_type)
        )
        measurements_by_type: dict[str, int] = {
            str(row[0]): row[1] for row in type_result.all()
        }

        # By status
        status_result = await self._db.execute(
            select(CalibrationMeasurement.status, func.count())
            .group_by(CalibrationMeasurement.status)
        )
        measurements_by_status: dict[str, int] = {
            str(row[0]): row[1] for row in status_result.all()
        }

        return AnalyticsSummary(
            total_measurements=total,
            total_devices=total_devices,
            anomaly_count=anomaly_count,
            anomaly_rate_pct=round(anomaly_count / max(total, 1) * 100, 2),
            avg_deviation_pct=round(avg_deviation, 4),
            measurements_by_device_type=measurements_by_type,
            measurements_by_status=measurements_by_status,
        )

    async def get_device_trend(self, device_id: uuid.UUID, *, limit: int = 100) -> DeviceTrend:
        device_result = await self._db.execute(
            select(Device).where(Device.id == device_id)
        )
        device = device_result.scalar_one_or_none()

        measurements_result = await self._db.execute(
            select(CalibrationMeasurement)
            .options(selectinload(CalibrationMeasurement.analysis))
            .where(CalibrationMeasurement.device_id == device_id)
            .order_by(CalibrationMeasurement.measured_at.asc())
            .limit(limit)
        )
        measurements = list(measurements_result.scalars().all())

        trend = [
            TrendPoint(
                timestamp=m.measured_at,
                measured_value=m.measured_value,
                reference_value=m.reference_value,
                deviation_pct=m.analysis.deviation_pct if m.analysis else 0.0,
                is_anomaly=m.status == MeasurementStatus.ANOMALY,
                anomaly_score=m.analysis.anomaly_score if m.analysis else None,
            )
            for m in measurements
        ]

        return DeviceTrend(
            device_id=device_id,
            device_name=device.name if device else "Unknown",
            unit=measurements[0].unit if measurements else "unknown",
            trend=trend,
        )

    async def get_anomalies(self, *, limit: int = 50) -> list[AnomalyEntry]:
        result = await self._db.execute(
            select(CalibrationMeasurement, AnalysisResult, Device)
            .join(AnalysisResult, CalibrationMeasurement.id == AnalysisResult.measurement_id)
            .join(Device, CalibrationMeasurement.device_id == Device.id)
            .where(AnalysisResult.is_anomaly == True)  # noqa: E712
            .order_by(CalibrationMeasurement.measured_at.desc())
            .limit(limit)
        )

        return [
            AnomalyEntry(
                measurement_id=m.id,
                device_id=m.device_id,
                device_name=d.name,
                serial_number=d.serial_number,
                measured_value=m.measured_value,
                reference_value=m.reference_value,
                deviation_pct=a.deviation_pct,
                anomaly_score=a.anomaly_score,
                measured_at=m.measured_at,
            )
            for m, a, d in result.all()
        ]
