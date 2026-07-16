"""
Polymarket Market Engine — Phase Next: Market Behaviour Engine.

UPGRADE: Now reads market BEHAVIOUR (changes over time) rather than just a
single snapshot score. Three-phase pipeline:

  Phase 1 — BEHAVIOUR DETECTION: compare the last N snapshots to find
    directional trends in spread, liquidity, volume, and bid/ask dynamics.
    Labels: Increasing Liquidity, Decreasing Liquidity, Healthy Spread,
    Wide Spread, Buy Pressure, Sell Pressure, Aggressive Buyers,
    Aggressive Sellers, Balanced Market, Passive Market, Low Participation,
    High Participation, Market Stability, Market becoming more efficient.

  Phase 2 — INTERPRETATION: emit the list of behaviour labels as the primary
    output so downstream engines (Decision Engine) can reason from them.

  Phase 3 — QUALITY CLASSIFICATION: derive a rich quality label from the
    behaviours rather than purely from the raw score:
    Excellent | Healthy | GOOD | AVERAGE | BAD | High Risk | Illiquid | Avoid.

The market_score is preserved for backward compatibility (confidence gate in
Decision Engine), but market_quality is now behaviour-driven.

Output: market_score (0-100), market_quality (rich label), market_confidence
(0-100), market_risk (LOW/MEDIUM/HIGH), market_behaviours (comma-joined
labels), and the raw snapshot fields.

Read-only with respect to market_universe / market_price_snapshots — only
reads them and writes to its own market_quality_scores table.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.repositories import market_quality_repository as repo
from app.repositories.market_price_repository import get_latest_by_condition
from app.repositories.universe_repository import get_active_universe

logger = get_logger(__name__)

# ── Behaviour detection window ─────────────────────────────────────────────────
BEHAVIOUR_WINDOW = 5        # how many recent snapshots to read per market

# ── Sub-score weights (sum to 100) ─────────────────────────────────────────────
WEIGHT_SPREAD = 30.0
WEIGHT_LIQUIDITY = 25.0
WEIGHT_VOLUME = 15.0
WEIGHT_EXPIRY = 20.0
WEIGHT_STATE = 10.0

# ── Behaviour thresholds ───────────────────────────────────────────────────────
SPREAD_HEALTHY_THRESHOLD = 0.02    # spread_yes < this → Healthy Spread
SPREAD_WIDE_THRESHOLD = 0.05       # spread_yes > this → Wide Spread
LIQUIDITY_LOW_THRESHOLD = 5_000.0  # below → Low Participation territory
VOLUME_LOW_THRESHOLD = 100.0       # below → Low Participation
BID_MOVE_AGGRESSIVE = 0.01         # yes_bid delta above this → Aggressive Buyers/Sellers
BID_STABLE_THRESHOLD = 0.005       # delta below this → stable side

# Data-scarcity fallback — markets in early AMM life frequently have NULL
# volume/liquidity. Score as "weak, unknown" instead of "fatal".
NULL_FIELD_SCORE = 30.0

# ── Non-tradable quality labels (Decision Engine gate check) ───────────────────
NON_TRADABLE_QUALITIES = {"BAD", "High Risk", "Illiquid", "Avoid"}


class PolymarketMarketEngine:
    """
    Usage (from a background loop)::

        engine = PolymarketMarketEngine()
        result = await engine.scan(session)
    """

    async def scan(self, session: AsyncSession) -> dict:
        started = datetime.now(timezone.utc)

        universe = await get_active_universe(session)

        scored = 0
        errors = 0

        for market in universe:
            try:
                result = await self._score_market(session, market)
                await repo.upsert_market_quality_score(session, **result)
                scored += 1
            except Exception as exc:
                logger.error(
                    "Market quality engine error",
                    condition_id=market.condition_id,
                    asset=market.asset,
                    error=str(exc),
                )
                errors += 1

        await session.commit()

        elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        logger.info(
            "Market behaviour engine cycle complete",
            markets=len(universe),
            scored=scored,
            errors=errors,
            duration_ms=elapsed_ms,
        )
        return {"markets": len(universe), "scored": scored, "errors": errors}

    async def _score_market(self, session: AsyncSession, market) -> dict:
        condition_id = market.condition_id
        asset = market.asset
        timeframe = market.timeframe

        # ── Fetch last N snapshots for behaviour detection ────────────────────
        snapshots = await get_latest_by_condition(session, condition_id, limit=BEHAVIOUR_WINDOW)
        snapshot = snapshots[0] if snapshots else None

        reasons: list[str] = []

        active = market.status == "active"
        now = datetime.now(timezone.utc)
        seconds_to_expiry = None
        if market.end_time is not None:
            end_time = market.end_time
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=timezone.utc)
            seconds_to_expiry = (end_time - now).total_seconds()

        # ── Hard override: inactive/closed market is always non-tradable ─────
        if not active:
            reasons.append(f"Market state={market.status} (not active) — forcing High Risk")
            return {
                "condition_id": condition_id,
                "asset": asset,
                "timeframe": timeframe,
                "market_score": 0.0,
                "market_quality": "High Risk",
                "market_confidence": 100.0,
                "market_risk": "HIGH",
                "market_behaviours": None,
                "reason": " | ".join(reasons),
                "yes_bid": snapshot.yes_bid if snapshot else None,
                "yes_ask": snapshot.yes_ask if snapshot else None,
                "spread_yes": snapshot.spread_yes if snapshot else None,
                "liquidity": snapshot.liquidity if snapshot else None,
                "volume": snapshot.volume if snapshot else None,
                "seconds_to_expiry": seconds_to_expiry,
                "active": active,
            }

        # ── Phase 1: Detect Market Behaviours ─────────────────────────────────
        behaviours = self._detect_behaviours(snapshots)
        behaviours_str = ", ".join(behaviours) if behaviours else None

        present_fields = 0
        total_fields = 3  # spread, liquidity, volume

        # ── Spread sub-score (30) ─────────────────────────────────────────────
        spread_yes = snapshot.spread_yes if snapshot else None
        if spread_yes is not None:
            present_fields += 1
            score_spread = max(0.0, 100.0 - (spread_yes * 1000.0))
            score_spread = min(score_spread, 100.0)
            reasons.append(f"Spread={spread_yes:.4f}")
        else:
            score_spread = NULL_FIELD_SCORE
            reasons.append("Spread: no data yet")

        # ── Liquidity sub-score (25) ──────────────────────────────────────────
        liquidity = snapshot.liquidity if snapshot else None
        if liquidity is not None:
            present_fields += 1
            score_liquidity = min(liquidity / 1000.0, 1.0) * 100.0
            reasons.append(f"Liquidity=${liquidity:.0f}")
        else:
            score_liquidity = NULL_FIELD_SCORE
            reasons.append("Liquidity: not reported yet (AMM init phase)")

        # ── Volume sub-score (15) ─────────────────────────────────────────────
        volume = snapshot.volume if snapshot else None
        if volume is not None:
            present_fields += 1
            score_volume = min(volume / 500.0, 1.0) * 100.0
            reasons.append(f"Volume=${volume:.0f}")
        else:
            score_volume = NULL_FIELD_SCORE
            reasons.append("Volume: not reported yet (AMM init phase)")

        # ── Time-to-expiry safety (20) ────────────────────────────────────────
        if seconds_to_expiry is None:
            score_expiry = NULL_FIELD_SCORE
            reasons.append("Expiry: unknown end_time")
        elif seconds_to_expiry <= 0:
            score_expiry = 0.0
            reasons.append("Expiry: market already past end_time")
        elif seconds_to_expiry < 300:
            score_expiry = 20.0
            reasons.append(f"Expiry: {seconds_to_expiry/60:.1f} min left — near resolution, risky")
        elif seconds_to_expiry < 900:
            score_expiry = 60.0
            reasons.append(f"Expiry: {seconds_to_expiry/60:.1f} min left — approaching resolution")
        else:
            score_expiry = 100.0
            reasons.append(f"Expiry: {seconds_to_expiry/60:.1f} min left — healthy window")

        # ── Active/state quality (10) ─────────────────────────────────────────
        score_state = 100.0
        reasons.append("State: active")

        market_score = (
            score_spread * WEIGHT_SPREAD
            + score_liquidity * WEIGHT_LIQUIDITY
            + score_volume * WEIGHT_VOLUME
            + score_expiry * WEIGHT_EXPIRY
            + score_state * WEIGHT_STATE
        ) / 100.0

        market_confidence = 40.0 + (present_fields / total_fields) * 60.0

        # ── Market Risk (structural risk assessment) ──────────────────────────
        if seconds_to_expiry is not None and seconds_to_expiry < 300:
            market_risk = "HIGH"
        elif market_score < 50.0 or (spread_yes is not None and spread_yes > SPREAD_WIDE_THRESHOLD):
            market_risk = "MEDIUM"
        else:
            market_risk = "LOW"

        # ── Phase 2 + 3: Market Quality from Behaviours ───────────────────────
        market_quality = self._quality_from_behaviours(
            behaviours, market_score, market_risk, spread_yes, liquidity, volume
        )

        # Append behaviour summary to reasons
        if behaviours:
            reasons.append(f"Behaviours: {behaviours_str}")
        else:
            reasons.append("Behaviours: insufficient snapshot history (single snapshot)")

        return {
            "condition_id": condition_id,
            "asset": asset,
            "timeframe": timeframe,
            "market_score": market_score,
            "market_quality": market_quality,
            "market_confidence": market_confidence,
            "market_risk": market_risk,
            "market_behaviours": behaviours_str,
            "reason": " | ".join(reasons),
            "yes_bid": snapshot.yes_bid if snapshot else None,
            "yes_ask": snapshot.yes_ask if snapshot else None,
            "spread_yes": spread_yes,
            "liquidity": liquidity,
            "volume": volume,
            "seconds_to_expiry": seconds_to_expiry,
            "active": active,
        }

    # ── Phase 1: Behaviour Detection ──────────────────────────────────────────

    @staticmethod
    def _detect_behaviours(snapshots: list) -> list[str]:
        """
        Compare recent snapshots to detect directional market behaviour.

        Returns a list of human-readable behaviour labels. The list may be
        empty if there is insufficient snapshot history.
        """
        behaviours: list[str] = []

        if not snapshots:
            return behaviours

        latest = snapshots[0]

        # ── Spread behaviour ──────────────────────────────────────────────────
        spread_snaps = [s for s in snapshots if s.spread_yes is not None]
        if spread_snaps:
            latest_spread = spread_snaps[0].spread_yes
            if latest_spread < SPREAD_HEALTHY_THRESHOLD:
                behaviours.append("Healthy Spread")
            elif latest_spread > SPREAD_WIDE_THRESHOLD:
                behaviours.append("Wide Spread")
            # Trend: is spread consistently narrowing? (newest first → decreasing means improving)
            if len(spread_snaps) >= 3:
                s0, s1, s2 = spread_snaps[0].spread_yes, spread_snaps[1].spread_yes, spread_snaps[2].spread_yes
                if s0 < s1 and s1 < s2:
                    behaviours.append("Market becoming more efficient")

        # ── Liquidity behaviour ───────────────────────────────────────────────
        liq_snaps = [s for s in snapshots if s.liquidity is not None]
        if len(liq_snaps) >= 3:
            # Trend label requires ≥3 data points — otherwise we cannot assert direction
            l0, l1, l2 = liq_snaps[0].liquidity, liq_snaps[1].liquidity, liq_snaps[2].liquidity
            if l0 > l1 and l1 > l2:
                behaviours.append("Increasing Liquidity")
            elif l0 < l1 and l1 < l2:
                behaviours.append("Decreasing Liquidity")
        elif liq_snaps:
            # Single snapshot: use point-in-time label, NOT a trend label
            if liq_snaps[0].liquidity < LIQUIDITY_LOW_THRESHOLD:
                behaviours.append("Low Liquidity")

        # ── Volume / participation behaviour ──────────────────────────────────
        vol_snaps = [s for s in snapshots if s.volume is not None]
        if len(vol_snaps) >= 3:
            v0, v1, v2 = vol_snaps[0].volume, vol_snaps[1].volume, vol_snaps[2].volume
            if v0 > v1 and v1 > v2:
                behaviours.append("High Participation")
            elif v0 < v1 and v1 < v2:
                behaviours.append("Low Participation")
        elif vol_snaps:
            if vol_snaps[0].volume < VOLUME_LOW_THRESHOLD:
                behaviours.append("Low Participation")

        # ── YES bid / ask dynamics ────────────────────────────────────────────
        bid_snaps = [s for s in snapshots if s.yes_bid is not None and s.yes_ask is not None]
        if len(bid_snaps) >= 2:
            bid_delta = bid_snaps[0].yes_bid - bid_snaps[1].yes_bid
            ask_delta = bid_snaps[0].yes_ask - bid_snaps[1].yes_ask
            if bid_delta > BID_MOVE_AGGRESSIVE and abs(ask_delta) < BID_STABLE_THRESHOLD:
                behaviours.append("Aggressive Buyers")
                behaviours.append("Buy Pressure")
            elif bid_delta < -BID_MOVE_AGGRESSIVE and abs(ask_delta) < BID_STABLE_THRESHOLD:
                behaviours.append("Aggressive Sellers")
                behaviours.append("Sell Pressure")
            elif abs(bid_delta) < BID_STABLE_THRESHOLD and abs(ask_delta) < BID_STABLE_THRESHOLD:
                behaviours.append("Balanced Market")

        # NO bid weakening — high spread_no relative to spread_yes
        no_snaps = [s for s in snapshots if s.spread_no is not None and s.spread_yes is not None]
        if no_snaps and no_snaps[0].spread_no > no_snaps[0].spread_yes * 2.0:
            behaviours.append("Sellers Weakening")

        # ── Composite derived behaviours ──────────────────────────────────────
        b_set = set(behaviours)
        if "Healthy Spread" in b_set and "Balanced Market" in b_set:
            behaviours.append("Market Stability")
        if "Low Participation" in b_set and "Balanced Market" in b_set:
            behaviours.append("Passive Market")

        return behaviours

    # ── Phase 3: Quality Classification from Behaviours ───────────────────────

    @staticmethod
    def _quality_from_behaviours(
        behaviours: list[str],
        market_score: float,
        market_risk: str,
        spread_yes: Optional[float],
        liquidity: Optional[float],
        volume: Optional[float],
    ) -> str:
        """
        Derive a rich market quality label from detected behaviours.

        Priority (highest → lowest):
          High Risk  → structural risk (near expiry, etc.)
          Illiquid   → Wide Spread + Low Participation → avoid AMM-only price
          Avoid      → Decreasing Liquidity + Wide Spread → deteriorating conditions
          Excellent  → 3+ positive behaviours with no negatives
          Healthy    → 2 positive, 0-1 negatives
          GOOD       → at least 1 positive, ≤1 negative
          AVERAGE    → mixed signals or score-fallback
          BAD        → 2+ negative behaviours or very low score
        """
        if market_risk == "HIGH":
            return "High Risk"

        b_set = set(behaviours)

        positive = {
            "Increasing Liquidity", "Healthy Spread", "High Participation",
            "Market Stability", "Market becoming more efficient",
            "Buy Pressure", "Sell Pressure",  # directional activity is positive for tradability
        }
        negative = {
            "Decreasing Liquidity", "Wide Spread", "Low Participation",
            "Passive Market", "Low Liquidity",
        }

        pos_count = sum(1 for b in b_set if b in positive)
        neg_count = sum(1 for b in b_set if b in negative)

        # Structural un-tradable checks first
        if "Wide Spread" in b_set and ("Low Participation" in b_set or "Low Liquidity" in b_set):
            return "Illiquid"
        if ("Decreasing Liquidity" in b_set or "Low Liquidity" in b_set) and "Wide Spread" in b_set:
            return "Avoid"

        # No behaviour data yet — fall back to score-based labels
        if not behaviours:
            if market_risk == "HIGH":
                return "High Risk"
            if market_score >= 70.0:
                return "GOOD"
            if market_score >= 40.0:
                return "AVERAGE"
            return "BAD"

        # Behaviour-driven quality
        if pos_count >= 3 and neg_count == 0:
            return "Excellent"
        if pos_count >= 2 and neg_count == 0:
            return "Healthy"
        if pos_count >= 1 and neg_count <= 1:
            return "GOOD"
        if neg_count >= 2:
            return "BAD"

        # Score-based fallback for ambiguous behaviour mix
        if market_score >= 70.0:
            return "GOOD"
        if market_score >= 40.0:
            return "AVERAGE"
        return "BAD"
