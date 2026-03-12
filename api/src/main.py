"""FastAPI application factory."""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.core.logging import configure_logging
from src.core.middleware import RequestIdMiddleware, TimingMiddleware, http_exception_handler
from src.routes import analytics, devices, health, ingestion, reports

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    from src.core.logging import get_logger
    logger = get_logger("startup")
    logger.info("startup", env=settings.app_env, version=settings.app_version)
    yield
    logger.info("shutdown")


app = FastAPI(
    title="Cloud Calibration Data Platform",
    description=(
        "Industrial calibration measurement ingestion, processing, and analytics. "
        "Devices → Ingestion API → Service Bus → Worker → PostgreSQL → Analytics API."
    ),
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Middleware ────────────────────────────────────────────────────────────────

app.add_middleware(TimingMiddleware)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Exception Handlers ────────────────────────────────────────────────────────

app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, http_exception_handler)

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(health.router)
app.include_router(ingestion.router)
app.include_router(devices.router)
app.include_router(analytics.router)
app.include_router(reports.router)
