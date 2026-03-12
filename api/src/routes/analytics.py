"""Analytics query endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth import get_current_user
from src.db.session import get_db
from src.models.schemas import AnomalyEntry, AnalyticsSummary, DeviceTrend, UserClaims
from src.services.analytics import AnalyticsService

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/summary", response_model=AnalyticsSummary)
async def get_summary(
    _user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalyticsSummary:
    """Aggregated platform statistics."""
    service = AnalyticsService(db)
    return await service.get_summary()


@router.get("/devices/{device_id}/trend", response_model=DeviceTrend)
async def get_device_trend(
    device_id: uuid.UUID,
    limit: int = 100,
    _user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DeviceTrend:
    """Time-series measurements + anomaly scores for a device."""
    service = AnalyticsService(db)
    return await service.get_device_trend(device_id, limit=limit)


@router.get("/anomalies", response_model=list[AnomalyEntry])
async def get_anomalies(
    limit: int = 50,
    _user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AnomalyEntry]:
    """Recent anomaly detections with device context."""
    service = AnalyticsService(db)
    return await service.get_anomalies(limit=limit)
