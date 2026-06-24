"""
schemas/ — Pydantic request / response schemas.

Separate from SQLAlchemy models (models/) which map to DB tables.
API routers import from here for response_model declarations.
"""

from app.schemas.analytics import CapitalStatusResponse, PerformanceAnalyticsResponse
from app.schemas.health import DetailedHealthResponse, HealthResponse
from app.schemas.opportunity import OpportunityResponse, OpportunityStatsResponse
from app.schemas.order import OrderResponse, OrderStatsResponse
from app.schemas.portfolio import PortfolioSummaryResponse
from app.schemas.position import PositionResponse, PositionStatsResponse
from app.schemas.price import PriceSnapshotResponse, PriceStatsResponse
from app.schemas.risk import RiskEventResponse, RiskStatsResponse
from app.schemas.signal import SignalResponse, SignalStatsResponse
from app.schemas.strategy import StrategyStatsResponse, TradeDecisionResponse
from app.schemas.universe import (
    AssetStats,
    SyncResponse,
    TimeframeStats,
    UniverseMarketResponse,
    UniverseStatsResponse,
)

__all__ = [
    "AssetStats",
    "CapitalStatusResponse",
    "DetailedHealthResponse",
    "HealthResponse",
    "OpportunityResponse",
    "OpportunityStatsResponse",
    "OrderResponse",
    "OrderStatsResponse",
    "PerformanceAnalyticsResponse",
    "PortfolioSummaryResponse",
    "PositionResponse",
    "PositionStatsResponse",
    "PriceSnapshotResponse",
    "PriceStatsResponse",
    "RiskEventResponse",
    "RiskStatsResponse",
    "SignalResponse",
    "SignalStatsResponse",
    "StrategyStatsResponse",
    "SyncResponse",
    "TimeframeStats",
    "TradeDecisionResponse",
    "UniverseMarketResponse",
    "UniverseStatsResponse",
]
