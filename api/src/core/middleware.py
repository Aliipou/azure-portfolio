"""Request ID, timing, and error handler middleware."""

from __future__ import annotations

import time
import uuid

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.models.schemas import ErrorResponse


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Attach X-Request-ID to every request/response."""

    async def dispatch(self, request: Request, call_next: Any) -> Response:  # type: ignore[override]
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class TimingMiddleware(BaseHTTPMiddleware):
    """Add X-Response-Time header."""

    async def dispatch(self, request: Request, call_next: Any) -> Response:  # type: ignore[override]
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
        return response


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return RFC 7807 Problem Details for all errors."""
    from fastapi import HTTPException
    if isinstance(exc, HTTPException):
        error = ErrorResponse(
            type=f"https://calibration.beamex.io/errors/{exc.status_code}",
            title=exc.detail if isinstance(exc.detail, str) else "Error",
            status=exc.status_code,
            detail=exc.detail if isinstance(exc.detail, str) else str(exc.detail),
            request_id=getattr(request.state, "request_id", None),
        )
        return JSONResponse(status_code=exc.status_code, content=error.model_dump())

    error = ErrorResponse(
        type="https://calibration.beamex.io/errors/500",
        title="Internal Server Error",
        status=500,
        detail="An unexpected error occurred.",
        request_id=getattr(request.state, "request_id", None),
    )
    return JSONResponse(status_code=500, content=error.model_dump())


# needed for type hints in BaseHTTPMiddleware
from typing import Any  # noqa: E402
