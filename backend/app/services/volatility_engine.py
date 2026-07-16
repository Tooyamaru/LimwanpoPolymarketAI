"""
Volatility Engine — Decision Engine pipeline, stage 4 (Volatility).

Reads Binance klines for every (asset, timeframe) pair currently active in
market_universe and classifies volatility regime from ATR(14) as a
percentage of the last close.

Scoring is "tradability", not raw volatility: a MEDIUM regime scores
highest (enough movement for the market to plausibly resolve directionally
within its window); LOW and HIGH regimes are penalised.

Read-only with respect to market (Polymarket) data — only fetches public
Binance candles and writes to its own volatility_scores table.
"""

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.repositories import volatility_repository as repo
from app.repositories.universe_repository import get_active_universe
from app.services.binance_market_data import closes_of, fetch_klines, highs_of, lows_of
from app.utils.indicators import atr as calc_atr

logger = get_logger(__name__)

ATR_PERIOD = 14
KLINES_LIMIT = 100

# ATR% (of last close) regime boundaries — calibrated for short-horizon
# crypto candles (5m/15m/1H). Values are approximate and rule-based, not
# statistically fitted; safe defaults for a v1 pipeline.
LOW_MAX_PCT = 0.08     # below this: too flat, market likely settles near seed
HIGH_MIN_PCT = 0.35    # above this: too erratic to trust directional read


class VolatilityEngine:
    """
    Usage (from a background loop)::

        engine = VolatilityEngine()
        result = await engine.scan(session)
    """

    async def scan(self, session: AsyncSession) -> dict:
        started = datetime.now(timezone.utc)

        universe = await get_active_universe(session)
        pairs = sorted({(m.asset, m.timeframe) for m in universe})

        scored = 0
        skipped = 0
        errors = 0

        for asset, timeframe in pairs:
            try:
                result = await self._score_pair(asset, timeframe)
                if result is None:
                    skipped += 1
                    continue
                await repo.upsert_volatility_score(session, **result)
                scored += 1
            except Exception as exc:
                logger.error(
                    "Volatility engine error",
                    asset=asset,
                    timeframe=timeframe,
                    error=str(exc),
                )
                errors += 1

        await session.commit()

        elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        logger.info(
            "Volatility engine cycle complete",
            pairs=len(pairs),
            scored=scored,
            skipped=skipped,
            errors=errors,
            duration_ms=elapsed_ms,
        )
        return {"pairs": len(pairs), "scored": scored, "skipped": skipped, "errors": errors}

    async def _score_pair(self, asset: str, timeframe: str) -> dict | None:
        candles = await fetch_klines(asset, timeframe, limit=KLINES_LIMIT)
        if len(candles) < ATR_PERIOD + 1:
            logger.debug(
                "Volatility engine: insufficient candles — skipping",
                asset=asset,
                timeframe=timeframe,
                candles=len(candles),
            )
            return None

        closes = closes_of(candles)
        highs = highs_of(candles)
        lows = lows_of(candles)
        last_close = closes[-1]

        atr_val = calc_atr(highs, lows, closes, period=ATR_PERIOD)
        if atr_val is None or last_close == 0:
            return None

        atr_pct = round(atr_val / last_close * 100.0, 4)

        if atr_pct < LOW_MAX_PCT:
            regime = "LOW"
            # Score falls off the closer to zero volatility we get.
            score = round(max(0.0, (atr_pct / LOW_MAX_PCT)) * 40.0, 2)
            distance = (LOW_MAX_PCT - atr_pct) / LOW_MAX_PCT
            reason = f"ATR {atr_pct:.3f}% of price — LOW volatility, limited price movement expected"
        elif atr_pct > HIGH_MIN_PCT:
            regime = "HIGH"
            # Score falls off the further past the HIGH boundary we go.
            overshoot = min((atr_pct - HIGH_MIN_PCT) / HIGH_MIN_PCT, 1.0)
            score = round(max(0.0, 1.0 - overshoot) * 50.0, 2)
            distance = overshoot
            reason = f"ATR {atr_pct:.3f}% of price — HIGH volatility, unpredictable price action"
        else:
            regime = "MEDIUM"
            mid = (LOW_MAX_PCT + HIGH_MIN_PCT) / 2.0
            band_half = (HIGH_MIN_PCT - LOW_MAX_PCT) / 2.0
            closeness = 1.0 - min(abs(atr_pct - mid) / band_half, 1.0) if band_half else 1.0
            score = round(70.0 + closeness * 30.0, 2)
            distance = closeness
            reason = f"ATR {atr_pct:.3f}% of price — MEDIUM volatility, favourable for directional resolution"

        confidence = round(min(max(distance, 0.0), 1.0) * 100.0, 2)

        return {
            "asset": asset,
            "timeframe": timeframe,
            "score": score,
            "confidence": confidence,
            "regime": regime,
            "reason": reason,
            "atr": atr_val,
            "atr_pct": atr_pct,
            "last_close": last_close,
        }
