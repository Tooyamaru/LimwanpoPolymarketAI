"""
Chainlink price feed collector — Sprint 2 placeholder.

Responsibilities (to be implemented):
- Subscribe to Chainlink Data Feeds via Ethereum RPC (eth_subscribe)
- Collect latest round data for configured price pairs
- Handle round answer updates
- Persist raw data to PostgreSQL
- Publish normalised events to Redis pub/sub
"""


class ChainlinkCollector:
    """Placeholder for Chainlink price feed collector."""

    def __init__(self) -> None:
        raise NotImplementedError("ChainlinkCollector is not implemented yet.")

    async def start(self) -> None:
        raise NotImplementedError

    async def stop(self) -> None:
        raise NotImplementedError
