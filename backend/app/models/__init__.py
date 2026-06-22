"""
SQLAlchemy ORM models.

Importing this package ensures all models are registered with Base.metadata
so that init_db() creates the correct tables.
"""

from app.core.database import Base
from app.models.discovery_run import DiscoveryRun
from app.models.event_classification import EventClassification
from app.models.market import Market
from app.models.market_price_snapshot import MarketPriceSnapshot
from app.models.market_snapshot import MarketSnapshot
from app.models.market_universe import MarketUniverse
from app.models.scanner_market import ScannerMarket
from app.models.signal import Signal
from app.models.source_validation_result import SourceValidationResult

__all__ = [
    "Base",
    "DiscoveryRun",
    "EventClassification",
    "Market",
    "MarketPriceSnapshot",
    "MarketSnapshot",
    "MarketUniverse",
    "ScannerMarket",
    "Signal",
    "SourceValidationResult",
]
