"""Shared test fixtures for the calibration API."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.main import app
from src.models.database import Base, CalibrationMeasurement, Device
from src.models.enums import DeviceType, MeasurementStatus

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSession = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables() -> AsyncGenerator[None, None]:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSession() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async test client with dev auth bypass."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Dev-User": '{"sub":"test-user","roles":["Admin"],"email":"test@test.com"}'},
    ) as c:
        yield c


@pytest_asyncio.fixture
async def operator_client() -> AsyncGenerator[AsyncClient, None]:
    """Client with Operator role."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Dev-User": '{"sub":"operator-user","roles":["Operator"]}'},
    ) as c:
        yield c


@pytest_asyncio.fixture
async def viewer_client() -> AsyncGenerator[AsyncClient, None]:
    """Client with Viewer role (read-only)."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Dev-User": '{"sub":"viewer-user","roles":["Viewer"]}'},
    ) as c:
        yield c


@pytest.fixture
def sample_device_data() -> dict[str, str]:
    return {
        "name": "Pressure Calibrator Model-X",
        "serial_number": f"SN-{uuid.uuid4().hex[:8].upper()}",
        "device_type": "pressure",
        "location": "Lab A, Rack 3",
        "tenant_id": "tenant-beamex-001",
    }


@pytest.fixture
def sample_measurement_data() -> dict[str, object]:
    return {
        "device_id": str(uuid.uuid4()),  # Will be replaced in tests needing real device
        "measured_value": 100.23,
        "reference_value": 100.00,
        "uncertainty": 0.05,
        "unit": "Pa",
        "temperature_c": 22.5,
        "humidity_pct": 45.0,
        "operator_name": "Technician A",
        "measured_at": datetime.now(timezone.utc).isoformat(),
    }
