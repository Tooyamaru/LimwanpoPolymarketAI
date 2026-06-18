"""
Binance Spot collector — Sprint 2 placeholder.

Responsibilities (to be implemented):
- Connect to Binance Spot WebSocket streams
- Collect real-time order book snapshots
- Collect trade ticks
- Persist raw data to PostgreSQL
- Publish normalised events to Redis pub/sub
"""


class BinanceSpotCollector:
    """Placeholder for Binance Spot data collector."""

    def __init__(self) -> None:
        raise NotImplementedError("BinanceSpotCollector is not implemented yet.")

    async def start(self) -> None:
        raise NotImplementedError

    async def stop(self) -> None:
        raise NotImplementedError
