"""
Decision Engine — Phase Next: Decision Engine Intelligence Upgrade.

Core philosophy: Polymarket data (YES/NO bid/ask, spread, liquidity, volume,
countdown, active/closed state) is the SOURCE OF TRUTH — read as-is, never
recomputed or predicted. Binance/technical indicators (momentum, trend,
volatility, orderbook, funding) are SUPPORTING / CONFIRMATION signals only.

No Machine Learning. No LLM. No prediction models.
Fully rule-based. Fully explainable. Fully auditable. Fully deterministic.

INTELLIGENCE UPGRADE — 8 new phases wrapped around the existing 10-step chain:

  Phase 1  — Consensus Engine
               Each voting engine casts a directional vote. Instead of summing
               directly, compute Agreement, Conflict, Consensus Score, then
               derive a weighted consensus direction.

  Phase 2  — Market Quality Filter (gate)
               Market Quality score 0-100 from Spread, Liquidity, Volume,
               Time-to-Expiry, Bid/Ask state. Low score → automatic WAIT.

  Phase 3  — Entry Quality Engine
               Not just BUY YES or BUY NO — is NOW a good moment to enter?
               YES too expensive? NO too expensive? Spread too wide? Liquidity
               bad? Opportunity score low? Output: Entry Quality 0-100.

  Phase 4  — Confidence Engine
               NOT a simple weighted average. Uses:
               Agreement (consensus) + Market Quality + Entry Quality +
               Trend Strength + Momentum Strength + Volatility Factor + Risk
               + Multi-Timeframe Context Multiplier.

  Phase 5  — Explainability
               Every decision includes a numbered reasoning chain (steps[])
               covering all phases. All reasons stored in decision_logs.reasons.

  Phase 6  — Decision History
               Append-only. Every cycle writes one row per market to
               decision_logs. Never overwrites — always appends.

  Phase 7  — Self-Validation
               Before the final decision is emitted, run conflict checks:
               Trend BUY + Momentum SELL → WAIT + "Conflict"
               Wide Spread → WAIT. Low Liquidity → WAIT.

  Phase 8  — Engine Health
               Stored in decision_logs: conflict_detected, consensus_score,
               agreement_level, entry_quality_score. Aggregated by
               decision_repository.get_decision_stats().

This engine is READ-ONLY with respect to every other table — only SELECTs
from all engine score tables and INSERTs append-only rows into decision_logs.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.core.logging import get_logger
from app.models.funding_score import FundingScore
from app.models.market_context_score import MarketContextScore
from app.models.market_quality_score import MarketQualityScore
from app.models.momentum_score import MomentumScore
from app.models.news_score import NewsScore
from app.models.opportunity import Opportunity
from app.models.orderbook_score import OrderbookScore
from app.models.order import Order
from app.models.position import Position
from app.models.trend_score import TrendScore
from app.models.volatility_score import VolatilityScore
from app.repositories import decision_repository as repo
from app.repositories.market_price_repository import get_latest_by_condition as _price_get_latest
from app.repositories.universe_repository import get_active_universe

logger = get_logger(__name__)

# ── Directional vote weights ────────────────────────────────────────────────────
WEIGHT_OPPORTUNITY = 0.30
WEIGHT_ORDERBOOK   = 0.20
WEIGHT_MOMENTUM    = 0.10
WEIGHT_TREND       = 0.10
WEIGHT_FUNDING     = 0.10

# ── Market Context confidence multiplier ────────────────────────────────────────
CONTEXT_MULTIPLIER = {"ALIGNED": 1.0, "MIXED": 0.85, "CONFLICT": 0.6}
CONTEXT_MULTIPLIER_UNKNOWN = 0.9

# ── Decision thresholds ─────────────────────────────────────────────────────────
DECISION_VOTE_THRESHOLD  = 0.15   # |vote_score| below this → WAIT
MIN_DECISION_CONFIDENCE  = 45.0   # overall confidence below this → WAIT
RISK_MIN_SCORE           = 40.0   # risk_score below this → force WAIT (hard gate)

# ── Phase 2: Market Quality Filter ─────────────────────────────────────────────
# Non-tradable quality labels produced by the Market Behaviour Engine
NON_TRADABLE_QUALITIES = {"BAD", "High Risk", "Illiquid", "Avoid"}
MIN_MARKET_QUALITY_SCORE = 20.0   # score below this → WAIT even if label is AVERAGE

# ── Phase 3: Entry Quality thresholds ───────────────────────────────────────────
MIN_ENTRY_QUALITY_SCORE = 30.0    # entry quality below this → WAIT
EXPENSIVE_PRICE_THRESHOLD = 0.82  # YES/NO mid above this → "too expensive"

# ── Phase 7: Self-Validation ────────────────────────────────────────────────────
CONFLICT_SPREAD_THRESHOLD    = 0.08  # spread_yes above this → WAIT (wide spread)
CONFLICT_AGREEMENT_THRESHOLD = 0.30  # if losing side has >30% weight → conflict


class DecisionEngine:
    """
    Usage (from a background loop)::

        engine = DecisionEngine()
        result = await engine.decide(session)
    """

    # ── Phase 7: Calibration constants ────────────────────────────────────────
    _MIN_CALIBRATION_SAMPLES = 5    # minimum bucket samples before trusting bucket data
    _MIN_TOTAL_EVALUATED     = 10   # minimum total outcomes before applying any correction
    _CORRECTION_FRACTION     = 0.25 # fraction of calibration error to apply as adjustment
    _MAX_ADJUSTMENT          = 15.0 # max absolute confidence adjustment in points

    async def _load_calibration_data(
        self, session: AsyncSession
    ) -> "tuple[Optional[object], list[object]]":
        """
        Phase 7 — Historical Database: load CalibrationSummary and per-bucket
        stats once per decision cycle.  Falls back to (None, []) on any error
        so calibration is always a graceful no-op when the table is empty.
        """
        from app.repositories import confidence_calibration_repository as cal_repo
        try:
            summary = await cal_repo.get_summary(session)
            buckets = await cal_repo.get_all_buckets(session)
            return summary, buckets
        except Exception as exc:
            logger.debug("Calibration data unavailable — no adjustment", error=str(exc))
            return None, []

    async def _load_effective_weights(self, session: AsyncSession) -> dict:
        """
        Load dynamic engine weights from the engine_weights table (Priority 3).
        Falls back to hardcoded constants if the table is empty or DB error occurs.
        """
        from app.repositories.engine_weight_repository import get_effective_weights
        try:
            weights = await get_effective_weights(session)
            return weights
        except Exception as exc:
            logger.debug("Dynamic weights unavailable — using base weights", error=str(exc))
            return {
                "opportunity": WEIGHT_OPPORTUNITY,
                "orderbook":   WEIGHT_ORDERBOOK,
                "momentum":    WEIGHT_MOMENTUM,
                "trend":       WEIGHT_TREND,
                "funding":     WEIGHT_FUNDING,
            }

    async def decide(self, session: AsyncSession) -> dict:
        started = datetime.now(timezone.utc)

        # Priority 3: load dynamic weights once per cycle (fallback to hardcoded)
        self._current_weights: dict = await self._load_effective_weights(session)

        # Phase 7 — Historical Database: load calibration data once per cycle
        self._calibration_data: tuple = await self._load_calibration_data(session)

        universe = await get_active_universe(session)
        risk_score, risk_gated, risk_reason = await self._compute_risk_context(session)

        errors = 0

        for market in universe:
            try:
                await self._decide_market(session, market, risk_score, risk_gated, risk_reason)
            except Exception as exc:
                logger.error(
                    "Decision engine error",
                    condition_id=market.condition_id,
                    asset=market.asset,
                    timeframe=market.timeframe,
                    error=str(exc),
                )
                errors += 1
                continue

        await session.commit()

        elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        logger.info(
            "Decision engine cycle complete",
            markets=len(universe),
            risk_score=risk_score,
            risk_gated=risk_gated,
            errors=errors,
            duration_ms=elapsed_ms,
        )
        return {
            "markets": len(universe),
            "risk_score": risk_score,
            "risk_gated": risk_gated,
            "errors": errors,
            "duration_ms": elapsed_ms,
        }

    async def _decide_market(
        self,
        session: AsyncSession,
        market,
        risk_score: float,
        risk_gated: bool,
        risk_reason: Optional[str],
    ) -> None:
        condition_id = market.condition_id
        asset        = market.asset
        timeframe    = market.timeframe

        steps: list[str] = []          # numbered reasoning chain (Phase 5)
        supporting_engines: list[str] = []

        # ══════════════════════════════════════════════════════════════════════
        # STEP 0 — Order Flow Pre-Check
        # Classifies the market as SEED_BOOK_ONLY or WITH_ORDER_FLOW before
        # any engine scores are evaluated.  Non-blocking: decision proceeds
        # regardless, but the note informs calibration and downstream consumers.
        # ══════════════════════════════════════════════════════════════════════
        _price_snaps = await _price_get_latest(session, condition_id, limit=1)
        if _price_snaps:
            _snap = _price_snaps[0]
            _has_order_flow = bool(_snap.volume is not None and _snap.volume > 0.0)
            if _has_order_flow:
                steps.append(
                    f"[Step 0] Order Flow: ACTIVE_WITH_ORDER_FLOW — "
                    f"volume={_snap.volume:.2f}; real trades confirmed."
                )
            else:
                steps.append(
                    f"[Step 0] Order Flow: SEED_BOOK_ONLY — "
                    f"volume=null liquidity=null; AMM init phase, no confirmed human "
                    f"trades yet. Confidence/signals based on seed-level book only. "
                    f"Reason: NO_ORDER_FLOW"
                )
        else:
            steps.append(
                "[Step 0] Order Flow: PRICE_DATA_MISSING — "
                "no price snapshot available; proceeding on market quality data only."
            )

        # ══════════════════════════════════════════════════════════════════════
        # STEP 1 — Market Behaviour (PRIMARY GATE)
        # Phase 2: Market Quality Filter
        # ══════════════════════════════════════════════════════════════════════
        market_quality_row = await self._get_market_quality(session, condition_id)
        market_quality_score_val = market_quality_row.market_score if market_quality_row else None
        market_quality   = market_quality_row.market_quality   if market_quality_row else None
        market_confidence= market_quality_row.market_confidence if market_quality_row else None
        market_risk      = market_quality_row.market_risk       if market_quality_row else None
        market_behaviours_raw = market_quality_row.market_behaviours if market_quality_row else None
        behaviours: list[str] = (
            [b.strip() for b in market_behaviours_raw.split(",") if b.strip()]
            if market_behaviours_raw else []
        )

        if market_quality_row is None:
            steps.append(
                "[Step 1] Market Behaviour: no market data yet — primary engine has no score.\n"
                "         → DECISION: WAIT (cannot trade without Polymarket data)"
            )
            await self._save_wait(
                session, condition_id, asset, timeframe,
                risk_score, risk_gated, steps, supporting_engines,
            )
            return

        supporting_engines.append("Polymarket Market Engine")
        beh_display = market_behaviours_raw or "no behaviour data yet"
        steps.append(
            f"[Step 1] Market Behaviour: {beh_display}\n"
            f"         → Market quality={market_quality} score={market_quality_score_val:.1f} "
            f"risk={market_risk}"
        )

        # Phase 2: Non-tradable quality gate
        if market_quality in NON_TRADABLE_QUALITIES:
            quality_interpretation = self._interpret_non_tradable(market_quality, behaviours)
            steps.append(
                f"[Gate]   Market not tradable ({market_quality}). {quality_interpretation}\n"
                f"         → DECISION: WAIT"
            )
            await self._save_wait(
                session, condition_id, asset, timeframe,
                risk_score, risk_gated, steps, supporting_engines,
                market_quality_score=market_quality_score_val,
                market_quality=market_quality,
                market_confidence=market_confidence,
                market_risk=market_risk,
                confidence=market_confidence or 0.0,
            )
            return

        # Phase 2: numeric market quality floor (low score even for AVERAGE label)
        if (market_quality_score_val is not None
                and market_quality_score_val < MIN_MARKET_QUALITY_SCORE):
            steps.append(
                f"[Gate]   Market quality score={market_quality_score_val:.1f} "
                f"below minimum {MIN_MARKET_QUALITY_SCORE:.0f}.\n"
                f"         → DECISION: WAIT (market not ready)"
            )
            await self._save_wait(
                session, condition_id, asset, timeframe,
                risk_score, risk_gated, steps, supporting_engines,
                market_quality_score=market_quality_score_val,
                market_quality=market_quality,
                market_confidence=market_confidence,
                market_risk=market_risk,
                confidence=market_confidence or 0.0,
            )
            return

        # ══════════════════════════════════════════════════════════════════════
        # STEP 2 — Spread Interpretation
        # ══════════════════════════════════════════════════════════════════════
        spread_yes = market_quality_row.spread_yes
        spread_interpretation = self._interpret_spread(spread_yes, behaviours)
        steps.append(f"[Step 2] Spread: {spread_interpretation}")

        # ══════════════════════════════════════════════════════════════════════
        # STEP 3 — Buy / Sell Pressure from Behaviours
        # ══════════════════════════════════════════════════════════════════════
        pressure_signal, pressure_interpretation = self._interpret_pressure(behaviours)
        steps.append(f"[Step 3] Market Pressure: {pressure_interpretation}")

        # ── Gather supporting engines ─────────────────────────────────────────
        momentum      = await self._get_momentum(session, asset, timeframe)
        trend         = await self._get_trend(session, asset, timeframe)
        volatility    = await self._get_volatility(session, asset, timeframe)
        opportunity   = await self._get_opportunity(session, condition_id)
        orderbook     = await self._get_orderbook(session, asset)
        funding       = await self._get_funding(session, asset)
        news          = await self._get_news(session, asset)
        market_context= await self._get_market_context(session, asset)

        # ── Phase 1: Build vote list ──────────────────────────────────────────
        votes: list[tuple[float, float]] = []  # (vote [-1,+1], weight)

        # Opportunity vote (Polymarket mispricing — strongest directional signal)
        opportunity_score_val = None
        opportunity_direction = None
        if opportunity is not None:
            supporting_engines.append("Opportunity Engine")
            opportunity_score_val = opportunity.opportunity_score
            opportunity_direction = opportunity.direction
            opp_vote = (
                1.0  if opportunity.direction == "BUY_YES" else
                -1.0 if opportunity.direction == "BUY_NO"  else 0.0
            )
            conf_frac = min((opportunity.opportunity_score or 0.0) / 100.0, 1.0)
            votes.append((opp_vote, self._current_weights.get("opportunity", WEIGHT_OPPORTUNITY) * conf_frac))

        # ══════════════════════════════════════════════════════════════════════
        # STEP 4 — Orderbook Confirmation
        # ══════════════════════════════════════════════════════════════════════
        orderbook_direction = None
        orderbook_confidence = None
        if orderbook is not None:
            supporting_engines.append("Orderbook Engine")
            orderbook_direction  = orderbook.direction
            orderbook_confidence = orderbook.confidence
            ob_vote = (
                1.0  if orderbook.direction == "BULLISH" else
                -1.0 if orderbook.direction == "BEARISH" else 0.0
            )
            conf_frac = (orderbook.confidence or 0.0) / 100.0
            votes.append((ob_vote, self._current_weights.get("orderbook", WEIGHT_ORDERBOOK) * conf_frac))
            ob_interp = self._interpret_confirmation(
                "Orderbook", orderbook.direction, pressure_signal, orderbook.reason
            )
            steps.append(f"[Step 4] Orderbook: {ob_interp}")
        else:
            steps.append("[Step 4] Orderbook: no data yet → no confirmation")

        # ══════════════════════════════════════════════════════════════════════
        # STEP 5 — Funding Rate
        # ══════════════════════════════════════════════════════════════════════
        funding_direction = None
        funding_confidence = None
        if funding is not None:
            supporting_engines.append("Funding Engine")
            funding_direction  = funding.direction
            funding_confidence = funding.confidence
            fund_vote = (
                1.0  if funding.direction == "BULLISH" else
                -1.0 if funding.direction == "BEARISH" else 0.0
            )
            conf_frac = (funding.confidence or 0.0) / 100.0
            votes.append((fund_vote, self._current_weights.get("funding", WEIGHT_FUNDING) * conf_frac))
            steps.append(f"[Step 5] Funding: {self._interpret_funding(funding.direction, funding.reason)}")
        else:
            steps.append("[Step 5] Funding: no data yet → neutral (no conflict)")

        # ══════════════════════════════════════════════════════════════════════
        # STEP 6 — Momentum
        # ══════════════════════════════════════════════════════════════════════
        momentum_score_val = None
        momentum_direction = None
        if momentum is not None:
            supporting_engines.append("Momentum Engine")
            momentum_score_val = momentum.score
            momentum_direction = momentum.direction
            mom_vote = (
                1.0  if momentum.direction == "BULLISH" else
                -1.0 if momentum.direction == "BEARISH" else 0.0
            )
            conf_frac = (momentum.confidence or 0.0) / 100.0
            votes.append((mom_vote, self._current_weights.get("momentum", WEIGHT_MOMENTUM) * conf_frac))
            mom_interp = self._interpret_support_engine(
                "Momentum", momentum.direction, pressure_signal, momentum.reason
            )
            steps.append(f"[Step 6] Momentum: {mom_interp}")
        else:
            steps.append("[Step 6] Momentum: insufficient candle history → not counted")

        # ══════════════════════════════════════════════════════════════════════
        # STEP 7 — Trend
        # ══════════════════════════════════════════════════════════════════════
        trend_score_val = None
        trend_direction = None
        if trend is not None:
            supporting_engines.append("Trend Engine")
            trend_score_val = trend.score
            trend_direction = trend.direction
            trend_vote = (
                1.0  if trend.direction == "UP"   else
                -1.0 if trend.direction == "DOWN" else 0.0
            )
            conf_frac = (trend.confidence or 0.0) / 100.0
            votes.append((trend_vote, self._current_weights.get("trend", WEIGHT_TREND) * conf_frac))
            trend_dir_norm = (
                "BULLISH" if trend.direction == "UP"   else
                "BEARISH" if trend.direction == "DOWN" else trend.direction
            )
            steps.append(
                f"[Step 7] Trend: {self._interpret_support_engine('Trend', trend_dir_norm, pressure_signal, trend.reason)}"
            )
        else:
            steps.append("[Step 7] Trend: insufficient candle history → not counted")

        # ── News (confidence-only contributor) ────────────────────────────────
        news_sentiment  = None
        news_confidence = None
        if news is not None:
            news_sentiment  = news.sentiment
            news_confidence = news.confidence

        # ── Volatility — confidence-only contributor ──────────────────────────
        volatility_score_val = None
        volatility_regime    = None
        if volatility is not None:
            supporting_engines.append("Volatility Engine")
            volatility_score_val = volatility.score
            volatility_regime    = volatility.regime

        # ══════════════════════════════════════════════════════════════════════
        # STEP 8 — Market Context (multi-timeframe alignment)
        # ══════════════════════════════════════════════════════════════════════
        market_context_status     = None
        market_context_confidence = None
        context_multiplier = CONTEXT_MULTIPLIER_UNKNOWN

        if market_context is not None:
            supporting_engines.append("Market Context Engine")
            market_context_status     = market_context.status
            market_context_confidence = market_context.confidence
            context_multiplier = CONTEXT_MULTIPLIER.get(
                market_context.status, CONTEXT_MULTIPLIER_UNKNOWN
            )
            steps.append(
                f"[Step 8] Market Context: {self._interpret_context(market_context.status, context_multiplier)}"
            )
        else:
            steps.append(
                f"[Step 8] Market Context: no data yet → "
                f"confidence multiplier={CONTEXT_MULTIPLIER_UNKNOWN:.2f} (cautious)"
            )

        # ── Risk hard gate ────────────────────────────────────────────────────
        supporting_engines.append("Risk Engine")

        # ══════════════════════════════════════════════════════════════════════
        # PHASE 1 — Consensus Engine
        # Compute Agreement, Conflict, Consensus Score from all directional votes
        # ══════════════════════════════════════════════════════════════════════
        consensus_score, agreement_level, conflict_detected, consensus_interp = (
            self._compute_consensus(votes)
        )

        # Combine directional votes for the vote_score
        total_vote_weight = sum(w for _, w in votes)
        vote_score = (
            sum(v * w for v, w in votes) / total_vote_weight
            if total_vote_weight > 0 else 0.0
        )

        steps.append(
            f"[Phase 1] Consensus: {consensus_interp}\n"
            f"          consensus_score={consensus_score:.1f} "
            f"agreement={agreement_level:.2f} "
            f"conflict={'YES' if conflict_detected else 'NO'}"
        )

        # ══════════════════════════════════════════════════════════════════════
        # PHASE 3 — Entry Quality Engine
        # Is NOW a good moment to enter? (price, spread, liquidity, opportunity)
        # ══════════════════════════════════════════════════════════════════════
        # Determine tentative direction from vote_score for price attractiveness
        tentative_direction = (
            "BUY_YES" if vote_score > 0 else
            "BUY_NO"  if vote_score < 0 else "NEUTRAL"
        )
        entry_quality_score, entry_quality_reasons = self._compute_entry_quality(
            market_quality_row, behaviours, opportunity_score_val,
            opportunity_direction, tentative_direction,
        )
        steps.append(
            f"[Phase 3] Entry Quality: score={entry_quality_score:.1f}/100\n"
            f"          {entry_quality_reasons}"
        )

        # ══════════════════════════════════════════════════════════════════════
        # PHASE 4 — Confidence Engine
        # Multi-factor confidence (NOT a simple average)
        # ══════════════════════════════════════════════════════════════════════
        overall_confidence = self._compute_confidence_engine(
            agreement_level      = agreement_level,
            market_quality_score = market_quality_score_val or 0.0,
            entry_quality_score  = entry_quality_score,
            trend_score          = trend_score_val,
            momentum_score       = momentum_score_val,
            volatility_score     = volatility_score_val,
            risk_score           = risk_score,
            context_multiplier   = context_multiplier,
            conflict_detected    = conflict_detected,
            news_confidence      = news_confidence,
        )
        steps.append(
            f"[Phase 4] Confidence Engine: {overall_confidence:.1f}%\n"
            f"          (consensus_bonus={max(0.0,(agreement_level-0.5)*2)*30:.1f} "
            f"mkt_quality={(market_quality_score_val or 0)/100*25:.1f} "
            f"entry_quality={entry_quality_score/100*20:.1f} "
            f"context_mult={context_multiplier:.2f})"
        )

        # ══════════════════════════════════════════════════════════════════════
        # PHASE 4b — Calibration Feedback (Phase 7 — Historical Database)
        # Adjust confidence using historical outcome-calibration data so that
        # systematic over/underconfidence from past cycles is corrected forward.
        # ══════════════════════════════════════════════════════════════════════
        _cal_summary, _cal_buckets = self._calibration_data
        overall_confidence, _calib_note = self._apply_calibration_adjustment(
            overall_confidence,
            _cal_summary,
            _cal_buckets,
            self._MIN_CALIBRATION_SAMPLES,
            self._MIN_TOTAL_EVALUATED,
            self._CORRECTION_FRACTION,
            self._MAX_ADJUSTMENT,
        )
        if _calib_note:
            steps.append(f"[Phase 4b] Calibration Feedback: {_calib_note}")

        # ══════════════════════════════════════════════════════════════════════
        # STEP 9 — Risk Assessment
        # ══════════════════════════════════════════════════════════════════════
        steps.append(
            f"[Step 9] Risk: {self._interpret_risk(risk_score, risk_gated, risk_reason)}"
        )

        # ══════════════════════════════════════════════════════════════════════
        # PHASE 7 — Self-Validation
        # Run conflict checks BEFORE emitting a directional decision.
        # Each check may override the decision to WAIT with an explicit reason.
        # ══════════════════════════════════════════════════════════════════════
        validation_conflict, validation_reason = self._self_validate(
            trend_direction     = trend_direction,
            momentum_direction  = momentum_direction,
            spread_yes          = spread_yes,
            behaviours          = behaviours,
            conflict_detected   = conflict_detected,
        )

        if validation_conflict:
            steps.append(
                f"[Phase 7] Self-Validation: CONFLICT DETECTED — {validation_reason}\n"
                f"          → Override to WAIT"
            )

        # ══════════════════════════════════════════════════════════════════════
        # STEP 10 — Final Decision
        # ══════════════════════════════════════════════════════════════════════
        if risk_gated:
            decision = "WAIT"
            gate_reason = f"risk gate active ({risk_reason})"
            final_reasons = self._build_final_reasons(
                decision, overall_confidence, behaviours, orderbook, funding,
                momentum, trend, market_context, volatility, opportunity_direction,
                gate_reason=gate_reason,
            )
            steps.append(
                f"[Step 10] DECISION: WAIT — risk gate active\n"
                f"          Confidence: {overall_confidence:.1f}%\n"
                f"          Reason: {final_reasons}"
            )

        elif validation_conflict:
            decision = "WAIT"
            final_reasons = self._build_final_reasons(
                decision, overall_confidence, behaviours, orderbook, funding,
                momentum, trend, market_context, volatility, opportunity_direction,
                gate_reason=f"self-validation: {validation_reason}",
            )
            steps.append(
                f"[Step 10] DECISION: WAIT — self-validation conflict\n"
                f"          Confidence: {overall_confidence:.1f}%\n"
                f"          Reason: {final_reasons}"
            )

        elif overall_confidence < MIN_DECISION_CONFIDENCE:
            decision = "WAIT"
            final_reasons = self._build_final_reasons(
                decision, overall_confidence, behaviours, orderbook, funding,
                momentum, trend, market_context, volatility, opportunity_direction,
                gate_reason=(
                    f"confidence {overall_confidence:.1f}% "
                    f"below minimum {MIN_DECISION_CONFIDENCE}%"
                ),
            )
            steps.append(
                f"[Step 10] DECISION: WAIT — insufficient confidence\n"
                f"          Confidence: {overall_confidence:.1f}%\n"
                f"          Reason: {final_reasons}"
            )

        elif entry_quality_score < MIN_ENTRY_QUALITY_SCORE:
            decision = "WAIT"
            final_reasons = self._build_final_reasons(
                decision, overall_confidence, behaviours, orderbook, funding,
                momentum, trend, market_context, volatility, opportunity_direction,
                gate_reason=(
                    f"entry quality {entry_quality_score:.1f} "
                    f"below minimum {MIN_ENTRY_QUALITY_SCORE:.0f} — "
                    f"{entry_quality_reasons}"
                ),
            )
            steps.append(
                f"[Step 10] DECISION: WAIT — poor entry quality\n"
                f"          Confidence: {overall_confidence:.1f}%\n"
                f"          Entry Quality: {entry_quality_score:.1f}/100\n"
                f"          Reason: {final_reasons}"
            )

        elif vote_score > DECISION_VOTE_THRESHOLD:
            decision = "BUY_YES"
            final_reasons = self._build_final_reasons(
                decision, overall_confidence, behaviours, orderbook, funding,
                momentum, trend, market_context, volatility, opportunity_direction,
            )
            steps.append(
                f"[Step 10] DECISION: BUY YES\n"
                f"          Confidence: {overall_confidence:.1f}%\n"
                f"          Consensus: {consensus_score:.1f}/100\n"
                f"          Entry Quality: {entry_quality_score:.1f}/100\n"
                f"          Reason:\n{final_reasons}"
            )

        elif vote_score < -DECISION_VOTE_THRESHOLD:
            decision = "BUY_NO"
            final_reasons = self._build_final_reasons(
                decision, overall_confidence, behaviours, orderbook, funding,
                momentum, trend, market_context, volatility, opportunity_direction,
            )
            steps.append(
                f"[Step 10] DECISION: BUY NO\n"
                f"          Confidence: {overall_confidence:.1f}%\n"
                f"          Consensus: {consensus_score:.1f}/100\n"
                f"          Entry Quality: {entry_quality_score:.1f}/100\n"
                f"          Reason:\n{final_reasons}"
            )

        else:
            decision = "WAIT"
            final_reasons = self._build_final_reasons(
                decision, overall_confidence, behaviours, orderbook, funding,
                momentum, trend, market_context, volatility, opportunity_direction,
                gate_reason=f"vote_score={vote_score:.3f} — signals inconclusive",
            )
            steps.append(
                f"[Step 10] DECISION: WAIT — signals inconclusive\n"
                f"          Confidence: {overall_confidence:.1f}%\n"
                f"          Reason: {final_reasons}"
            )

        # Phase 6: Decision History — append-only INSERT
        await repo.create_decision_log(
            session,
            condition_id        = condition_id,
            asset               = asset,
            timeframe           = timeframe,
            decision            = decision,
            confidence          = overall_confidence,
            vote_score          = vote_score,
            # Phase 1: Consensus Engine
            consensus_score     = consensus_score,
            agreement_level     = agreement_level,
            conflict_detected   = conflict_detected or validation_conflict,
            # Phase 3: Entry Quality Engine
            entry_quality_score = entry_quality_score,
            # Per-engine snapshots
            signal_confidence   = None,
            signal_regime       = None,
            momentum_score      = momentum_score_val,
            momentum_direction  = momentum_direction,
            trend_score         = trend_score_val,
            trend_direction     = trend_direction,
            volatility_score    = volatility_score_val,
            volatility_regime   = volatility_regime,
            opportunity_score   = opportunity_score_val,
            opportunity_direction = opportunity_direction,
            risk_score          = risk_score,
            risk_gated          = risk_gated,
            market_quality_score = market_quality_score_val,
            market_quality      = market_quality,
            market_confidence   = market_confidence,
            market_risk         = market_risk,
            market_context_status     = market_context_status,
            market_context_confidence = market_context_confidence,
            orderbook_direction  = orderbook_direction,
            orderbook_confidence = orderbook_confidence,
            funding_direction    = funding_direction,
            funding_confidence   = funding_confidence,
            news_sentiment       = news_sentiment,
            news_confidence      = news_confidence,
            supporting_engines   = ", ".join(supporting_engines),
            # Phase 5: Explainability — full reasoning chain
            reasons = "\n".join(steps),
        )

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 1 — Consensus Engine
    # ══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _compute_consensus(
        votes: list[tuple[float, float]],
    ) -> tuple[float, float, bool, str]:
        """
        Compute agreement, conflict and consensus score from all directional votes.

        Args:
            votes: list of (vote, weight). vote is -1 (bearish), 0 (neutral), +1 (bullish).

        Returns:
            (consensus_score 0-100, agreement_level 0-1, conflict_detected, interpretation)

            consensus_score — 0 = pure split, 100 = unanimous agreement
            agreement_level — fraction of directional weight on the winning side
                              0.5 = perfect split, 1.0 = unanimous
            conflict_detected — True when the losing side has >30% of total weight
        """
        directional = [(v, w) for v, w in votes if abs(v) > 0.01]

        if not directional:
            return 50.0, 0.5, False, "No directional votes — consensus undetermined"

        bullish_weight = sum(w for v, w in directional if v > 0)
        bearish_weight = sum(w for v, w in directional if v < 0)
        total_weight   = bullish_weight + bearish_weight

        if total_weight < 1e-9:
            return 50.0, 0.5, False, "Vote weights effectively zero — no consensus"

        winning_weight = max(bullish_weight, bearish_weight)
        losing_weight  = min(bullish_weight, bearish_weight)

        agreement_level   = winning_weight / total_weight       # 0.5 → 1.0
        losing_fraction   = losing_weight  / total_weight       # 0.0 → 0.5
        conflict_detected = losing_fraction > CONFLICT_AGREEMENT_THRESHOLD

        # Map agreement [0.5, 1.0] → consensus_score [0, 100]
        consensus_score = max(0.0, (agreement_level - 0.5) * 200.0)

        direction_label = "BULLISH" if bullish_weight >= bearish_weight else "BEARISH"

        if conflict_detected:
            interp = (
                f"CONFLICT — {direction_label} but opposing weight={losing_fraction:.0%}. "
                f"Engines disagree. Conviction reduced."
            )
        elif agreement_level >= 0.90:
            interp = (
                f"STRONG CONSENSUS — {agreement_level:.0%} weight aligned {direction_label}. "
                f"High conviction."
            )
        elif agreement_level >= 0.70:
            interp = (
                f"MODERATE CONSENSUS — {agreement_level:.0%} weight aligned {direction_label}. "
                f"Good conviction."
            )
        else:
            interp = (
                f"WEAK CONSENSUS — {agreement_level:.0%} weight aligned {direction_label}. "
                f"Borderline conviction."
            )

        return round(consensus_score, 2), round(agreement_level, 4), conflict_detected, interp

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 3 — Entry Quality Engine
    # ══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _compute_entry_quality(
        market_quality_row: Optional[MarketQualityScore],
        behaviours: list[str],
        opportunity_score: Optional[float],
        opportunity_direction: Optional[str],
        tentative_direction: str,  # "BUY_YES" | "BUY_NO" | "NEUTRAL"
    ) -> tuple[float, str]:
        """
        Compute entry quality score (0-100).

        Evaluates whether THIS MOMENT is a good entry point — not just whether
        the direction is right, but whether price, spread, liquidity, and
        opportunity alignment make the entry worthwhile right now.

        Returns (entry_quality_score 0-100, human_readable_reasons).
        """
        if market_quality_row is None:
            return 0.0, "No market data — cannot assess entry quality"

        score   = 50.0  # start neutral
        reasons: list[str] = []
        b_set   = set(behaviours)

        # 1. Spread quality (±25 points)
        spread_yes = market_quality_row.spread_yes
        if spread_yes is not None:
            if spread_yes < 0.02:
                score += 25
                reasons.append(f"Tight spread ({spread_yes:.4f}) — low friction")
            elif spread_yes < 0.04:
                score += 12
                reasons.append(f"Moderate spread ({spread_yes:.4f}) — acceptable")
            elif spread_yes > 0.08:
                score -= 25
                reasons.append(f"Wide spread ({spread_yes:.4f}) — high friction penalty")
            else:
                score -= 8
                reasons.append(f"Above-average spread ({spread_yes:.4f}) — minor penalty")

        # 2. Price attractiveness for the tentative direction (±20 points)
        yes_bid = market_quality_row.yes_bid
        yes_ask = market_quality_row.yes_ask
        if yes_bid is not None and yes_ask is not None:
            yes_mid = (yes_bid + yes_ask) / 2.0
            no_mid  = 1.0 - yes_mid
            if tentative_direction == "BUY_YES":
                if yes_mid > EXPENSIVE_PRICE_THRESHOLD:
                    score -= 20
                    reasons.append(
                        f"YES too expensive (mid={yes_mid:.2f}) — poor entry, "
                        f"upside limited"
                    )
                elif yes_mid < 0.20:
                    score += 20
                    reasons.append(
                        f"YES very cheap (mid={yes_mid:.2f}) — high upside potential"
                    )
                elif yes_mid < 0.40:
                    score += 10
                    reasons.append(
                        f"YES at attractive price (mid={yes_mid:.2f})"
                    )
                else:
                    reasons.append(f"YES at fair price (mid={yes_mid:.2f})")
            elif tentative_direction == "BUY_NO":
                if no_mid > EXPENSIVE_PRICE_THRESHOLD:
                    score -= 20
                    reasons.append(
                        f"NO too expensive (mid={no_mid:.2f}) — poor entry, "
                        f"upside limited"
                    )
                elif no_mid < 0.20:
                    score += 20
                    reasons.append(
                        f"NO very cheap (mid={no_mid:.2f}) — high upside potential"
                    )
                elif no_mid < 0.40:
                    score += 10
                    reasons.append(f"NO at attractive price (mid={no_mid:.2f})")
                else:
                    reasons.append(f"NO at fair price (mid={no_mid:.2f})")

        # 3. Liquidity quality from behaviours (±15 points)
        if "Increasing Liquidity" in b_set or "High Participation" in b_set:
            score += 15
            reasons.append("Liquidity growing — good entry window")
        elif "Low Liquidity" in b_set or "Decreasing Liquidity" in b_set:
            score -= 15
            reasons.append("Low/decreasing liquidity — thin market, avoid")

        # 4. Opportunity Engine alignment (+15 points max)
        if (opportunity_score is not None
                and opportunity_direction is not None
                and opportunity_direction != "NEUTRAL"):
            if opportunity_direction == tentative_direction:
                bonus = min(15.0, (opportunity_score / 100.0) * 15.0)
                score += bonus
                reasons.append(
                    f"Opportunity engine confirms {opportunity_direction} "
                    f"(score={opportunity_score:.0f}) — aligned entry"
                )
            else:
                score -= 10
                reasons.append(
                    f"Opportunity engine disagrees ({opportunity_direction} vs {tentative_direction})"
                )

        # Clamp to [0, 100]
        score = max(0.0, min(100.0, score))
        return round(score, 2), "; ".join(reasons) if reasons else "Neutral entry conditions"

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 4 — Confidence Engine
    # ══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _compute_confidence_engine(
        agreement_level:      float,
        market_quality_score: float,
        entry_quality_score:  float,
        trend_score:          Optional[float],
        momentum_score:       Optional[float],
        volatility_score:     Optional[float],
        risk_score:           float,
        context_multiplier:   float,
        conflict_detected:    bool,
        news_confidence:      Optional[float],
    ) -> float:
        """
        Phase 4: Multi-factor Confidence Engine.

        NOT a simple weighted average. Combines:
          Consensus agreement bonus (0-30 pts) — how much engines agree
          Market quality component (0-25 pts) — is the market tradable?
          Entry quality component  (0-20 pts) — is NOW a good moment?
          Trend strength           (0-10 pts) — how strong is the trend?
          Momentum strength        (0-10 pts) — how strong is momentum?
          Risk headroom            (0-5  pts)  — portfolio capacity

        Then applies:
          × Context multiplier (0.6-1.0) — multi-timeframe alignment
          × Volatility factor  (0.85-1.05) — high vol = uncertainty
          × Conflict penalty   (×0.70)     — engines disagree strongly
        """
        # 1. Consensus agreement bonus: agreement [0.5,1.0] → [0,30]
        consensus_component = max(0.0, (agreement_level - 0.5) * 2.0) * 30.0

        # 2. Market quality: how tradable is the market? → [0,25]
        market_component = (market_quality_score / 100.0) * 25.0

        # 3. Entry quality: is now a good entry moment? → [0,20]
        entry_component = (entry_quality_score / 100.0) * 20.0

        # 4. Trend strength → [0,10]  (default 50 if absent = 5 pts, neutral)
        trend_component = ((trend_score if trend_score is not None else 50.0) / 100.0) * 10.0

        # 5. Momentum strength → [0,10]
        momentum_component = (
            (momentum_score if momentum_score is not None else 50.0) / 100.0
        ) * 10.0

        # 6. Risk headroom → [0,5]
        risk_component = (risk_score / 100.0) * 5.0

        raw_confidence = (
            consensus_component
            + market_component
            + entry_component
            + trend_component
            + momentum_component
            + risk_component
        )  # max = 100

        # Apply multi-timeframe context multiplier
        confidence = raw_confidence * context_multiplier

        # Volatility adjustment
        if volatility_score is not None:
            if volatility_score > 70:
                # High volatility → uncertain market, reduce confidence
                confidence *= 0.88
            elif volatility_score < 30:
                # Low volatility → stable conditions, slight boost
                confidence *= 1.04

        # News confidence boost (small)
        if news_confidence is not None and news_confidence > 70:
            confidence *= 1.02

        # Phase 1: Conflict penalty — strong disagreement destroys confidence
        if conflict_detected:
            confidence *= 0.70

        return round(min(max(confidence, 0.0), 100.0), 2)

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 4b — Calibration Feedback (Phase 7 — Historical Database)
    # ══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _apply_calibration_adjustment(
        raw_confidence: float,
        calibration_summary: "Optional[object]",
        bucket_stats: "list[object]",
        min_bucket_samples: int,
        min_total_evaluated: int,
        correction_fraction: float,
        max_adjustment: float,
    ) -> "tuple[float, str]":
        """
        Phase 4b — Calibration Feedback.

        Reads historical outcome-calibration data (written by
        ConfidenceCalibrationService after every OutcomeLearningService cycle)
        and applies a small, bounded correction to ``raw_confidence``.

        Algorithm
        ---------
        1. Require a global minimum of ``min_total_evaluated`` evaluated outcomes
           before applying any correction (no adjustment if the system is too new).
        2. Find the confidence bucket that contains ``raw_confidence``.
        3. Require ``min_bucket_samples`` in that bucket; fall back to the global
           over/underconfident summary if the bucket is empty.
        4. Compute the signed calibration error for the bucket:
             signed_error = accuracy − avg_confidence
           Positive  → system was UNDERCONFIDENT in this range → boost.
           Negative  → system was OVERCONFIDENT in this range → dampen.
        5. Apply ``correction_fraction`` of that error, capped at ±``max_adjustment``.
        6. Return (adjusted_confidence, human_readable_explanation).

        This is always a graceful no-op: if data is absent or insufficient, the
        original ``raw_confidence`` is returned unchanged.
        """
        # Guard: no data at all
        if calibration_summary is None:
            return raw_confidence, ""

        total_evaluated = getattr(calibration_summary, "total_evaluated", 0) or 0
        if total_evaluated < min_total_evaluated:
            return (
                raw_confidence,
                f"Calibration: only {total_evaluated} outcomes evaluated "
                f"(need ≥{min_total_evaluated}) — no adjustment yet",
            )

        # --- Bucket-level adjustment ----------------------------------------
        relevant_bucket = None
        for b in bucket_stats:
            sample_count = getattr(b, "sample_count", 0) or 0
            if sample_count < min_bucket_samples:
                continue
            bucket_min = getattr(b, "bucket_min", 0.0)
            bucket_max = getattr(b, "bucket_max", 0.0)
            if bucket_max <= 50.0:
                # below-50 catch-all bucket
                if raw_confidence < 50.0:
                    relevant_bucket = b
                    break
            elif bucket_min <= raw_confidence < bucket_max:
                relevant_bucket = b
                break
            elif bucket_max == 100.0 and raw_confidence == 100.0:
                relevant_bucket = b
                break

        if relevant_bucket is not None:
            accuracy        = getattr(relevant_bucket, "accuracy", None)
            avg_confidence  = getattr(relevant_bucket, "avg_confidence", None)
            sample_count    = getattr(relevant_bucket, "sample_count", 0)
            bucket_min      = getattr(relevant_bucket, "bucket_min", 0.0)
            bucket_max      = getattr(relevant_bucket, "bucket_max", 0.0)

            if accuracy is not None and avg_confidence is not None:
                # signed_error > 0 → underconfident → boost
                # signed_error < 0 → overconfident → dampen
                signed_error = accuracy - avg_confidence
                adjustment = signed_error * correction_fraction
                adjustment = max(-max_adjustment, min(max_adjustment, adjustment))

                adjusted = round(max(0.0, min(100.0, raw_confidence + adjustment)), 2)
                direction = (
                    "dampened" if adjustment < -0.05 else
                    "boosted"  if adjustment >  0.05 else
                    "unchanged"
                )
                note = (
                    f"bucket [{bucket_min:.0f}–{bucket_max:.0f}%] "
                    f"accuracy={accuracy:.1f}% vs avg_conf={avg_confidence:.1f}% "
                    f"(n={sample_count}) → {direction} by {abs(adjustment):.1f}pts "
                    f"[{raw_confidence:.1f}→{adjusted:.1f}]"
                )
                return adjusted, note

        # --- Fallback: global summary adjustment ----------------------------
        overconfident_pct   = getattr(calibration_summary, "overconfident_pct",   None)
        underconfident_pct  = getattr(calibration_summary, "underconfident_pct",  None)
        well_calibrated_pct = getattr(calibration_summary, "well_calibrated_pct", None)

        # Only apply a global adjustment when there is a dominant bias
        GLOBAL_BIAS_THRESHOLD = 60.0  # >60% of outcomes in one category
        if overconfident_pct is not None and overconfident_pct > GLOBAL_BIAS_THRESHOLD:
            adjustment = -(raw_confidence * 0.05)  # global 5% dampen
            adjustment = max(-max_adjustment, adjustment)
            adjusted   = round(max(0.0, min(100.0, raw_confidence + adjustment)), 2)
            return (
                adjusted,
                f"Global calibration: {overconfident_pct:.0f}% of outcomes OVERCONFIDENT "
                f"(n={total_evaluated}) → dampened {abs(adjustment):.1f}pts "
                f"[{raw_confidence:.1f}→{adjusted:.1f}]",
            )
        if underconfident_pct is not None and underconfident_pct > GLOBAL_BIAS_THRESHOLD:
            adjustment = raw_confidence * 0.05  # global 5% boost
            adjustment = min(max_adjustment, adjustment)
            adjusted   = round(max(0.0, min(100.0, raw_confidence + adjustment)), 2)
            return (
                adjusted,
                f"Global calibration: {underconfident_pct:.0f}% of outcomes UNDERCONFIDENT "
                f"(n={total_evaluated}) → boosted {abs(adjustment):.1f}pts "
                f"[{raw_confidence:.1f}→{adjusted:.1f}]",
            )

        # Bucket exists but has insufficient samples and no dominant global bias
        if well_calibrated_pct is not None:
            fallback_note = (
                f"Calibration: insufficient bucket samples — no adjustment "
                f"(total evaluated={total_evaluated}, "
                f"well_calibrated={well_calibrated_pct:.0f}%)"
            )
        else:
            fallback_note = (
                f"Calibration: insufficient bucket samples — no adjustment "
                f"(total evaluated={total_evaluated})"
            )
        return raw_confidence, fallback_note

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 7 — Self-Validation
    # ══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _self_validate(
        trend_direction:    Optional[str],
        momentum_direction: Optional[str],
        spread_yes:         Optional[float],
        behaviours:         list[str],
        conflict_detected:  bool,
    ) -> tuple[bool, str]:
        """
        Phase 7: Self-Validation — run conflict checks before emitting a decision.

        Returns (conflict_found: bool, reason: str).

        Checks (in priority order):
          1. Trend vs Momentum direct conflict (UP vs BEARISH or DOWN vs BULLISH)
          2. Spread too wide (> CONFLICT_SPREAD_THRESHOLD)
          3. Low Liquidity behaviour detected
          4. Consensus conflict already flagged by Phase 1
        """
        b_set = set(behaviours)

        # Check 1: Trend vs Momentum conflict
        if trend_direction is not None and momentum_direction is not None:
            trend_up   = trend_direction == "UP"
            trend_down = trend_direction == "DOWN"
            mom_bull   = momentum_direction == "BULLISH"
            mom_bear   = momentum_direction == "BEARISH"
            if trend_up and mom_bear:
                return (
                    True,
                    f"Trend=UP but Momentum=BEARISH — signals conflict. "
                    f"Wait for alignment before entering."
                )
            if trend_down and mom_bull:
                return (
                    True,
                    f"Trend=DOWN but Momentum=BULLISH — signals conflict. "
                    f"Possible reversal or noise. Wait for confirmation."
                )

        # Check 2: Spread too wide
        if spread_yes is not None and spread_yes > CONFLICT_SPREAD_THRESHOLD:
            return (
                True,
                f"Spread={spread_yes:.4f} exceeds maximum {CONFLICT_SPREAD_THRESHOLD:.4f}. "
                f"Entry cost too high — WAIT for spread to tighten."
            )

        # Check 3: Low Liquidity behaviour
        if "Low Liquidity" in b_set:
            return (
                True,
                "Low Liquidity behaviour detected. "
                "Thin market — wide real slippage risk. WAIT for liquidity."
            )

        # Check 4: Phase 1 conflict already detected
        if conflict_detected:
            return (
                True,
                "Engine consensus conflict (>30% weight opposing). "
                "No clear directional edge — WAIT for agreement."
            )

        return False, ""

    # ── Reasoning interpreters ────────────────────────────────────────────────

    @staticmethod
    def _interpret_non_tradable(quality: str, behaviours: list[str]) -> str:
        if quality == "High Risk":
            return "Market is near expiry or structurally risky."
        if quality == "Illiquid":
            return "Wide spread and low participation — AMM-only pricing, no real liquidity."
        if quality == "Avoid":
            return "Liquidity is decreasing and spread is widening — deteriorating conditions."
        return "Market conditions do not meet minimum tradability criteria."

    @staticmethod
    def _interpret_spread(spread_yes: Optional[float], behaviours: list[str]) -> str:
        b_set = set(behaviours)
        if spread_yes is None:
            return "No spread data yet — cannot assess friction"
        if "Healthy Spread" in b_set or spread_yes < 0.02:
            return (
                f"{spread_yes:.4f} → Tight spread. Market is liquid and efficient. "
                "Low friction for entry."
            )
        if "Market becoming more efficient" in b_set:
            return (
                f"{spread_yes:.4f} → Spread narrowing across recent snapshots. "
                "Market improving — GOOD signal."
            )
        if "Wide Spread" in b_set or spread_yes > 0.05:
            return (
                f"{spread_yes:.4f} → Wide spread. High friction. Entry cost elevated. "
                "Proceed with caution."
            )
        return f"{spread_yes:.4f} → Moderate spread. Acceptable conditions."

    @staticmethod
    def _interpret_pressure(behaviours: list[str]) -> tuple[str, str]:
        """Returns (pressure_signal, human_readable_interpretation)."""
        b_set = set(behaviours)
        if "Aggressive Buyers" in b_set or "Buy Pressure" in b_set:
            return (
                "BULLISH",
                "Buy pressure detected. YES buyers becoming aggressive. "
                + ("Sellers weakening." if "Sellers Weakening" in b_set else
                   "Buy pressure detected. YES buyers becoming aggressive."),
            )
        if "Aggressive Sellers" in b_set or "Sell Pressure" in b_set:
            return "BEARISH", "Sell pressure detected. NO buyers becoming aggressive."
        if "Balanced Market" in b_set:
            return "NEUTRAL", "Market is balanced. No directional pressure from bid/ask dynamics."
        if "Passive Market" in b_set:
            return "NEUTRAL", "Passive market. Low volume, no price movement. Thin participation."
        if "Increasing Liquidity" in b_set:
            return "BULLISH_LEAN", "Liquidity increasing — market attracting participants. Mildly bullish signal."
        return "UNKNOWN", "No directional pressure signal from market behaviour."

    @staticmethod
    def _interpret_confirmation(
        engine_name: str,
        direction: Optional[str],
        pressure_signal: str,
        reason: Optional[str],
    ) -> str:
        if direction is None:
            return "no data → no confirmation"
        pressure_bullish = pressure_signal in {"BULLISH", "BULLISH_LEAN"}
        pressure_bearish = pressure_signal == "BEARISH"
        if direction == "BULLISH":
            if pressure_bullish:
                return f"BULLISH → Confirms buy pressure. {reason or ''}"
            if pressure_bearish:
                return f"BULLISH → Conflicts with sell pressure. Mixed signal."
            return f"BULLISH. {reason or ''}"
        if direction == "BEARISH":
            if pressure_bearish:
                return f"BEARISH → Confirms sell pressure. {reason or ''}"
            if pressure_bullish:
                return f"BEARISH → Conflicts with buy pressure. Mixed signal."
            return f"BEARISH. {reason or ''}"
        return f"{direction}. {reason or ''}"

    @staticmethod
    def _interpret_funding(direction: Optional[str], reason: Optional[str]) -> str:
        if direction is None:
            return "no data → neutral, no conflict"
        if direction == "BULLISH":
            return f"BULLISH — funding supports upside. No conflict. {reason or ''}"
        if direction == "BEARISH":
            return f"BEARISH — funding leans short. Watch for conflict with YES buy. {reason or ''}"
        return f"{direction} — {reason or 'neutral'}"

    @staticmethod
    def _interpret_support_engine(
        engine_name: str,
        direction: Optional[str],
        pressure_signal: str,
        reason: Optional[str],
    ) -> str:
        if direction is None:
            return "no data → not counted"
        pressure_bullish = pressure_signal in {"BULLISH", "BULLISH_LEAN"}
        pressure_bearish = pressure_signal == "BEARISH"
        if direction == "BULLISH":
            suffix = (
                "Agrees with buy pressure." if pressure_bullish else
                "Conflicts with sell pressure." if pressure_bearish else ""
            )
            return f"BULLISH → Support. {suffix} {reason or ''}".strip()
        if direction == "BEARISH":
            suffix = (
                "Agrees with sell pressure." if pressure_bearish else
                "Conflicts with buy pressure." if pressure_bullish else ""
            )
            return f"BEARISH → Support. {suffix} {reason or ''}".strip()
        return f"{direction} → Neutral. {reason or ''}"

    @staticmethod
    def _interpret_context(status: Optional[str], multiplier: float) -> str:
        if status == "ALIGNED":
            return (
                f"ALIGNED — all timeframes agree. Confidence multiplier={multiplier:.2f}. "
                "Conviction increased."
            )
        if status == "MIXED":
            return (
                f"MIXED — partial timeframe agreement. Confidence multiplier={multiplier:.2f}. "
                "Some divergence — proceed with reduced conviction."
            )
        if status == "CONFLICT":
            return (
                f"CONFLICT — timeframes disagree. Confidence multiplier={multiplier:.2f}. "
                "Significant divergence — confidence heavily discounted."
            )
        return f"{status} — multiplier={multiplier:.2f}"

    @staticmethod
    def _interpret_risk(risk_score: float, risk_gated: bool, risk_reason: Optional[str]) -> str:
        if risk_gated:
            return f"GATED — portfolio limits reached. {risk_reason or ''}"
        if risk_score >= 80:
            return f"Safe (score={risk_score:.0f}). Portfolio capacity available. {risk_reason or ''}"
        if risk_score >= 60:
            return f"Acceptable (score={risk_score:.0f}). Approaching limits but within bounds. {risk_reason or ''}"
        return f"Elevated concern (score={risk_score:.0f}). Near portfolio limits. {risk_reason or ''}"

    @staticmethod
    def _build_final_reasons(
        decision: str,
        confidence: float,
        behaviours: list[str],
        orderbook,
        funding,
        momentum,
        trend,
        market_context,
        volatility,
        opportunity_direction: Optional[str],
        gate_reason: Optional[str] = None,
    ) -> str:
        """
        Build the human-readable 'Reason' block for the final decision.
        """
        lines: list[str] = []

        if gate_reason:
            lines.append(f"  - {gate_reason}")
            return "\n".join(lines)

        positive_behaviours = [
            b for b in behaviours
            if b in {
                "Increasing Liquidity", "Healthy Spread", "High Participation",
                "Market Stability", "Market becoming more efficient",
                "Buy Pressure", "Aggressive Buyers",
                "Sell Pressure", "Aggressive Sellers",
            }
        ]
        if positive_behaviours:
            lines.append(f"  - {'. '.join(positive_behaviours)}.")

        if opportunity_direction and opportunity_direction != "NEUTRAL":
            lines.append(f"  - Polymarket mispricing detected: {opportunity_direction}.")

        if orderbook and orderbook.direction:
            lines.append(f"  - Orderbook confirms {orderbook.direction.lower()} pressure.")

        if funding and funding.direction:
            if funding.direction == "BULLISH":
                lines.append("  - Funding neutral or bullish — no conflict.")
            elif funding.direction == "BEARISH":
                lines.append("  - Funding bearish — watch for reversal risk.")

        if momentum and momentum.direction:
            lines.append(f"  - Momentum {momentum.direction.lower()}.")

        if trend and trend.direction:
            lines.append(f"  - Trend {trend.direction.lower()}.")

        if market_context and market_context.status:
            if market_context.status == "ALIGNED":
                lines.append("  - Market context aligned — all timeframes agree.")
            elif market_context.status == "CONFLICT":
                lines.append("  - Market context conflicted — timeframes disagree.")

        if volatility and volatility.regime:
            lines.append(f"  - Volatility {volatility.regime.lower()}.")

        lines.append(f"  - Risk acceptable (confidence={confidence:.1f}%).")

        if not lines:
            lines.append("  - Signals collectively insufficient for a directional decision.")

        return "\n".join(lines)

    # ── Save helpers ──────────────────────────────────────────────────────────

    async def _save_wait(
        self,
        session: AsyncSession,
        condition_id: str,
        asset: str,
        timeframe: str,
        risk_score: float,
        risk_gated: bool,
        steps: list[str],
        supporting_engines: list[str],
        *,
        market_quality_score: Optional[float] = None,
        market_quality: Optional[str] = None,
        market_confidence: Optional[float] = None,
        market_risk: Optional[str] = None,
        confidence: float = 0.0,
    ) -> None:
        """Save an early-exit WAIT decision (before reaching Phase 1/3/4)."""
        await repo.create_decision_log(
            session,
            condition_id    = condition_id,
            asset           = asset,
            timeframe       = timeframe,
            decision        = "WAIT",
            confidence      = confidence,
            vote_score      = 0.0,
            consensus_score = None,
            agreement_level = None,
            conflict_detected = None,
            entry_quality_score = None,
            signal_confidence   = None,
            signal_regime       = None,
            momentum_score      = None,
            momentum_direction  = None,
            trend_score         = None,
            trend_direction     = None,
            volatility_score    = None,
            volatility_regime   = None,
            opportunity_score   = None,
            opportunity_direction = None,
            risk_score          = risk_score,
            risk_gated          = risk_gated,
            market_quality_score = market_quality_score,
            market_quality       = market_quality,
            market_confidence    = market_confidence,
            market_risk          = market_risk,
            supporting_engines   = ", ".join(supporting_engines),
            reasons              = "\n".join(steps),
        )

    # ── Read helpers (all SELECT-only) ────────────────────────────────────────

    @staticmethod
    async def _get_market_quality(
        session: AsyncSession, condition_id: str
    ) -> Optional[MarketQualityScore]:
        result = await session.execute(
            select(MarketQualityScore).where(
                MarketQualityScore.condition_id == condition_id
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _get_market_context(
        session: AsyncSession, asset: str
    ) -> Optional[MarketContextScore]:
        result = await session.execute(
            select(MarketContextScore).where(MarketContextScore.asset == asset)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _get_orderbook(
        session: AsyncSession, asset: str
    ) -> Optional[OrderbookScore]:
        result = await session.execute(
            select(OrderbookScore).where(OrderbookScore.asset == asset)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _get_funding(
        session: AsyncSession, asset: str
    ) -> Optional[FundingScore]:
        result = await session.execute(
            select(FundingScore).where(FundingScore.asset == asset)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _get_news(
        session: AsyncSession, asset: str
    ) -> Optional[NewsScore]:
        result = await session.execute(
            select(NewsScore).where(NewsScore.asset == asset)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _get_momentum(
        session: AsyncSession, asset: str, timeframe: str
    ) -> Optional[MomentumScore]:
        result = await session.execute(
            select(MomentumScore).where(
                MomentumScore.asset == asset,
                MomentumScore.timeframe == timeframe,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _get_trend(
        session: AsyncSession, asset: str, timeframe: str
    ) -> Optional[TrendScore]:
        result = await session.execute(
            select(TrendScore).where(
                TrendScore.asset == asset,
                TrendScore.timeframe == timeframe,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _get_volatility(
        session: AsyncSession, asset: str, timeframe: str
    ) -> Optional[VolatilityScore]:
        result = await session.execute(
            select(VolatilityScore).where(
                VolatilityScore.asset == asset,
                VolatilityScore.timeframe == timeframe,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _get_opportunity(
        session: AsyncSession, condition_id: str
    ) -> Optional[Opportunity]:
        result = await session.execute(
            select(Opportunity).where(Opportunity.condition_id == condition_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _compute_risk_context(session: AsyncSession) -> tuple[float, bool, str]:
        """
        Read-only snapshot of current portfolio risk conditions.
        Returns (risk_score 0-100, risk_gated, reason).
        """
        open_positions_result = await session.execute(
            select(func.count()).select_from(Position).where(Position.status == "OPEN")
        )
        open_positions_count = open_positions_result.scalar_one() or 0

        from sqlalchemy import Date, cast
        today = datetime.now(timezone.utc).date()
        daily_trades_result = await session.execute(
            select(func.count(Order.id)).where(cast(Order.created_at, Date) == today)
        )
        daily_trades = daily_trades_result.scalar_one() or 0

        daily_loss_result = await session.execute(
            select(
                func.coalesce(func.sum(Position.unrealized_pnl), 0.0)
            ).where(Position.status == "OPEN", Position.unrealized_pnl.is_not(None))
        )
        daily_loss = float(daily_loss_result.scalar_one() or 0.0)

        # Phase 12L: no fixed position count cap; use portfolio exposure limit as proxy.
        # Approximate fraction by comparing open_exposure to PORTFOLIO_MAX_EXPOSURE_USDC.
        positions_frac = min(open_positions_count / max(500, 1), 1.0)
        trades_frac    = min(daily_trades / max(settings.MAX_DAILY_TRADES, 1), 1.0)
        loss_frac      = (
            min(abs(daily_loss) / max(abs(settings.MAX_DAILY_LOSS), 1e-6), 1.0)
            if daily_loss < 0 else 0.0
        )

        consumed   = max(positions_frac, trades_frac, loss_frac)
        risk_score = round((1.0 - consumed) * 100.0, 2)

        gated = (
            daily_loss <= settings.MAX_DAILY_LOSS
            or daily_trades >= settings.MAX_DAILY_TRADES
            or risk_score < RISK_MIN_SCORE
        )

        reason = (
            f"open_positions={open_positions_count} "
            f"daily_trades={daily_trades}/{settings.MAX_DAILY_TRADES} "
            f"daily_pnl={daily_loss:.2f} (limit {settings.MAX_DAILY_LOSS})"
        )

        return risk_score, gated, reason
