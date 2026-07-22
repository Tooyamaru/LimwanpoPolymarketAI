"""
OutcomeLearningService — Priority 1: Outcome Learning + Priority 5: Feedback Loop.

Phase 9D: Direct Polymarket Resolution as primary correctness source.

Correctness determination priority:
  1. DIRECT_POLYMARKET_RESOLUTION (primary):
       If Gamma API confirms market is closed and outcomePrices clearly show
       winner (one side >= 0.99), use that as ground truth.
         BUY_YES correct  ↔  winning_side == "YES"
         BUY_NO  correct  ↔  winning_side == "NO"
       realized_pnl is stored as economic_result only — not used for correctness.
       outcome_source = "DIRECT_POLYMARKET_RESOLUTION"

  2. REALIZED_PNL_PROXY (fallback):
       If direct resolution is NOT_AVAILABLE (market not yet resolved, no data,
       or voided), fall back to position PnL > 0 as proxy.
       outcome_source = "REALIZED_PNL_PROXY"

  3. NOT_AVAILABLE:
       No position taken and no direct resolution.
       outcome_source = "NOT_AVAILABLE"
       correct = None

No Machine Learning. Pure statistics.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.decision_log import DecisionLog
from app.models.market_universe import MarketUniverse
from app.models.position import Position
from app.repositories import outcome_learning_repository as ol_repo
from app.services.confidence_calibration_service import ConfidenceCalibrationService
from app.services.engine_performance_service import EnginePerformanceService
from app.services.gamma_series_client import (
    GammaSeriesClient,
    OUTCOME_SOURCE_DIRECT,
    OUTCOME_SOURCE_PROXY,
    OUTCOME_SOURCE_NONE,
    MarketResolutionResult,
)
from app.services.market_type_performance_service import MarketTypePerformanceService

logger = get_logger(__name__)

# Sentinel returned by _evaluate_market when official resolution is not yet
# available.  Signals run() to count the market as resolution_pending and
# perform no write or idempotency mark — the worker will retry next cycle.
_RESOLUTION_PENDING = object()

# Confidence thresholds for calibration evaluation
CONFIDENCE_HIGH = 65.0
CONFIDENCE_LOW  = 35.0

_perf_service = EnginePerformanceService()
_calibration_service = ConfidenceCalibrationService()
_market_type_perf_service = MarketTypePerformanceService()


def _derive_market_type(series_slug: Optional[str]) -> str:
    """Priority 1 — classify market_type from Gamma series_slug."""
    if series_slug and "up-or-down" in series_slug.lower():
        return "UP_DOWN"
    return "OTHER"


def _compute_ai_score(
    confidence: Optional[float],
    consensus_score: Optional[float],
    entry_quality_score: Optional[float],
) -> Optional[float]:
    """
    Priority 1 — composite AI score (0-100) blending the AI's confidence,
    the multi-engine consensus strength, and the entry quality filter score
    at decision time.
    """
    if confidence is None:
        return None
    consensus = consensus_score if consensus_score is not None else 50.0
    entry_q = entry_quality_score if entry_quality_score is not None else 50.0
    score = confidence * 0.5 + consensus * 0.3 + entry_q * 0.2
    return round(score, 2)


class OutcomeLearningService:
    """
    Priority 1 — Outcome Learning + Priority 5 — Paper Trading Feedback Loop.

    Phase 9D: Direct Polymarket Resolution is the primary correctness source.
    REALIZED_PNL_PROXY is only used when direct resolution is NOT_AVAILABLE.

    Usage::

        svc = OutcomeLearningService()
        result = await svc.run(session)
    """

    async def run(self, session: AsyncSession) -> dict:
        started = datetime.now(timezone.utc)

        # Find all expired markets not yet fully evaluated
        now = datetime.now(timezone.utc)

        # Checkpoint 10: eligibility is determined solely by prediction_window_end.
        # end_time is NOT used.  Markets whose prediction_window_end is NULL are
        # excluded from the SQL result; any that slip through the mock boundary
        # in tests are caught by the defensive check inside the loop.
        expired_markets_result = await session.execute(
            select(MarketUniverse).where(
                MarketUniverse.prediction_window_end <= now,
                MarketUniverse.status.in_(["active", "expired"]),
            )
        )
        expired_markets = list(expired_markets_result.scalars().all())

        evaluated          = 0
        skipped            = 0
        resolution_pending = 0
        errors             = 0
        direct_resolution_count = 0

        async with GammaSeriesClient() as gamma_client:
            for market in expired_markets:
                try:
                    # Defensive guard — SQL WHERE excludes NULL pw_end, but protect
                    # against any edge case (e.g. test injection or metadata race).
                    if market.prediction_window_end is None:
                        logger.warning(
                            "INVALID_PREDICTION_WINDOW: missing prediction_window_end, skipping",
                            condition_id=market.condition_id,
                            asset=market.asset,
                        )
                        skipped += 1
                        continue
                    if market.prediction_window_end > now:
                        # Not yet eligible; SQL should have excluded this market.
                        skipped += 1
                        continue

                    already = await ol_repo.already_evaluated(session, market.condition_id)
                    if already:
                        skipped += 1
                        continue

                    outcome = await self._evaluate_market(session, market, gamma_client)
                    if outcome is _RESOLUTION_PENDING:
                        # Official resolution not yet available — no write, retry next cycle.
                        resolution_pending += 1
                    elif outcome is not None:
                        evaluated += 1
                        direct_resolution_count += 1  # all learned outcomes are DIRECT
                except Exception as exc:
                    logger.error(
                        "Outcome learning error",
                        condition_id=market.condition_id,
                        asset=market.asset,
                        error=str(exc),
                    )
                    errors += 1

        if evaluated > 0:
            # Refresh per-engine performance stats after batch evaluation
            try:
                await _perf_service.recompute_from_all_outcomes(session)
            except Exception as exc:
                logger.error("Engine performance recompute failed", error=str(exc))

            # Priority 3 & 6: confidence calibration + confidence-vs-performance buckets
            try:
                await _calibration_service.recompute(session)
            except Exception as exc:
                logger.error("Confidence calibration recompute failed", error=str(exc))

            # Priority 5: market type performance
            try:
                await _market_type_perf_service.recompute(session)
            except Exception as exc:
                logger.error("Market type performance recompute failed", error=str(exc))

        await session.commit()

        elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        logger.info(
            "Outcome learning cycle complete",
            expired_markets=len(expired_markets),
            evaluated=evaluated,
            direct_resolution=direct_resolution_count,
            resolution_pending=resolution_pending,
            skipped=skipped,
            errors=errors,
            duration_ms=elapsed_ms,
        )
        return {
            "expired_markets": len(expired_markets),
            "evaluated": evaluated,
            "direct_resolution": direct_resolution_count,
            "resolution_pending": resolution_pending,
            "skipped": skipped,
            "errors": errors,
            "duration_ms": elapsed_ms,
        }

    async def _evaluate_market(
        self,
        session: AsyncSession,
        market: MarketUniverse,
        gamma_client: GammaSeriesClient,
    ) -> Optional[object]:
        condition_id = market.condition_id
        asset        = market.asset
        timeframe    = getattr(market, "timeframe", "unknown")

        # 1. Get the last AI decision_log for this market AT OR BEFORE prediction_window_end.
        #    Using prediction_window_end (not end_time) prevents look-ahead errors for
        #    5M markets whose contract end_time may be days later.
        dl_result = await session.execute(
            select(DecisionLog)
            .where(
                DecisionLog.condition_id == condition_id,
                DecisionLog.created_at <= market.prediction_window_end,
            )
            .order_by(desc(DecisionLog.created_at))
            .limit(1)
        )
        decision_log: Optional[DecisionLog] = dl_result.scalar_one_or_none()

        # If no decision was ever made for this market before it expired, skip
        if decision_log is None:
            return None

        prediction = decision_log.decision  # BUY_YES | BUY_NO | WAIT

        # 1b. Optional binding validation — only applied when the decision log carries
        #     binding fields (e.g. from TradeDecision-linked records). Standard
        #     DecisionLog rows do not carry these fields, so getattr returns None and
        #     validation is skipped.  Window-A decision must not be learned against
        #     Window-B market.
        dl_event_slug = getattr(decision_log, "decision_event_slug", None)
        if dl_event_slug is not None and dl_event_slug != market.event_slug:
            logger.warning(
                "Decision event_slug mismatch — skipping outcome learning",
                condition_id=condition_id[:16],
                dl_event_slug=dl_event_slug,
                market_event_slug=market.event_slug,
            )
            return None

        dl_pw_start = getattr(decision_log, "decision_prediction_window_start", None)
        if dl_pw_start is not None and dl_pw_start != market.prediction_window_start:
            logger.warning(
                "Decision prediction_window_start mismatch — skipping outcome learning",
                condition_id=condition_id[:16],
            )
            return None

        dl_pw_end = getattr(decision_log, "decision_prediction_window_end", None)
        if dl_pw_end is not None and dl_pw_end != market.prediction_window_end:
            logger.warning(
                "Decision prediction_window_end mismatch — skipping outcome learning",
                condition_id=condition_id[:16],
            )
            return None

        # 2. Find any CLOSED position for this market.
        #    Position PnL is stored as trading performance data only — it is
        #    never used to determine correctness or winning_side.
        pos_result = await session.execute(
            select(Position)
            .where(
                Position.condition_id == condition_id,
                Position.status == "CLOSED",
            )
            .order_by(desc(Position.id))
            .limit(1)
        )
        position: Optional[Position] = pos_result.scalar_one_or_none()

        actual_pnl:  Optional[float] = position.realized_pnl if position is not None else None
        position_id: Optional[int]   = position.id           if position is not None else None

        # 3. Poll official Polymarket/Gamma resolution — ONLY source of correctness.
        yes_token_id = getattr(market, "yes_token_id", None)
        no_token_id  = getattr(market, "no_token_id", None)

        resolution: MarketResolutionResult = await gamma_client.fetch_market_resolution(
            condition_id=condition_id,
            yes_token_id=yes_token_id,
            no_token_id=no_token_id,
        )

        # 4. Fail-closed gate — only proceed when official resolution is confirmed.
        #    No PnL proxy, no GAP inference, no Chainlink, no CLOB midpoint.
        if resolution.outcome_source != OUTCOME_SOURCE_DIRECT:
            logger.info(
                "Official resolution pending — no learning record created, will retry",
                condition_id=condition_id[:16],
                asset=asset,
                resolution_note=resolution.resolution_note,
            )
            return _RESOLUTION_PENDING

        winning_side: Optional[str] = resolution.winning_side
        if winning_side not in ("YES", "NO"):
            logger.warning(
                "OFFICIAL_OUTCOME_INVALID: winning_side not YES/NO — skipping learning",
                condition_id=condition_id[:16],
                asset=asset,
                winning_side=winning_side,
            )
            return _RESOLUTION_PENDING

        # 5. Determine correctness from official winning_side only.
        winning_token_id: Optional[str] = resolution.winning_token_id
        outcome_source: str             = OUTCOME_SOURCE_DIRECT
        correct: Optional[bool]

        if prediction == "BUY_YES":
            correct      = (winning_side == "YES")
            outcome_type = "POSITION" if position is not None else "NO_POSITION"
        elif prediction == "BUY_NO":
            correct      = (winning_side == "NO")
            outcome_type = "POSITION" if position is not None else "NO_POSITION"
        else:
            # WAIT — direction undefined; correctness cannot be determined from side alone
            correct      = None
            outcome_type = "WAIT_UNKNOWN"

        logger.info(
            "Direct resolution used for correctness",
            condition_id=condition_id[:16],
            asset=asset,
            prediction=prediction,
            winning_side=winning_side,
            correct=correct,
        )

        # 5. Priority 5: Feedback Loop — evaluate quality metrics
        confidence_calibration  = self._evaluate_confidence(decision_log.confidence, correct)
        entry_quality_eval      = self._evaluate_entry_quality(decision_log.entry_quality_score, correct)
        consensus_eval          = self._evaluate_consensus(decision_log.conflict_detected, correct)
        feedback_summary        = self._build_feedback_summary(
            prediction, correct, decision_log, confidence_calibration,
            entry_quality_eval, consensus_eval, actual_pnl, outcome_source,
        )

        # Priority 1: market-level learning fields
        market_title = market.question
        market_type  = _derive_market_type(market.series_slug)
        entry_timestamp = position.opened_at if position is not None else None
        close_timestamp = (
            position.closed_at if position is not None and position.closed_at is not None
            else market.prediction_window_end
        )
        ai_score = _compute_ai_score(
            decision_log.confidence,
            decision_log.consensus_score,
            decision_log.entry_quality_score,
        )

        # 6. Save to outcome_learnings
        row = await ol_repo.upsert_outcome(
            session,
            condition_id            = condition_id,
            asset                   = asset,
            timeframe               = timeframe,
            prediction              = prediction,
            outcome_type            = outcome_type,
            correct                 = correct,
            actual_pnl              = actual_pnl,
            decision_log_id         = decision_log.id,
            confidence              = decision_log.confidence,
            consensus_score         = decision_log.consensus_score,
            agreement_level         = decision_log.agreement_level,
            conflict_detected       = decision_log.conflict_detected,
            entry_quality_score     = decision_log.entry_quality_score,
            market_quality          = decision_log.market_quality,
            market_quality_score    = decision_log.market_quality_score,
            vote_score              = decision_log.vote_score,
            opportunity_direction   = decision_log.opportunity_direction,
            orderbook_direction     = decision_log.orderbook_direction,
            momentum_direction      = decision_log.momentum_direction,
            trend_direction         = decision_log.trend_direction,
            funding_direction       = decision_log.funding_direction,
            confidence_calibration  = confidence_calibration,
            entry_quality_evaluation= entry_quality_eval,
            consensus_evaluation    = consensus_eval,
            feedback_summary        = feedback_summary,
            position_id             = position_id,
            market_title            = market_title,
            market_type             = market_type,
            entry_timestamp         = entry_timestamp,
            close_timestamp         = close_timestamp,
            ai_score                = ai_score,
            # Phase 9D fields
            outcome_source          = outcome_source,
            winning_side            = winning_side,
            winning_token_id        = winning_token_id,
            final_yes_price         = resolution.final_yes_price,
            final_no_price          = resolution.final_no_price,
            resolution_note         = resolution.resolution_note,
        )

        logger.info(
            "Outcome learned",
            condition_id=condition_id[:12],
            asset=asset,
            prediction=prediction,
            correct=correct,
            outcome_type=outcome_type,
            outcome_source=outcome_source,
            actual_pnl=actual_pnl,
            calibration=confidence_calibration,
        )
        return row

    # ── Feedback Loop evaluators (Priority 5) ────────────────────────────────

    @staticmethod
    def _evaluate_confidence(
        confidence: Optional[float], correct: Optional[bool]
    ) -> str:
        """Was the AI's confidence level correctly calibrated?"""
        if confidence is None or correct is None:
            return "UNKNOWN"
        if confidence >= CONFIDENCE_HIGH and correct:
            return "WELL_CALIBRATED"
        if confidence >= CONFIDENCE_HIGH and not correct:
            return "OVERCONFIDENT"
        if confidence < CONFIDENCE_LOW and correct:
            return "UNDERCONFIDENT"
        if confidence < CONFIDENCE_LOW and not correct:
            return "WELL_CALIBRATED"  # Low confidence on a loss = well calibrated
        # Mid-range confidence
        return "WELL_CALIBRATED"

    @staticmethod
    def _evaluate_entry_quality(
        entry_quality_score: Optional[float], correct: Optional[bool]
    ) -> str:
        """Did entry quality scoring correctly predict a good/bad trade?"""
        if entry_quality_score is None or correct is None:
            return "UNKNOWN"
        high_entry = entry_quality_score >= 65.0
        if high_entry and correct:
            return "GOOD_FILTER"      # High quality + correct = filter worked
        if high_entry and not correct:
            return "FALSE_POSITIVE"   # High quality score but trade lost
        if not high_entry and not correct:
            return "GOOD_FILTER"      # Low quality + loss = correctly avoided
        return "MISSED"               # Low quality score but trade won

    @staticmethod
    def _evaluate_consensus(
        conflict_detected: Optional[bool], correct: Optional[bool]
    ) -> str:
        """Was the consensus engine's conflict flag meaningful?"""
        if conflict_detected is None or correct is None:
            return "UNKNOWN"
        if not conflict_detected and correct:
            return "RELIABLE"              # No conflict + correct = good consensus
        if conflict_detected and not correct:
            return "CONFLICTED_AND_WRONG"  # Conflict detected + wrong = consensus warned correctly
        if conflict_detected and correct:
            return "CONFLICTED_AND_LUCKY"  # Conflict detected but still correct = lucky
        return "RELIABLE"                  # No conflict + wrong (consensus missed)

    @staticmethod
    def _build_feedback_summary(
        prediction: str,
        correct: Optional[bool],
        dl: DecisionLog,
        calibration: str,
        entry_eval: str,
        consensus_eval: str,
        actual_pnl: Optional[float],
        outcome_source: str = OUTCOME_SOURCE_PROXY,
    ) -> str:
        lines = []

        if correct is True:
            lines.append(f"✓ Correct prediction ({prediction}). PnL={actual_pnl:.4f}." if actual_pnl else f"✓ Correct prediction ({prediction}).")
        elif correct is False:
            lines.append(f"✗ Wrong prediction ({prediction}). PnL={actual_pnl:.4f}." if actual_pnl else f"✗ Wrong prediction ({prediction}).")
        else:
            lines.append(f"? Outcome unknown ({prediction}). No position taken.")

        lines.append(f"Source: {outcome_source}.")

        lines.append(
            f"Confidence: {dl.confidence:.1f}% → {calibration}."
            if dl.confidence else "Confidence: N/A."
        )
        lines.append(
            f"Entry quality: {dl.entry_quality_score:.1f} → {entry_eval}."
            if dl.entry_quality_score else "Entry quality: N/A."
        )
        lines.append(
            f"Consensus: conflict={dl.conflict_detected} → {consensus_eval}."
        )

        return " ".join(lines)
