"""
Funding Engine — Phase Next, supporting engine.

Reads Binance USDT-M perpetual funding rate, open interest, and long/short
account ratio as a sentiment confirmation signal. This is a CONFIRMATION
signal only — never a decision center on its own.

Read-only with respect to Binance public data — writes to its own
funding_scores table.
"""

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.repositories import funding_repository as repo
from app.repositories.universe_repository import get_active_universe
from app.services.binance_market_data import fetch_funding_data

logger = get_logger(__name__)

FUNDING_BULLISH_THRESHOLD = 0.0005   # 0.05%
FUNDING_BEARISH_THRESHOLD = -0.0005


class FundingEngine:
    """
    Usage (from a background loop)::

        engine = FundingEngine()
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
                await repo.upsert_funding_score(session, **result)
                scored += 1
            except Exception as exc:
                logger.error("Funding engine error", asset=asset, error=str(exc))
                errors += 1

        await session.commit()

        elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        logger.info(
            "Funding engine cycle complete",
            assets=len(assets),
            scored=scored,
            skipped=skipped,
            errors=errors,
            duration_ms=elapsed_ms,
        )
        return {"assets": len(assets), "scored": scored, "skipped": skipped, "errors": errors}

    @staticmethod
    async def _score_asset(asset: str) -> dict | None:
        data = await fetch_funding_data(asset)
        if data is None:
            return None

        funding_rate = data.get("funding_rate")
        open_interest = data.get("open_interest")
        long_short_ratio = data.get("long_short_ratio")

        reasons: list[str] = []

        if funding_rate is None:
            direction = "NEUTRAL"
            confidence = 0.0
            reasons.append("Funding rate unavailable")
        else:
            reasons.append(f"Funding rate={funding_rate*100:.4f}%")
            if funding_rate >= FUNDING_BULLISH_THRESHOLD:
                direction = "BULLISH"
                confidence = min(abs(funding_rate) / 0.002, 1.0) * 100.0
                reasons.append("positive funding — demand for longs")
            elif funding_rate <= FUNDING_BEARISH_THRESHOLD:
                direction = "BEARISH"
                confidence = min(abs(funding_rate) / 0.002, 1.0) * 100.0
                reasons.append("negative funding — demand for shorts")
            else:
                direction = "NEUTRAL"
                confidence = 20.0
                reasons.append("funding near zero — no crowd bias")

        if long_short_ratio is not None:
            reasons.append(f"long/short ratio={long_short_ratio:.2f}")
            if direction == "BULLISH" and long_short_ratio < 1.0:
                confidence *= 0.7
                reasons.append("(tempered: fewer longs than shorts on record)")
            elif direction == "BEARISH" and long_short_ratio > 1.0:
                confidence *= 0.7
                reasons.append("(tempered: more longs than shorts on record)")

        if open_interest is not None:
            reasons.append(f"open interest={open_interest:.0f}")

        return {
            "asset": asset,
            "direction": direction,
            "confidence": round(confidence, 2),
            "reason": " | ".join(reasons),
            "funding_rate": funding_rate,
            "open_interest": open_interest,
            "long_short_ratio": long_short_ratio,
        }
