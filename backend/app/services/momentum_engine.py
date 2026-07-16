"""
Momentum Engine — Decision Engine pipeline, stage 2 (Momentum).

Reads Binance klines for every (asset, timeframe) pair currently active in
market_universe and scores short-term momentum from three rule-based
sub-signals: Rate of Change, RSI, and an EMA fast/slow crossover.

Read-only with respect to market (Polymarket) data — only fetches public
Binance candles and writes to its own momentum_scores table.
"""

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.repositories import momentum_repository as repo
from app.repositories.universe_repository import get_active_universe
from app.services.binance_market_data import closes_of, fetch_klines, last_close
from app.utils.indicators import ema_last, roc, rsi as calc_rsi

logger = get_logger(__name__)

EMA_FAST_PERIOD = 9
EMA_SLOW_PERIOD = 21
RSI_PERIOD = 14
ROC_PERIOD = 10
KLINES_LIMIT = 100


class MomentumEngine:
    """
    Usage (from a background loop)::

        engine = MomentumEngine()
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
                await repo.upsert_momentum_score(session, **result)
                scored += 1
            except Exception as exc:
                logger.error(
                    "Momentum engine error",
                    asset=asset,
                    timeframe=timeframe,
                    error=str(exc),
                )
                errors += 1

        await session.commit()

        elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        logger.info(
            "Momentum engine cycle complete",
            pairs=len(pairs),
            scored=scored,
            skipped=skipped,
            errors=errors,
            duration_ms=elapsed_ms,
        )
        return {"pairs": len(pairs), "scored": scored, "skipped": skipped, "errors": errors}

    async def _score_pair(self, asset: str, timeframe: str) -> dict | None:
        candles = await fetch_klines(asset, timeframe, limit=KLINES_LIMIT)
        min_needed = max(EMA_SLOW_PERIOD, RSI_PERIOD + 1, ROC_PERIOD + 1)
        if len(candles) < min_needed:
            logger.debug(
                "Momentum engine: insufficient candles — skipping",
                asset=asset,
                timeframe=timeframe,
                candles=len(candles),
            )
            return None

        closes = closes_of(candles)
        close = last_close(candles)

        roc_pct = roc(closes, period=ROC_PERIOD)
        rsi_val = calc_rsi(closes, period=RSI_PERIOD)
        ema_fast = ema_last(closes, EMA_FAST_PERIOD)
        ema_slow = ema_last(closes, EMA_SLOW_PERIOD)

        reasons: list[str] = []
        sub_signals: list[int] = []  # +1 bullish, -1 bearish, 0 neutral, per sub-signal

        # ── Sub-signal 1: Rate of Change ──────────────────────────────────────
        score_roc = 0.0
        if roc_pct is not None:
            score_roc = min(abs(roc_pct) / 2.0, 1.0) * 40.0  # +/-2% ROC saturates
            if roc_pct > 0.05:
                sub_signals.append(1)
                reasons.append(f"ROC +{roc_pct:.2f}% over {ROC_PERIOD} candles (bullish)")
            elif roc_pct < -0.05:
                sub_signals.append(-1)
                reasons.append(f"ROC {roc_pct:.2f}% over {ROC_PERIOD} candles (bearish)")
            else:
                sub_signals.append(0)
                reasons.append(f"ROC {roc_pct:.2f}% — flat")

        # ── Sub-signal 2: RSI zone ─────────────────────────────────────────────
        score_rsi = 0.0
        if rsi_val is not None:
            if 55.0 <= rsi_val <= 70.0:
                score_rsi = 30.0
                sub_signals.append(1)
                reasons.append(f"RSI {rsi_val:.1f} in bullish momentum zone")
            elif rsi_val > 70.0:
                score_rsi = 15.0
                sub_signals.append(1)
                reasons.append(f"RSI {rsi_val:.1f} overbought — momentum may be overextended")
            elif 30.0 <= rsi_val <= 45.0:
                score_rsi = 30.0
                sub_signals.append(-1)
                reasons.append(f"RSI {rsi_val:.1f} in bearish momentum zone")
            elif rsi_val < 30.0:
                score_rsi = 15.0
                sub_signals.append(-1)
                reasons.append(f"RSI {rsi_val:.1f} oversold — momentum may be overextended")
            else:
                score_rsi = 5.0
                sub_signals.append(0)
                reasons.append(f"RSI {rsi_val:.1f} — neutral zone")

        # ── Sub-signal 3: EMA fast/slow crossover ─────────────────────────────
        score_ema = 0.0
        if ema_fast is not None and ema_slow is not None and ema_slow != 0:
            spread_pct = (ema_fast - ema_slow) / ema_slow * 100.0
            score_ema = min(abs(spread_pct) / 0.5, 1.0) * 30.0
            if ema_fast > ema_slow:
                sub_signals.append(1)
                reasons.append(
                    f"EMA{EMA_FAST_PERIOD} > EMA{EMA_SLOW_PERIOD} (bullish crossover)"
                )
            elif ema_fast < ema_slow:
                sub_signals.append(-1)
                reasons.append(
                    f"EMA{EMA_FAST_PERIOD} < EMA{EMA_SLOW_PERIOD} (bearish crossover)"
                )
            else:
                sub_signals.append(0)

        score = round(score_roc + score_rsi + score_ema, 2)

        # ── Direction + confidence from sub-signal agreement ──────────────────
        bullish = sum(1 for s in sub_signals if s > 0)
        bearish = sum(1 for s in sub_signals if s < 0)
        total = len(sub_signals) or 1

        if bullish > bearish:
            direction = "BULLISH"
            agreement = bullish / total
        elif bearish > bullish:
            direction = "BEARISH"
            agreement = bearish / total
        else:
            direction = "NEUTRAL"
            agreement = 0.34

        confidence = round(agreement * 100.0, 2)

        return {
            "asset": asset,
            "timeframe": timeframe,
            "score": score,
            "confidence": confidence,
            "direction": direction,
            "reason": " | ".join(reasons) if reasons else None,
            "roc_pct": roc_pct,
            "rsi": rsi_val,
            "ema_fast": ema_fast,
            "ema_slow": ema_slow,
            "last_close": close,
        }
