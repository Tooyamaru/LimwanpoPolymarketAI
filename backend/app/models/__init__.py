"""
SQLAlchemy ORM models.

Importing this package ensures all models are registered with Base.metadata
so that init_db() creates the correct tables.
"""

from app.core.database import Base
from app.models.market_price_snapshot import MarketPriceSnapshot
from app.models.market_universe import MarketUniverse
from app.models.opportunity import Opportunity
from app.models.signal import Signal
from app.models.order import Order
from app.models.trade_decision import TradeDecision
from app.models.position import Position
from app.models.risk_event import RiskEvent
from app.models.trade_evaluation import TradeEvaluation
from app.models.momentum_score import MomentumScore
from app.models.trend_score import TrendScore
from app.models.volatility_score import VolatilityScore
from app.models.decision_log import DecisionLog
from app.models.market_quality_score import MarketQualityScore
from app.models.market_context_score import MarketContextScore
from app.models.orderbook_score import OrderbookScore
from app.models.funding_score import FundingScore
from app.models.news_score import NewsScore
from app.models.outcome_learning import OutcomeLearning
from app.models.engine_performance import EnginePerformance
from app.models.engine_weight import EngineWeight

__all__ = [
    "Base",
    "MarketPriceSnapshot",
    "MarketUniverse",
    "Opportunity",
    "Order",
    "Position",
    "RiskEvent",
    "Signal",
    "TradeDecision",
    "TradeEvaluation",
    "MomentumScore",
    "TrendScore",
    "VolatilityScore",
    "DecisionLog",
    "MarketQualityScore",
    "MarketContextScore",
    "OrderbookScore",
    "FundingScore",
    "NewsScore",
    "OutcomeLearning",
    "EnginePerformance",
    "EngineWeight",
]
