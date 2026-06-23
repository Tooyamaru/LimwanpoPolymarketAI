"""
Opportunity Engine — Layer 5.

Scans all active universe markets and computes a 0–100 Opportunity Score
by aggregating five sub-scores derived from live CLOB snapshots, recent
signals, and market metadata.

Score components (calibrated to the empirical findings from Audit #1–#5):

  score_mid_movement    (0–30)
      Seed deviation: how far yes_mid has moved from the fixed seed price
      (0.50).  All markets start at 0.50; any deviation means a trade has
      consumed depth.  Formula: min(30, abs(yes_mid - 0.50) * 600)
      Interpretation: 0.005 dev → 3 pts | 0.01 → 6 pts | 0.05+ → 30 pts

  score_spread          (0–20)
      Tighter spread = lower cost to enter/exit = better opportunity.
      Baseline: 5m/15m markets have spread=0.01, 1H markets spread=0.02.
      Formula: max(0, min(20, (0.02 - spread_yes) * 2000))
      Interpretation: 0.01 → 20 pts | 0.015 → 10 pts | ≥0.02 → 0 pts

  score_depth_imbalance (0–20)
      YES-vs-NO liquidity imbalance.  Proxy: abs(spread_no − spread_yes).
      When one side is tighter than the other, there is directional pressure
      on that side.
      Formula: min(20, abs(spread_no - spread_yes) * 2000) if both known
      Falls back to 0 when either spread is unavailable.

  score_signal_activity (0–20)
      Recent signal density: counts MID_MOVE and SEED_DEVIATION signals
      emitted in the last 60 minutes for this market.
      0 → 0 pts | 1 → 10 pts | 2–3 → 15 pts | 4+ → 20 pts
      Each HIGH severity signal adds +3 pts bonus (cap remains 20).

  score_discovery       (0–10)
      Time-to-expiry urgency.  Markets approaching resolution have more
      certain outcomes and tighter pricing.
      < 15 min → 10 | 15-30 min → 8 | 30-60 min → 6 |
      1-2 H → 4 | 2-6 H → 2 | > 6 H → 1 | unknown → 0

Direction hint (mean-reversion against seed 0.50):
  BUY_YES  if yes_mid < 0.495  (market is below seed → expect rise to 0.50)
  BUY_NO   if yes_mid > 0.505  (market is above seed → expect fall to 0.50)
  NEUTRAL  otherwise
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.market_universe import MarketUniverse
from app.models.signal import Signal
from app.repositories import opportunity_repository as repo
from app.repositories.market_price_repository import get_latest_by_condition
from app.repositories.universe_repository import get_active_universe

logger = get_logger(__name__)

SEED_PRICE = 0.50
DIRECTION_THRESHOLD = 0.005   # ±0.5 % from seed triggers directional hint


# ── Sub-score calculators ──────────────────────────────────────────────────────

def _score_mid_movement(yes_mid: Optional[float]) -> float:
    """0–30: deviation of yes_mid from seed 0.50."""
    if yes_mid is None:
        return 0.0
    deviation = abs(yes_mid - SEED_PRICE)
    return round(min(30.0, deviation * 600.0), 2)


def _score_spread(spread_yes: Optional[float]) -> float:
    """0–20: spread tightness (tighter = higher score)."""
    if spread_yes is None:
        return 0.0
    return round(max(0.0, min(20.0, (0.02 - spread_yes) * 2000.0)), 2)


def _score_depth_imbalance(
    spread_yes: Optional[float],
    spread_no: Optional[float],
) -> float:
    """0–20: YES vs NO spread imbalance as a liquidity-pressure proxy."""
    if spread_yes is None or spread_no is None:
        return 0.0
    return round(min(20.0, abs(spread_no - spread_yes) * 2000.0), 2)


def _score_signal_activity(
    signal_count: int,
    high_severity_count: int,
) -> float:
    """0–20: recent signal density over the past 60 minutes."""
    if signal_count == 0:
        return 0.0
    if signal_count == 1:
        base = 10.0
    elif signal_count <= 3:
        base = 15.0
    else:
        base = 20.0
    bonus = min(5.0, high_severity_count * 3.0)
    return round(min(20.0, base + bonus), 2)


def _score_discovery(minutes_to_expiry: Optional[float]) -> float:
    """0–10: urgency based on time remaining to market expiry."""
    if minutes_to_expiry is None:
        return 0.0
    if minutes_to_expiry < 15:
        return 10.0
    if minutes_to_expiry < 30:
        return 8.0
    if minutes_to_expiry < 60:
        return 6.0
    if minutes_to_expiry < 120:
        return 4.0
    if minutes_to_expiry < 360:
        return 2.0
    return 1.0


def _direction(yes_mid: Optional[float]) -> str:
    """BUY_YES | BUY_NO | NEUTRAL based on seed deviation."""
    if yes_mid is None:
        return "NEUTRAL"
    if yes_mid < (SEED_PRICE - DIRECTION_THRESHOLD):
        return "BUY_YES"
    if yes_mid > (SEED_PRICE + DIRECTION_THRESHOLD):
        return "BUY_NO"
    return "NEUTRAL"


# ── Engine ─────────────────────────────────────────────────────────────────────

class OpportunityEngine:
    """
    Evaluates all active markets and persists their Opportunity Scores.

    Usage (from FastAPI lifespan or background loop)::

        engine = OpportunityEngine()
        result = await engine.evaluate(session)
    """

    async def evaluate(self, session: AsyncSession) -> dict:
        """
        Run one full evaluation cycle across all active universe markets.

        Returns::
            {
                "markets_evaluated": int,
                "top_score": float,
                "top_market": str,      # "ASSET/TF"
                "skipped_no_data": int,
                "errors": int,
                "duration_ms": int,
            }
        """
        started = datetime.now(timezone.utc)
        active_markets: list[MarketUniverse] = await get_active_universe(session)

        if not active_markets:
            logger.debug("Opportunity engine: no active markets, evaluation skipped")
            return {
                "markets_evaluated": 0,
                "top_score": 0.0,
                "top_market": None,
                "skipped_no_data": 0,
                "errors": 0,
                "duration_ms": 0,
            }

        markets_evaluated = 0
        skipped_no_data = 0
        errors = 0
        top_score = 0.0
        top_market = None

        # Cutoff for recent signal look-back
        signal_cutoff = started - timedelta(hours=1)

        for market in active_markets:
            try:
                score, did_skip = await self._evaluate_market(
                    session, market, signal_cutoff
                )
                if did_skip:
                    skipped_no_data += 1
                else:
                    markets_evaluated += 1
                    if score > top_score:
                        top_score = score
                        top_market = f"{market.asset}/{market.timeframe}"
            except Exception as exc:
                logger.error(
                    "Opportunity engine error",
                    condition_id=market.condition_id[:12],
                    asset=market.asset,
                    timeframe=market.timeframe,
                    error=str(exc),
                )
                errors += 1

        await session.commit()

        elapsed_ms = int(
            (datetime.now(timezone.utc) - started).total_seconds() * 1000
        )

        logger.info(
            "Opportunity engine evaluation complete",
            markets_evaluated=markets_evaluated,
            top_score=round(top_score, 1),
            top_market=top_market,
            errors=errors,
            duration_ms=elapsed_ms,
        )

        return {
            "markets_evaluated": markets_evaluated,
            "top_score": round(top_score, 2),
            "top_market": top_market,
            "skipped_no_data": skipped_no_data,
            "errors": errors,
            "duration_ms": elapsed_ms,
        }

    async def _evaluate_market(
        self,
        session: AsyncSession,
        market: MarketUniverse,
        signal_cutoff: datetime,
    ) -> tuple[float, bool]:
        """
        Evaluate one market. Returns (score, skipped_flag).
        skipped_flag is True when no price snapshot exists yet.
        """
        # ── Latest price snapshot ──────────────────────────────────────────────
        snapshots = await get_latest_by_condition(
            session, market.condition_id, limit=1
        )
        if not snapshots:
            return 0.0, True

        snap = snapshots[0]
        yes_mid = snap.yes_mid
        yes_bid = snap.yes_bid
        yes_ask = snap.yes_ask
        no_mid = snap.no_mid
        spread_yes = snap.spread_yes
        spread_no = snap.spread_no
        seed_deviation = round(abs((yes_mid or SEED_PRICE) - SEED_PRICE), 8)

        # ── Recent signals ─────────────────────────────────────────────────────
        sig_result = await session.execute(
            select(Signal.signal_type, Signal.severity)
            .where(
                Signal.condition_id == market.condition_id,
                Signal.signal_type.in_(["MID_MOVE", "SEED_DEVIATION"]),
                Signal.detected_at >= signal_cutoff,
            )
        )
        sig_rows = sig_result.all()
        signal_count = len(sig_rows)
        high_count = sum(1 for r in sig_rows if r[1] == "HIGH")
        last_signal_type = sig_rows[0][0] if sig_rows else None
        last_signal_severity = sig_rows[0][1] if sig_rows else None

        # ── Time to expiry ─────────────────────────────────────────────────────
        minutes_to_expiry: Optional[float] = None
        if market.end_time is not None:
            now = datetime.now(timezone.utc)
            remaining = (market.end_time - now).total_seconds() / 60.0
            minutes_to_expiry = round(remaining, 1) if remaining > 0 else 0.0

        # ── Compute sub-scores ─────────────────────────────────────────────────
        s_mid = _score_mid_movement(yes_mid)
        s_spread = _score_spread(spread_yes)
        s_depth = _score_depth_imbalance(spread_yes, spread_no)
        s_signal = _score_signal_activity(signal_count, high_count)
        s_discovery = _score_discovery(minutes_to_expiry)

        total = round(s_mid + s_spread + s_depth + s_signal + s_discovery, 2)
        direction = _direction(yes_mid)

        # ── Persist ────────────────────────────────────────────────────────────
        await repo.upsert_opportunity(
            session,
            condition_id=market.condition_id,
            asset=market.asset,
            timeframe=market.timeframe,
            opportunity_score=total,
            score_mid_movement=s_mid,
            score_spread=s_spread,
            score_depth_imbalance=s_depth,
            score_signal_activity=s_signal,
            score_discovery=s_discovery,
            yes_mid=yes_mid,
            yes_bid=yes_bid,
            yes_ask=yes_ask,
            no_mid=no_mid,
            spread_yes=spread_yes,
            spread_no=spread_no,
            seed_deviation=seed_deviation,
            signal_count_1h=signal_count,
            last_signal_type=last_signal_type,
            last_signal_severity=last_signal_severity,
            minutes_to_expiry=minutes_to_expiry,
            direction=direction,
        )

        return total, False
