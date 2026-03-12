"""Pydantic v2 request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .enums import DeviceType, MeasurementStatus, UserRole


# ── Device Schemas ────────────────────────────────────────────────────────────

class DeviceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    serial_number: str = Field(..., min_length=1, max_length=100)
    device_type: DeviceType
    location: str = Field(..., min_length=1, max_length=300)
    tenant_id: str = Field(..., min_length=1, max_length=100)


class DeviceUpdate(BaseModel):
    name: str | None = Field(None, max_length=200)
    location: str | None = Field(None, max_length=300)
    is_active: bool | None = None


class DeviceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    serial_number: str
    device_type: DeviceType
    location: str
    tenant_id: str
    last_calibration_at: datetime | None
    is_active: bool
    created_at: datetime


# ── Measurement Schemas ───────────────────────────────────────────────────────

class MeasurementCreate(BaseModel):
    device_id: uuid.UUID
    measured_value: float
    reference_value: float
    uncertainty: float = Field(..., gt=0, description="Measurement uncertainty (must be > 0)")
    unit: str = Field(..., min_length=1, max_length=50)
    temperature_c: float | None = Field(None, ge=-273.15, le=1000)
    humidity_pct: float | None = Field(None, ge=0, le=100)
    operator_name: str = Field(..., min_length=1, max_length=200)
    measured_at: datetime

    @field_validator("measured_value", "reference_value")
    @classmethod
    def validate_finite(cls, v: float) -> float:
        import math
        if not math.isfinite(v):
            raise ValueError("Value must be finite")
        return v


class MeasurementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    device_id: uuid.UUID
    measured_value: float
    reference_value: float
    uncertainty: float
    unit: str
    temperature_c: float | None
    humidity_pct: float | None
    operator_name: str
    status: MeasurementStatus
    raw_data_url: str | None
    measured_at: datetime
    created_at: datetime
    analysis: AnalysisResponse | None = None


class MeasurementList(BaseModel):
    items: list[MeasurementResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


# ── Analysis Schemas ──────────────────────────────────────────────────────────

class AnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    anomaly_score: float
    is_anomaly: bool
    deviation_pct: float
    confidence: float
    model_version: str
    details: dict[str, Any] | None
    created_at: datetime


# ── Analytics Schemas ─────────────────────────────────────────────────────────

class AnalyticsSummary(BaseModel):
    total_measurements: int
    total_devices: int
    anomaly_count: int
    anomaly_rate_pct: float
    avg_deviation_pct: float
    measurements_by_device_type: dict[str, int]
    measurements_by_status: dict[str, int]


class TrendPoint(BaseModel):
    timestamp: datetime
    measured_value: float
    reference_value: float
    deviation_pct: float
    is_anomaly: bool
    anomaly_score: float | None


class DeviceTrend(BaseModel):
    device_id: uuid.UUID
    device_name: str
    unit: str
    trend: list[TrendPoint]


class AnomalyEntry(BaseModel):
    measurement_id: uuid.UUID
    device_id: uuid.UUID
    device_name: str
    serial_number: str
    measured_value: float
    reference_value: float
    deviation_pct: float
    anomaly_score: float
    measured_at: datetime


# ── Auth Schemas ──────────────────────────────────────────────────────────────

class UserClaims(BaseModel):
    sub: str
    email: str | None = None
    roles: list[UserRole] = []
    tenant_id: str | None = None
    name: str | None = None


# ── Health Schemas ────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str = "1.0.0"
    environment: str


class ReadinessResponse(BaseModel):
    status: str
    checks: dict[str, str]


# ── Error Schemas ─────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    type: str
    title: str
    status: int
    detail: str
    request_id: str | None = None
