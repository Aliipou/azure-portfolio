"""Measurement ingestion endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth import get_current_user, require_role
from src.db.session import get_db
from src.models.enums import MeasurementStatus, UserRole
from src.models.schemas import (
    MeasurementCreate,
    MeasurementList,
    MeasurementResponse,
    UserClaims,
)
from src.services.ingestion import IngestionService

router = APIRouter(prefix="/api/v1/measurements", tags=["ingestion"])


@router.post("", response_model=MeasurementResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_measurement(
    payload: MeasurementCreate,
    user: UserClaims = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
    db: AsyncSession = Depends(get_db),
) -> MeasurementResponse:
    """Accept a calibration measurement and enqueue it for processing."""
    service = IngestionService(db)
    measurement = await service.create_measurement(payload, operator_id=user.sub)
    return MeasurementResponse.model_validate(measurement)


@router.get("", response_model=MeasurementList)
async def list_measurements(
    device_id: uuid.UUID | None = Query(None),
    measurement_status: MeasurementStatus | None = Query(None, alias="status"),
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    _user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeasurementList:
    service = IngestionService(db)
    items, total = await service.list_measurements(
        device_id=device_id,
        status=measurement_status,
        skip=skip,
        limit=limit,
    )
    return MeasurementList(
        items=[MeasurementResponse.model_validate(m) for m in items],
        total=total,
        page=skip // limit + 1,
        page_size=limit,
        has_more=(skip + limit) < total,
    )


@router.get("/{measurement_id}", response_model=MeasurementResponse)
async def get_measurement(
    measurement_id: uuid.UUID,
    _user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeasurementResponse:
    service = IngestionService(db)
    measurement = await service.get_measurement(measurement_id)
    if not measurement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Measurement not found"
        )
    return MeasurementResponse.model_validate(measurement)
