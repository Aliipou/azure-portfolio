"""Report generation endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth import require_role
from src.db.session import get_db
from src.models.enums import UserRole
from src.models.schemas import UserClaims
from src.services.report import ReportService

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.post("/calibration-certificate")
async def generate_calibration_certificate(
    device_id: uuid.UUID,
    user: UserClaims = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Generate a calibration certificate PDF and return a download URL."""
    service = ReportService(db)
    download_url = await service.generate_certificate(device_id, requested_by=user.sub)
    return JSONResponse(
        status_code=202,
        content={
            "status": "generated",
            "download_url": download_url,
            "expires_in_seconds": 3600,
        },
    )
