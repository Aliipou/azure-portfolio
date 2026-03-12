"""Device CRUD endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth import get_current_user, require_role
from src.db.repository import BaseRepository
from src.db.session import get_db
from src.models.database import Device
from src.models.enums import DeviceType, UserRole
from src.models.schemas import DeviceCreate, DeviceResponse, DeviceUpdate, UserClaims

router = APIRouter(prefix="/api/v1/devices", tags=["devices"])


@router.get("", response_model=list[DeviceResponse])
async def list_devices(
    device_type: DeviceType | None = Query(None),
    location: str | None = Query(None),
    is_active: bool | None = Query(None, description="Filter by active status"),
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    _user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Device]:
    repo = BaseRepository(Device, db)
    filters: dict[str, object] = {}
    if device_type:
        filters["device_type"] = device_type
    if is_active is not None:
        filters["is_active"] = is_active
    items, _ = await repo.get_all(skip=skip, limit=limit, filters=filters)
    return items


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(
    device_id: uuid.UUID,
    _user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Device:
    repo = BaseRepository(Device, db)
    device = await repo.get(device_id)
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return device


@router.post("", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
async def create_device(
    payload: DeviceCreate,
    user: UserClaims = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> Device:
    repo = BaseRepository(Device, db)
    device = Device(**payload.model_dump())
    return await repo.create(device)


@router.put("/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: uuid.UUID,
    payload: DeviceUpdate,
    _user: UserClaims = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> Device:
    repo = BaseRepository(Device, db)
    device = await repo.get(device_id)
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    data = {k: v for k, v in payload.model_dump().items() if v is not None}
    return await repo.update(device, data)
