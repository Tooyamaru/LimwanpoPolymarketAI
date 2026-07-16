from fastapi import APIRouter

from app.api.v1.alerts import router as alerts_router
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
from app.api.v1.trades import router as trades_router
from app.api.v1.replay import router as replay_router
from app.api.v1.evaluation import router as evaluation_router
from app.api.v1.momentum import router as momentum_router
from app.api.v1.trend import router as trend_router
from app.api.v1.volatility import router as volatility_router
from app.api.v1.decision import router as decision_router
from app.api.v1.market_quality import router as market_quality_router
from app.api.v1.market_context import router as market_context_router
from app.api.v1.orderbook import router as orderbook_router
from app.api.v1.funding import router as funding_router
from app.api.v1.news import router as news_router
from app.api.v1.outcome_learning import router as outcome_learning_router
from app.api.v1.engine_performance import router as engine_performance_router
from app.api.v1.engine_weights import router as engine_weights_router
from app.api.v1.portfolio_allocation import router as portfolio_allocation_router
from app.api.v1.feed import router as feed_router
from app.api.v1.live_trades import router as live_trades_router

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
api_router.include_router(trades_router)
api_router.include_router(replay_router)
api_router.include_router(evaluation_router)
api_router.include_router(momentum_router)
api_router.include_router(trend_router)
api_router.include_router(volatility_router)
api_router.include_router(decision_router)
api_router.include_router(market_quality_router)
api_router.include_router(market_context_router)
api_router.include_router(orderbook_router)
api_router.include_router(funding_router)
api_router.include_router(news_router)
api_router.include_router(outcome_learning_router)
api_router.include_router(engine_performance_router)
api_router.include_router(engine_weights_router)
api_router.include_router(portfolio_allocation_router)
api_router.include_router(feed_router)
api_router.include_router(alerts_router)
api_router.include_router(live_trades_router)
