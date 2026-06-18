"""
Binance Futures collector — Sprint 2 placeholder.

Responsibilities (to be implemented):
- Connect to Binance USD-M Futures WebSocket streams
- Collect funding rates
- Collect mark price and index price
- Collect open interest snapshots
- Persist raw data to PostgreSQL
- Publish normalised events to Redis pub/sub
"""


class BinanceFuturesCollector:
    """Placeholder for Binance Futures data collector."""

    def __init__(self) -> None:
        raise NotImplementedError("BinanceFuturesCollector is not implemented yet.")

    async def start(self) -> None:
        raise NotImplementedError

    async def stop(self) -> None:
        raise NotImplementedError
