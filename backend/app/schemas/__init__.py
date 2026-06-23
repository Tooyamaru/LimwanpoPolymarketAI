"""
schemas/ — Pydantic request / response schemas.

Separate from SQLAlchemy models (models/) which map to DB tables.
API routers import from here for response_model declarations.
"""

from app.schemas.classifier import ClassificationResponse, ClassifierStatsResponse
from app.schemas.discovery import DiscoveryDiagnosticsResponse, DiscoveryMarketResponse
from app.schemas.health import DetailedHealthResponse, HealthResponse
from app.schemas.market import MarketResponse, SnapshotResponse
from app.schemas.opportunity import OpportunityResponse, OpportunityStatsResponse
from app.schemas.order import OrderResponse, OrderStatsResponse
from app.schemas.position import PositionResponse, PositionStatsResponse
from app.schemas.price import PriceSnapshotResponse, PriceStatsResponse
from app.schemas.risk import RiskEventResponse, RiskStatsResponse
from app.schemas.scanner import AssetBreakdown, ScannerMarketResponse, ScannerStatsResponse
from app.schemas.signal import SignalResponse, SignalStatsResponse
from app.schemas.source_validation import (
    AuditResult,
    DiagnosticsResponse,
    SearchResult,
    ValidationRunResponse,
)
from app.schemas.strategy import StrategyStatsResponse, TradeDecisionResponse
from app.schemas.universe import (
    AssetStats,
    SyncResponse,
    TimeframeStats,
    UniverseMarketResponse,
    UniverseStatsResponse,
)

__all__ = [
    "AuditResult",
    "AssetBreakdown",
    "AssetStats",
    "ClassificationResponse",
    "ClassifierStatsResponse",
    "DetailedHealthResponse",
    "DiagnosticsResponse",
    "DiscoveryDiagnosticsResponse",
    "DiscoveryMarketResponse",
    "HealthResponse",
    "MarketResponse",
    "OpportunityResponse",
    "OpportunityStatsResponse",
    "OrderResponse",
    "OrderStatsResponse",
    "PositionResponse",
    "PositionStatsResponse",
    "PriceSnapshotResponse",
    "PriceStatsResponse",
    "RiskEventResponse",
    "RiskStatsResponse",
    "ScannerMarketResponse",
    "ScannerStatsResponse",
    "SearchResult",
    "SignalResponse",
    "SignalStatsResponse",
    "SnapshotResponse",
    "StrategyStatsResponse",
    "SyncResponse",
    "TimeframeStats",
    "TradeDecisionResponse",
    "UniverseMarketResponse",
    "UniverseStatsResponse",
    "ValidationRunResponse",
]
