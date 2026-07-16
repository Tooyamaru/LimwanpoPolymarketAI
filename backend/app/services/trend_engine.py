"""
Trend Engine — Decision Engine pipeline, stage 3 (Trend).

Reads Binance klines for every (asset, timeframe) pair currently active in
market_universe and scores medium-term trend from two rule-based
sub-signals: MACD histogram sign/magnitude and an EMA20/EMA50 slope check.

Read-only with respect to market (Polymarket) data — only fetches public
Binance candles and writes to its own trend_scores table.
"""

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.repositories import trend_repository as repo
from app.repositories.universe_repository import get_active_universe
from app.services.binance_market_data import closes_of, fetch_klines
from app.utils.indicators import ema_last, macd as calc_macd

logger = get_logger(__name__)

EMA_FAST_PERIOD = 20
EMA_SLOW_PERIOD = 50
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
KLINES_LIMIT = 100


class TrendEngine:
    """
    Usage (from a background loop)::

        engine = TrendEngine()
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
                await repo.upsert_trend_score(session, **result)
                scored += 1
            except Exception as exc:
                logger.error(
                    "Trend engine error",
                    asset=asset,
                    timeframe=timeframe,
                    error=str(exc),
                )
                errors += 1

        await session.commit()

        elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        logger.info(
            "Trend engine cycle complete",
            pairs=len(pairs),
            scored=scored,
            skipped=skipped,
            errors=errors,
            duration_ms=elapsed_ms,
        )
        return {"pairs": len(pairs), "scored": scored, "skipped": skipped, "errors": errors}

    async def _score_pair(self, asset: str, timeframe: str) -> dict | None:
        candles = await fetch_klines(asset, timeframe, limit=KLINES_LIMIT)
        min_needed = max(EMA_SLOW_PERIOD, MACD_SLOW + MACD_SIGNAL)
        if len(candles) < min_needed:
            logger.debug(
                "Trend engine: insufficient candles — skipping",
                asset=asset,
                timeframe=timeframe,
                candles=len(candles),
            )
            return None

        closes = closes_of(candles)

        macd_line, macd_signal, macd_hist = calc_macd(
            closes, fast=MACD_FAST, slow=MACD_SLOW, signal=MACD_SIGNAL
        )
        ema_fast = ema_last(closes, EMA_FAST_PERIOD)
        ema_slow = ema_last(closes, EMA_SLOW_PERIOD)

        reasons: list[str] = []
        sub_signals: list[int] = []

        last_close = closes[-1]

        # ── Sub-signal 1: MACD histogram ──────────────────────────────────────
        score_macd = 0.0
        if macd_hist is not None and last_close:
            hist_pct = abs(macd_hist) / last_close * 100.0
            score_macd = min(hist_pct / 0.1, 1.0) * 50.0
            if macd_hist > 0:
                sub_signals.append(1)
                reasons.append(f"MACD histogram +{macd_hist:.4f} (bullish)")
            elif macd_hist < 0:
                sub_signals.append(-1)
                reasons.append(f"MACD histogram {macd_hist:.4f} (bearish)")
            else:
                sub_signals.append(0)
                reasons.append("MACD histogram flat")

        # ── Sub-signal 2: EMA20/EMA50 slope ───────────────────────────────────
        score_ema = 0.0
        if ema_fast is not None and ema_slow is not None and ema_slow != 0:
            spread_pct = (ema_fast - ema_slow) / ema_slow * 100.0
            score_ema = min(abs(spread_pct) / 0.5, 1.0) * 50.0
            if ema_fast > ema_slow:
                sub_signals.append(1)
                reasons.append(
                    f"EMA{EMA_FAST_PERIOD} above EMA{EMA_SLOW_PERIOD} — uptrend intact"
                )
            elif ema_fast < ema_slow:
                sub_signals.append(-1)
                reasons.append(
                    f"EMA{EMA_FAST_PERIOD} below EMA{EMA_SLOW_PERIOD} — downtrend intact"
                )
            else:
                sub_signals.append(0)

        score = round(score_macd + score_ema, 2)

        bullish = sum(1 for s in sub_signals if s > 0)
        bearish = sum(1 for s in sub_signals if s < 0)
        total = len(sub_signals) or 1

        if bullish > bearish:
            direction = "UP"
            agreement = bullish / total
        elif bearish > bullish:
            direction = "DOWN"
            agreement = bearish / total
        else:
            direction = "SIDEWAYS"
            agreement = 0.34

        confidence = round(agreement * 100.0, 2)

        return {
            "asset": asset,
            "timeframe": timeframe,
            "score": score,
            "confidence": confidence,
            "direction": direction,
            "reason": " | ".join(reasons) if reasons else None,
            "macd_line": macd_line,
            "macd_signal": macd_signal,
            "macd_hist": macd_hist,
            "ema_fast": ema_fast,
            "ema_slow": ema_slow,
        }
