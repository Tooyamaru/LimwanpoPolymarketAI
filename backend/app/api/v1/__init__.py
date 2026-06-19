from fastapi import APIRouter

from app.api.v1.classifier import router as classifier_router
from app.api.v1.discovery import router as discovery_router
from app.api.v1.health import router as health_router
from app.api.v1.markets import router as markets_router
from app.api.v1.price import router as price_router
from app.api.v1.scanner import router as scanner_router
from app.api.v1.source_validation import router as source_validation_router
from app.api.v1.universe import router as universe_router

api_router = APIRouter()

api_router.include_router(health_router, tags=["health"])
api_router.include_router(markets_router)
api_router.include_router(discovery_router)
api_router.include_router(scanner_router)
api_router.include_router(classifier_router)
api_router.include_router(source_validation_router)
api_router.include_router(universe_router)
api_router.include_router(price_router)
