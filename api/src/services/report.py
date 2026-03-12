"""Report generation service: PDF certificate + Blob upload."""

from __future__ import annotations

import io
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.core.logging import get_logger
from src.models.database import CalibrationMeasurement, Device

logger = get_logger(__name__)


class ReportService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def generate_certificate(
        self, device_id: uuid.UUID, *, requested_by: str
    ) -> str:
        """Generate calibration certificate PDF and return download URL."""
        device_result = await self._db.execute(
            select(Device).where(Device.id == device_id)
        )
        device = device_result.scalar_one_or_none()

        measurements_result = await self._db.execute(
            select(CalibrationMeasurement)
            .where(CalibrationMeasurement.device_id == device_id)
            .order_by(CalibrationMeasurement.measured_at.desc())
            .limit(10)
        )
        measurements = list(measurements_result.scalars().all())

        pdf_bytes = self._generate_pdf(device, measurements)
        filename = f"certificate_{device_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.pdf"
        url = await self._upload(pdf_bytes, filename)

        logger.info("certificate_generated", device_id=str(device_id), requested_by=requested_by)
        return url

    def _generate_pdf(
        self,
        device: Device | None,
        measurements: list[CalibrationMeasurement],
    ) -> bytes:
        """Generate PDF using reportlab."""
        try:
            from reportlab.lib.pagesizes import A4  # type: ignore[import]
            from reportlab.pdfgen import canvas  # type: ignore[import]

            buf = io.BytesIO()
            c = canvas.Canvas(buf, pagesize=A4)
            width, height = A4

            c.setFont("Helvetica-Bold", 20)
            c.drawString(72, height - 72, "CALIBRATION CERTIFICATE")

            c.setFont("Helvetica", 12)
            c.drawString(72, height - 110, f"Device: {device.name if device else 'Unknown'}")
            c.drawString(72, height - 130, f"Serial: {device.serial_number if device else 'N/A'}")
            c.drawString(72, height - 150, f"Type: {device.device_type if device else 'N/A'}")
            c.drawString(72, height - 170, f"Generated: {datetime.now(timezone.utc).isoformat()}")

            y = height - 220
            c.setFont("Helvetica-Bold", 11)
            c.drawString(72, y, "Recent Calibration Measurements:")
            y -= 20
            c.setFont("Helvetica", 10)
            for m in measurements[:5]:
                status_str = "✓ PASS" if m.status.value == "validated" else f"⚠ {m.status.value.upper()}"
                c.drawString(
                    72, y,
                    f"{m.measured_at.strftime('%Y-%m-%d')} | "
                    f"Measured: {m.measured_value:.4f} {m.unit} | "
                    f"Reference: {m.reference_value:.4f} | {status_str}"
                )
                y -= 18

            c.save()
            return buf.getvalue()
        except ImportError:
            # Fallback if reportlab not available
            return b"%PDF-1.4 placeholder certificate"

    async def _upload(self, data: bytes, filename: str) -> str:
        if settings.app_env == "dev" or not settings.azure_storage_account_name:
            out_dir = Path("/tmp/calibration-blobs")
            out_dir.mkdir(parents=True, exist_ok=True)
            path = out_dir / filename
            path.write_bytes(data)
            return f"file://{path}"

        from azure.identity.aio import DefaultAzureCredential
        from azure.storage.blob.aio import BlobServiceClient

        account_url = f"https://{settings.azure_storage_account_name}.blob.core.windows.net"
        credential = DefaultAzureCredential()
        async with BlobServiceClient(account_url, credential=credential) as client:
            container = client.get_container_client(settings.azure_storage_container_reports)
            blob = container.get_blob_client(filename)
            await blob.upload_blob(data, overwrite=True)
            return blob.url
