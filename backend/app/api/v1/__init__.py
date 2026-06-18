from fastapi import APIRouter

from app.api.v1.discovery import router as discovery_router
from app.api.v1.health import router as health_router
from app.api.v1.markets import router as markets_router
from app.api.v1.scanner import router as scanner_router

api_router = APIRouter()

api_router.include_router(health_router, tags=["health"])
api_router.include_router(markets_router)
api_router.include_router(discovery_router)
api_router.include_router(scanner_router)
