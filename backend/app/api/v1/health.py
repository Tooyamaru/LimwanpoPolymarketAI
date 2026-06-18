from fastapi import APIRouter
from pydantic import BaseModel

from app.core.database import check_db_health
from app.core.redis import check_redis_health

router = APIRouter()


class HealthResponse(BaseModel):
    status: str


class DetailedHealthResponse(BaseModel):
    status: str
    database: str
    redis: str
    version: str


@router.get("/health", response_model=HealthResponse, summary="Basic health check")
async def health() -> HealthResponse:
    return HealthResponse(status="healthy")


@router.get(
    "/health/detailed",
    response_model=DetailedHealthResponse,
    summary="Detailed health check with dependency status",
)
async def health_detailed() -> DetailedHealthResponse:
    from app.config.settings import settings

    db_ok = await check_db_health()
    redis_ok = await check_redis_health()

    overall = "healthy" if db_ok and redis_ok else "degraded"

    return DetailedHealthResponse(
        status=overall,
        database="healthy" if db_ok else "unhealthy",
        redis="healthy" if redis_ok else "unhealthy",
        version=settings.APP_VERSION,
    )
