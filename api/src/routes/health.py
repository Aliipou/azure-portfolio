"""Liveness and readiness health check endpoints."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from src.config import settings
from src.db.session import engine
from src.models.schemas import HealthResponse, ReadinessResponse

router = APIRouter(tags=["health"])


@router.get("/healthz", response_model=HealthResponse, summary="Liveness probe")
async def liveness() -> HealthResponse:
    """Returns 200 if the process is alive."""
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        environment=settings.app_env,
    )


@router.get("/readyz", response_model=ReadinessResponse, summary="Readiness probe")
async def readiness() -> JSONResponse:
    """Returns 200 if the app can serve traffic (DB reachable)."""
    checks: dict[str, str] = {}
    all_ok = True

    # Database check
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"
        all_ok = False

    status_code = 200 if all_ok else 503
    return JSONResponse(
        status_code=status_code,
        content=ReadinessResponse(
            status="ready" if all_ok else "not_ready",
            checks=checks,
        ).model_dump(),
    )
