"""Ingestion service: validate, persist, and enqueue measurements."""

from __future__ import annotations

import json
import uuid

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.core.logging import get_logger
from src.db.repository import BaseRepository
from src.models.database import AuditLog, CalibrationMeasurement
from src.models.enums import MeasurementStatus
from src.models.schemas import MeasurementCreate

logger = get_logger(__name__)


class IngestionService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._measurement_repo = BaseRepository(CalibrationMeasurement, db)
        self._audit_repo = BaseRepository(AuditLog, db)

    async def create_measurement(
        self, payload: MeasurementCreate, *, operator_id: str
    ) -> CalibrationMeasurement:
        measurement = CalibrationMeasurement(
            device_id=payload.device_id,
            measured_value=payload.measured_value,
            reference_value=payload.reference_value,
            uncertainty=payload.uncertainty,
            unit=payload.unit,
            temperature_c=payload.temperature_c,
            humidity_pct=payload.humidity_pct,
            operator_name=payload.operator_name,
            measured_at=payload.measured_at,
            status=MeasurementStatus.RECEIVED,
        )
        measurement = await self._measurement_repo.create(measurement)

        # Audit log
        audit = AuditLog(
            user_id=operator_id,
            action="create_measurement",
            resource_type="CalibrationMeasurement",
            resource_id=str(measurement.id),
        )
        await self._audit_repo.create(audit)

        # Enqueue for worker processing
        await self._enqueue(measurement)

        logger.info(
            "measurement_created",
            measurement_id=str(measurement.id),
            device_id=str(payload.device_id),
            operator=operator_id,
        )
        return measurement

    async def _enqueue(self, measurement: CalibrationMeasurement) -> None:
        message = json.dumps({
            "measurement_id": str(measurement.id),
            "device_id": str(measurement.device_id),
            "measured_value": measurement.measured_value,
            "reference_value": measurement.reference_value,
            "uncertainty": measurement.uncertainty,
            "unit": measurement.unit,
        })

        if settings.use_redis_queue:
            client = redis.from_url(settings.redis_url)
            try:
                await client.lpush(settings.servicebus_queue_name, message)
            finally:
                await client.aclose()
        else:
            from azure.servicebus.aio import ServiceBusClient
            async with ServiceBusClient.from_connection_string(
                settings.servicebus_connection_string
            ) as sb_client:
                async with sb_client.get_queue_sender(
                    settings.servicebus_queue_name
                ) as sender:
                    from azure.servicebus import ServiceBusMessage
                    await sender.send_messages(ServiceBusMessage(message))

    async def list_measurements(
        self,
        *,
        device_id: uuid.UUID | None = None,
        status: MeasurementStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[CalibrationMeasurement], int]:
        filters: dict[str, object] = {}
        if device_id:
            filters["device_id"] = device_id
        if status:
            filters["status"] = status
        return await self._measurement_repo.get_all(skip=skip, limit=limit, filters=filters)

    async def get_measurement(self, measurement_id: uuid.UUID) -> CalibrationMeasurement | None:
        return await self._measurement_repo.get(measurement_id)
