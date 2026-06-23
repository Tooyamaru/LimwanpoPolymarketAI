"""
Health endpoints.
"""

from datetime import datetime, timezone

from fastapi import APIRouter

from app.config.settings import settings
from app.core.database import check_db_health
from app.core.redis import check_redis_health
from app.schemas.health import DetailedHealthResponse, HealthResponse

router = APIRouter()

_start_time: datetime = datetime.now(timezone.utc)


def get_uptime_seconds() -> float:
    return (datetime.now(timezone.utc) - _start_time).total_seconds()


@router.get("/health", response_model=HealthResponse, summary="Basic health check")
async def health() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        version=settings.APP_VERSION,
        uptime_seconds=get_uptime_seconds(),
    )


@router.get(
    "/health/detailed",
    response_model=DetailedHealthResponse,
    summary="Detailed health check with dependency status",
)
async def health_detailed() -> DetailedHealthResponse:
    db_ok = await check_db_health()
    redis_ok = await check_redis_health()
    overall = "healthy" if db_ok else "degraded"

    return DetailedHealthResponse(
        status=overall,
        version=settings.APP_VERSION,
        uptime_seconds=get_uptime_seconds(),
        database="healthy" if db_ok else "unhealthy",
        redis="healthy" if redis_ok else "unhealthy",
    )
