"""
Polymarket collector — Sprint 2 placeholder.

Responsibilities (to be implemented):
- Connect to Polymarket CLOB WebSocket API
- Collect market order books (Yes/No token prices)
- Collect trade history
- Fetch market metadata via REST API
- Persist raw data to PostgreSQL
- Publish normalised events to Redis pub/sub
"""


class PolymarketCollector:
    """Placeholder for Polymarket data collector."""

    def __init__(self) -> None:
        raise NotImplementedError("PolymarketCollector is not implemented yet.")

    async def start(self) -> None:
        raise NotImplementedError

    async def stop(self) -> None:
        raise NotImplementedError
