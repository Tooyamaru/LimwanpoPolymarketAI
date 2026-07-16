"""
Orderbook Engine — Phase Next, supporting engine.

Reads Binance spot order book depth to gauge short-term bid/ask pressure.
This is a CONFIRMATION signal only — it never overrides the Polymarket
Market Engine or the Decision Engine's Polymarket-first reasoning, it only
helps confirm or weaken a direction already suggested by Polymarket pricing.

Read-only with respect to Binance public data — writes to its own
orderbook_scores table.
"""

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.repositories import orderbook_repository as repo
from app.repositories.universe_repository import get_active_universe
from app.services.binance_market_data import fetch_order_book_depth

logger = get_logger(__name__)

DEPTH_LIMIT = 100
IMBALANCE_BULLISH_THRESHOLD = 0.15
IMBALANCE_BEARISH_THRESHOLD = -0.15


class OrderbookEngine:
    """
    Usage (from a background loop)::

        engine = OrderbookEngine()
        result = await engine.scan(session)
    """

    async def scan(self, session: AsyncSession) -> dict:
        started = datetime.now(timezone.utc)

        universe = await get_active_universe(session)
        assets = sorted({m.asset for m in universe})

        scored = 0
        skipped = 0
        errors = 0

        for asset in assets:
            try:
                result = await self._score_asset(asset)
                if result is None:
                    skipped += 1
                    continue
                await repo.upsert_orderbook_score(session, **result)
                scored += 1
            except Exception as exc:
                logger.error("Orderbook engine error", asset=asset, error=str(exc))
                errors += 1

        await session.commit()

        elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        logger.info(
            "Orderbook engine cycle complete",
            assets=len(assets),
            scored=scored,
            skipped=skipped,
            errors=errors,
            duration_ms=elapsed_ms,
        )
        return {"assets": len(assets), "scored": scored, "skipped": skipped, "errors": errors}

    @staticmethod
    async def _score_asset(asset: str) -> dict | None:
        depth = await fetch_order_book_depth(asset, limit=DEPTH_LIMIT)
        if depth is None:
            return None

        bid_volume = sum(q for _, q in depth["bids"])
        ask_volume = sum(q for _, q in depth["asks"])
        total = bid_volume + ask_volume

        if total <= 0:
            return None

        imbalance_pct = (bid_volume - ask_volume) / total

        if imbalance_pct >= IMBALANCE_BULLISH_THRESHOLD:
            direction = "BULLISH"
        elif imbalance_pct <= IMBALANCE_BEARISH_THRESHOLD:
            direction = "BEARISH"
        else:
            direction = "NEUTRAL"

        confidence = min(abs(imbalance_pct) / 0.5, 1.0) * 100.0

        reason = (
            f"bid_volume={bid_volume:.2f} ask_volume={ask_volume:.2f} "
            f"imbalance={imbalance_pct*100:.1f}% (top {DEPTH_LIMIT} levels)"
        )

        return {
            "asset": asset,
            "direction": direction,
            "confidence": round(confidence, 2),
            "reason": reason,
            "bid_volume": bid_volume,
            "ask_volume": ask_volume,
            "imbalance_pct": round(imbalance_pct, 4),
        }
