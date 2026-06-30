from fastapi import APIRouter

from app.api.v1.analytics import router as analytics_router
from app.api.v1.health import router as health_router
from app.api.v1.price import router as price_router
from app.api.v1.opportunities import router as opportunities_router
from app.api.v1.orders import router as orders_router
from app.api.v1.signals import router as signals_router
from app.api.v1.strategies import router as strategies_router
from app.api.v1.universe import router as universe_router
from app.api.v1.positions import router as positions_router
from app.api.v1.risk import router as risk_router
from app.api.v1.portfolio import router as portfolio_router
from app.api.v1.btc_candles import router as btc_candles_router
from app.api.v1.crypto_ticker import router as crypto_ticker_router

api_router = APIRouter()

api_router.include_router(health_router, tags=["health"])
api_router.include_router(universe_router)
api_router.include_router(price_router)
api_router.include_router(signals_router)
api_router.include_router(opportunities_router)
api_router.include_router(strategies_router)
api_router.include_router(orders_router)
api_router.include_router(positions_router)
api_router.include_router(risk_router)
api_router.include_router(portfolio_router)
api_router.include_router(analytics_router)
api_router.include_router(btc_candles_router)
api_router.include_router(crypto_ticker_router)
