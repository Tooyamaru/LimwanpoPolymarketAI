"""
PortfolioAllocationService — Priority 4: Portfolio Allocation Intelligence.

When multiple markets are simultaneously good (active opportunities), this
service ranks them by composite score and applies capital/position constraints
to decide which to ENTER, DEFER, or SKIP.

Composite score formula (0-100):
  allocation_score = (
    opportunity_score   × 0.40   # market mispricing strength
    + market_quality_score × 0.30   # market tradability (from market_quality_scores)
    + confidence         × 0.20   # overall AI confidence (from last decision_log)
    + spread_tightness   × 0.10   # tighter spread = more liquid = cheaper to trade
  )

Constraints (applied in this order):
  1. SKIP  — non-tradable market quality (BAD, High Risk, Illiquid, Avoid)
  2. SKIP  — asset already has an open position (one-per-asset rule)
  3. DEFER — would exceed MAX_CONCURRENT_POSITIONS
  4. DEFER — score below MIN_ALLOCATION_SCORE
  5. ENTER — everything else, sorted by allocation_score desc

No Machine Learning. Pure statistics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.decision_log import DecisionLog
from app.models.engine_weight import EngineWeight
from app.models.market_price_snapshot import MarketPriceSnapshot
from app.models.market_quality_score import MarketQualityScore  # fields: market_score, market_quality, computed_at
from app.models.market_type_performance import MarketTypePerformance
from app.models.market_universe import MarketUniverse
from app.models.opportunity import Opportunity
from app.models.position import Position
from app.repositories import opportunity_repository as opp_repo
from app.services.outcome_learning_service import _compute_ai_score, _derive_market_type

logger = get_logger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

NON_TRADABLE_QUALITIES = {"BAD", "High Risk", "Illiquid", "Avoid"}

MAX_CONCURRENT_POSITIONS = 10   # align with risk engine
MIN_ALLOCATION_SCORE     = 30.0  # skip anything below this threshold

# Composite score weights (existing allocation_score — UNCHANGED)
W_OPPORTUNITY    = 0.40
W_MARKET_QUALITY = 0.30
W_CONFIDENCE     = 0.20
W_SPREAD         = 0.10

# ── Priority 8: Portfolio Priority Score weights (additive, new field) ───────
# priority_score blends AI score, confidence, risk, expected value, spread,
# liquidity, historical edge, and the dynamic engine weight signal into one
# 0-100 ranking metric. It does NOT replace allocation_score or any existing
# ENTER/DEFER/SKIP gate — it is purely additional context on each decision.
PW_AI_SCORE        = 0.20
PW_CONFIDENCE      = 0.15
PW_RISK            = 0.15  # inverted: lower decision_log.risk_score = safer = higher term
PW_EXPECTED_VALUE  = 0.15
PW_SPREAD          = 0.10
PW_LIQUIDITY       = 0.10
PW_HISTORICAL_EDGE = 0.10
PW_ENGINE_WEIGHT   = 0.05

# Liquidity normalisation: liquidity in USDC / this divisor, clamped 0-100.
LIQUIDITY_NORMALIZATION_USDC = 100.0


@dataclass
class AllocationDecision:
    condition_id: str
    asset: str
    timeframe: str
    action: str                    # ENTER | DEFER | SKIP
    reason: str
    allocation_score: Optional[float]
    rank: Optional[int]

    # Component scores
    opportunity_score: Optional[float]    = field(default=None)
    market_quality_score: Optional[float] = field(default=None)
    market_quality: Optional[str]         = field(default=None)
    confidence: Optional[float]           = field(default=None)
    spread_tightness: Optional[float]     = field(default=None)

    # Priority 8: portfolio priority score (additive ranking signal, 0-100)
    priority_score: Optional[float]       = field(default=None)

    # Reference IDs
    opportunity_id: Optional[int]  = field(default=None)
    decision_log_id: Optional[int] = field(default=None)


class PortfolioAllocationService:
    """
    Priority 4 — Portfolio Allocation Intelligence.

    Usage::

        svc = PortfolioAllocationService()
        decisions = await svc.allocate(session)
    """

    async def allocate(
        self,
        session: AsyncSession,
        max_concurrent: int = MAX_CONCURRENT_POSITIONS,
        min_score:      float = MIN_ALLOCATION_SCORE,
    ) -> list[AllocationDecision]:
        """
        Rank all active opportunities and return allocation decisions.
        """
        # 1. Count currently open/pending positions
        open_pos_result = await session.execute(
            select(Position).where(Position.status.in_(["OPEN", "PENDING"]))
        )
        open_positions   = list(open_pos_result.scalars().all())
        open_count       = len(open_positions)
        open_cids        = {p.condition_id for p in open_positions}
        open_asset_names = {
            p.asset for p in open_positions if p.asset
        }

        # 2. Load opportunities for currently-active universe markets only.
        #    Phase 9C fix: the opportunities table is UPSERTed by condition_id
        #    and rows are never deleted when a market rolls off the active
        #    universe, so an unfiltered `select(Opportunity)` could allocate
        #    capital against a market that has since expired or become
        #    upcoming-only. `get_all_opportunities` defaults to active_only=True.
        opportunities = await opp_repo.get_all_opportunities(session, min_score=0.0)

        if not opportunities:
            return []

        condition_ids = [o.condition_id for o in opportunities]

        # 3. Load latest MarketQualityScore per condition_id
        mq_map: dict[str, MarketQualityScore] = {}
        for cid in condition_ids:
            mq_res = await session.execute(
                select(MarketQualityScore)
                .where(MarketQualityScore.condition_id == cid)
                .order_by(desc(MarketQualityScore.computed_at))
                .limit(1)
            )
            mq = mq_res.scalar_one_or_none()
            if mq:
                mq_map[cid] = mq

        # 4. Load latest DecisionLog per condition_id for confidence
        dl_map: dict[str, DecisionLog] = {}
        for cid in condition_ids:
            dl_res = await session.execute(
                select(DecisionLog)
                .where(DecisionLog.condition_id == cid)
                .order_by(desc(DecisionLog.created_at))
                .limit(1)
            )
            dl = dl_res.scalar_one_or_none()
            if dl:
                dl_map[cid] = dl

        # 4b. Priority 8 — load additional data for priority_score computation.
        #     These are loaded once outside the per-opportunity loop for efficiency.

        # Latest MarketPriceSnapshot per condition_id (liquidity component)
        ps_map: dict[str, "MarketPriceSnapshot"] = {}
        for cid in condition_ids:
            ps_res = await session.execute(
                select(MarketPriceSnapshot)
                .where(MarketPriceSnapshot.condition_id == cid)
                .order_by(desc(MarketPriceSnapshot.captured_at))
                .limit(1)
            )
            ps = ps_res.scalar_one_or_none()
            if ps:
                ps_map[cid] = ps

        # Market type performance accuracy by (asset, timeframe) — historical edge
        mtp_accuracy: dict[tuple[str, str], float] = {}
        mtp_res = await session.execute(select(MarketTypePerformance))
        for r in mtp_res.scalars().all():
            if r.accuracy is not None and r.asset and r.timeframe:
                mtp_accuracy[(r.asset, r.timeframe)] = r.accuracy

        # Engine weight signal — average (current / base) ratio across all engines.
        # > 1.0 means the dynamic weight system has boosted engines overall (good signal).
        # Normalised to 0-100 (50 = neutral, no adjustment).
        ew_res = await session.execute(select(EngineWeight))
        ew_rows = list(ew_res.scalars().all())
        if ew_rows:
            ratios = [
                r.current_weight / r.base_weight
                for r in ew_rows
                if r.base_weight > 0
            ]
            ew_signal_pct = (
                max(0.0, min(100.0, 50.0 + (sum(ratios) / len(ratios) - 1.0) * 100.0))
                if ratios else 50.0
            )
        else:
            ew_signal_pct = 50.0

        # 5. Score each opportunity
        scored: list[tuple[float, Opportunity, Optional[float]]] = []
        skip_decisions: list[AllocationDecision] = []

        for opp in opportunities:
            cid   = opp.condition_id
            asset = opp.asset or ""
            mq    = mq_map.get(cid)
            dl    = dl_map.get(cid)

            quality_label = mq.market_quality if mq else None
            quality_score: Optional[float] = (
                float(mq.market_score) if mq and mq.market_score is not None else None
            )

            # Gate 1: non-tradable market quality
            if quality_label and quality_label in NON_TRADABLE_QUALITIES:
                skip_decisions.append(AllocationDecision(
                    condition_id=cid,
                    asset=asset,
                    timeframe=opp.timeframe or "",
                    action="SKIP",
                    reason=f"Non-tradable market quality: {quality_label}",
                    allocation_score=None,
                    rank=None,
                    market_quality=quality_label,
                    opportunity_id=opp.id,
                ))
                continue

            # Gate 2: asset already has an open position
            if asset and asset in open_asset_names:
                skip_decisions.append(AllocationDecision(
                    condition_id=cid,
                    asset=asset,
                    timeframe=opp.timeframe or "",
                    action="SKIP",
                    reason=f"Asset {asset} already has an open position",
                    allocation_score=None,
                    rank=None,
                    market_quality=quality_label,
                    opportunity_id=opp.id,
                ))
                continue

            # Gate 3: this exact condition_id already has a position
            if cid in open_cids:
                skip_decisions.append(AllocationDecision(
                    condition_id=cid,
                    asset=asset,
                    timeframe=opp.timeframe or "",
                    action="SKIP",
                    reason="Market already has an open position",
                    allocation_score=None,
                    rank=None,
                    market_quality=quality_label,
                    opportunity_id=opp.id,
                ))
                continue

            confidence: Optional[float] = dl.confidence if dl else None

            # Gate 4 (Phase 9C): required components missing — do not fabricate
            # a neutral 50.0 and let that manufacture an ENTER decision on
            # incomplete data. DEFER explicitly instead so the caller can see
            # the market needs another cycle before it is scored at all.
            if quality_score is None or confidence is None:
                missing = []
                if quality_score is None:
                    missing.append("market_quality_score")
                if confidence is None:
                    missing.append("confidence")
                skip_decisions.append(AllocationDecision(
                    condition_id=cid,
                    asset=asset,
                    timeframe=opp.timeframe or "",
                    action="DEFER",
                    reason=f"NOT_AVAILABLE: missing {', '.join(missing)}",
                    allocation_score=None,
                    rank=None,
                    market_quality=quality_label,
                    opportunity_score=float(opp.opportunity_score or 0.0),
                    market_quality_score=quality_score,
                    confidence=confidence,
                    opportunity_id=opp.id,
                    decision_log_id=dl.id if dl else None,
                ))
                continue

            # Compute composite allocation score
            opp_score  = float(opp.opportunity_score or 0.0)

            # Spread tightness: use yes_spread (smaller spread = better = higher score)
            spread_raw    = float(opp.spread_yes or 0.0) if opp.spread_yes else 0.0
            spread_pct    = min(spread_raw * 100.0, 100.0)   # 0-100 %
            spread_tight  = max(0.0, 100.0 - spread_pct)     # 100 = zero spread, 0 = wide

            allocation_score = (
                opp_score       * W_OPPORTUNITY
                + quality_score * W_MARKET_QUALITY
                + confidence    * W_CONFIDENCE
                + spread_tight  * W_SPREAD
            )
            allocation_score = round(allocation_score, 2)

            # Priority 8 — portfolio priority score (additive context, 0-100).
            # Blends AI score, confidence, entry quality (risk proxy), opportunity
            # score (expected value proxy), spread, liquidity, historical edge,
            # and engine weight signal into one ranking metric.
            # Does NOT replace allocation_score or ENTER/DEFER/SKIP gates.
            # Phase 9C: entry_quality_score is a required input to the risk
            # proxy term, same as market_score/confidence above. If it is
            # genuinely missing (no decision_log yet, or entry-quality filter
            # never ran), do not fabricate a neutral 50.0 — report the
            # priority_score itself as NOT_AVAILABLE (None) rather than
            # silently degrading it with an invented value.
            _entry_quality: Optional[float] = dl.entry_quality_score if dl else None
            if _entry_quality is None:
                priority_score: Optional[float] = None
            else:
                _ai_s = _compute_ai_score(
                    dl.confidence if dl else None,
                    dl.consensus_score if dl else None,
                    dl.entry_quality_score if dl else None,
                )
                # confidence/entry_quality are already confirmed non-None at
                # this point (gated above), so _ai_s cannot be None here.
                _risk_proxy = float(_entry_quality)
                _ps = ps_map.get(cid)
                _liq_raw = float(_ps.liquidity or 0.0) if _ps else 0.0
                _liq_score = min(100.0, _liq_raw / LIQUIDITY_NORMALIZATION_USDC * 100.0)
                # Historical edge has no natural "neutral" value from a data
                # standpoint, but market_type_performance genuinely may not
                # exist yet for a new (asset, timeframe) pair — 50.0 here is
                # a documented "no history yet" prior, not a hidden fallback
                # covering missing decision-log data (see AllocationDecision
                # priority_score docstring / audit §9C).
                _hist_edge = mtp_accuracy.get((asset, opp.timeframe or ""), 50.0)
                priority_score = round(
                    _ai_s           * PW_AI_SCORE
                    + confidence    * PW_CONFIDENCE
                    + _risk_proxy   * PW_RISK
                    + opp_score     * PW_EXPECTED_VALUE
                    + spread_tight  * PW_SPREAD
                    + _liq_score    * PW_LIQUIDITY
                    + _hist_edge    * PW_HISTORICAL_EDGE
                    + ew_signal_pct * PW_ENGINE_WEIGHT,
                    2,
                )

            scored.append((allocation_score, opp, priority_score))

        # 6. Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        # 7. Assign ENTER / DEFER by rank and capacity
        results: list[AllocationDecision] = []
        slots_remaining = max(0, max_concurrent - open_count)
        rank = 1

        for score, opp, p_score in scored:
            cid   = opp.condition_id
            asset = opp.asset or ""
            dl    = dl_map.get(cid)
            mq    = mq_map.get(cid)

            quality_label = mq.market_quality if mq else None
            # Both are guaranteed non-None here: `scored` only contains
            # opportunities that passed the Gate 4 NOT_AVAILABLE check above.
            quality_score = float(mq.market_score) if mq and mq.market_score is not None else None
            spread_raw    = float(opp.spread_yes or 0.0) if opp.spread_yes else 0.0
            spread_pct    = min(spread_raw * 100.0, 100.0)
            spread_tight  = max(0.0, 100.0 - spread_pct)

            if score < min_score:
                action = "DEFER"
                reason = f"Score {score:.1f} below minimum threshold {min_score}"
            elif slots_remaining <= 0:
                action = "DEFER"
                reason = f"Position capacity full ({open_count}/{max_concurrent} open)"
            else:
                action = "ENTER"
                reason = f"Rank #{rank}, composite score={score:.1f}"
                slots_remaining -= 1

            results.append(AllocationDecision(
                condition_id=cid,
                asset=asset,
                timeframe=opp.timeframe or "",
                action=action,
                reason=reason,
                allocation_score=score,
                rank=rank if action == "ENTER" else None,
                opportunity_score=float(opp.opportunity_score or 0.0),
                market_quality_score=quality_score,
                market_quality=quality_label,
                confidence=dl.confidence if dl else None,
                spread_tightness=round(spread_tight, 2),
                priority_score=p_score,
                opportunity_id=opp.id,
                decision_log_id=dl.id if dl else None,
            ))
            rank += 1

        all_decisions = skip_decisions + results

        enter_count = sum(1 for d in all_decisions if d.action == "ENTER")
        defer_count = sum(1 for d in all_decisions if d.action == "DEFER")
        skip_count  = sum(1 for d in all_decisions if d.action == "SKIP")

        logger.info(
            "Portfolio allocation complete",
            opportunities=len(opportunities),
            enter=enter_count,
            defer=defer_count,
            skip=skip_count,
            open_positions=open_count,
            capacity=max_concurrent,
        )
        return all_decisions

    async def get_ranked_summary(
        self,
        session: AsyncSession,
        max_concurrent: int = MAX_CONCURRENT_POSITIONS,
        min_score: float = MIN_ALLOCATION_SCORE,
    ) -> dict:
        """Return a summary dict suitable for API responses."""
        decisions = await self.allocate(session, max_concurrent=max_concurrent, min_score=min_score)

        def _to_dict(d: AllocationDecision) -> dict:
            return {
                "condition_id":        d.condition_id,
                "asset":               d.asset,
                "timeframe":           d.timeframe,
                "action":              d.action,
                "reason":              d.reason,
                "allocation_score":    d.allocation_score,
                "priority_score":      d.priority_score,
                "rank":                d.rank,
                "opportunity_score":   d.opportunity_score,
                "market_quality_score":d.market_quality_score,
                "market_quality":      d.market_quality,
                "confidence":          d.confidence,
                "spread_tightness":    d.spread_tightness,
                "opportunity_id":      d.opportunity_id,
                "decision_log_id":     d.decision_log_id,
            }

        return {
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "total":        len(decisions),
            "open_positions_count": sum(
                1 for d in decisions if d.action == "SKIP" and "open position" in d.reason
            ),
            "enter": [_to_dict(d) for d in decisions if d.action == "ENTER"],
            "defer": [_to_dict(d) for d in decisions if d.action == "DEFER"],
            "skip":  [_to_dict(d) for d in decisions if d.action == "SKIP"],
        }
