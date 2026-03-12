"""Service Bus (or Redis) listener loop with graceful shutdown."""

from __future__ import annotations

import asyncio
import json
import os
import signal
import sys

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.processor import process_measurement

logger = structlog.get_logger("worker")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/calibration_db",
)
QUEUE_NAME = os.getenv("SERVICEBUS_QUEUE_NAME", "calibration-measurements")
USE_REDIS = os.getenv("USE_REDIS_QUEUE", "true").lower() == "true"
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
MAX_RETRIES = 3

engine = create_async_engine(DATABASE_URL, pool_pre_ping=True, pool_size=3)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

_shutdown = asyncio.Event()


def _handle_signal(sig: int, _: object) -> None:
    logger.info("shutdown_signal", signal=sig)
    _shutdown.set()


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


async def _process_message(raw: str) -> None:
    """Deserialize and process one message with retry logic."""
    data = json.loads(raw)
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with SessionLocal() as db:
                await process_measurement(
                    measurement_id=data["measurement_id"],
                    device_id=data["device_id"],
                    measured_value=float(data["measured_value"]),
                    reference_value=float(data["reference_value"]),
                    uncertainty=float(data["uncertainty"]),
                    unit=data["unit"],
                    db=db,
                )
            return
        except Exception as exc:
            logger.warning("process_attempt_failed", attempt=attempt, error=str(exc))
            if attempt == MAX_RETRIES:
                logger.error("message_dead_lettered", error=str(exc), data=data)
                raise
            await asyncio.sleep(2 ** attempt)  # exponential backoff


async def _redis_loop() -> None:
    """Listen to Redis list (local dev replacement for Service Bus)."""
    import redis.asyncio as redis
    client = redis.from_url(REDIS_URL)
    logger.info("redis_listener_started", queue=QUEUE_NAME)
    try:
        while not _shutdown.is_set():
            result = await client.brpop(QUEUE_NAME, timeout=2)
            if result:
                _, raw = result
                await _process_message(raw.decode())
    finally:
        await client.aclose()


async def _servicebus_loop() -> None:
    """Listen to Azure Service Bus queue."""
    from azure.servicebus.aio import ServiceBusClient
    conn_str = os.getenv("SERVICEBUS_CONNECTION_STRING", "")
    logger.info("servicebus_listener_started", queue=QUEUE_NAME)
    async with ServiceBusClient.from_connection_string(conn_str) as client:
        async with client.get_queue_receiver(QUEUE_NAME, max_wait_time=5) as receiver:
            while not _shutdown.is_set():
                messages = await receiver.receive_messages(max_message_count=10, max_wait_time=5)
                for msg in messages:
                    try:
                        await _process_message(str(msg))
                        await receiver.complete_message(msg)
                    except Exception:
                        await receiver.dead_letter_message(
                            msg, reason="ProcessingFailed", error_description="Max retries exceeded"
                        )


async def main() -> None:
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_log_level,
            structlog.processors.JSONRenderer(),
        ]
    )
    logger.info("worker_starting", use_redis=USE_REDIS)

    if USE_REDIS:
        await _redis_loop()
    else:
        await _servicebus_loop()

    logger.info("worker_stopped")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
