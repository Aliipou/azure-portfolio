"""Blob storage writer — Azure Blob in prod, local filesystem in dev."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


async def upload_raw_measurement(
    measurement_id: str,
    device_id: str,
    data: dict[object, object],
) -> str:
    """
    Upload raw measurement JSON to Blob Storage.
    Path: raw-measurements/{device_id}/{year}/{month}/{measurement_id}.json
    Returns the blob URL or local path.
    """
    now = datetime.now(timezone.utc)
    blob_path = f"{device_id}/{now.year}/{now.month:02d}/{measurement_id}.json"
    content = json.dumps(data, default=str).encode()

    account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME", "")
    dev_mode = os.getenv("DEV_MODE", "true").lower() == "true"

    if dev_mode or not account_name:
        return await _write_local(blob_path, content)
    return await _write_blob(account_name, blob_path, content)


async def _write_local(blob_path: str, content: bytes) -> str:
    container = os.getenv("AZURE_STORAGE_CONTAINER_RAW", "raw-measurements")
    base = Path("/tmp/calibration-blobs") / container
    full_path = base / blob_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(content)
    return f"file://{full_path}"


async def _write_blob(account_name: str, blob_path: str, content: bytes) -> str:
    from azure.identity.aio import DefaultAzureCredential
    from azure.storage.blob.aio import BlobServiceClient

    container = os.getenv("AZURE_STORAGE_CONTAINER_RAW", "raw-measurements")
    account_url = f"https://{account_name}.blob.core.windows.net"

    async with DefaultAzureCredential() as credential:
        async with BlobServiceClient(account_url, credential=credential) as client:
            blob = client.get_blob_client(container=container, blob=blob_path)
            await blob.upload_blob(content, overwrite=True)
            return blob.url
