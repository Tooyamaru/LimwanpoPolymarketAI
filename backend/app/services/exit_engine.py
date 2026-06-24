"""
Exit Decision Engine — Layer between Opportunity and Strategy.

Evaluates all OPEN positions and emits CLOSE_POSITION TradeDecision rows
when an exit trigger fires.

Exit triggers (evaluated in priority order; first match wins):
  1. EXPIRY_EXIT        — hard: minutes_to_expiry < EXIT_FORCE_EXPIRY_MINUTES
                          soft: minutes_to_expiry < EXIT_EXPIRY_BUFFER_MINUTES AND bid PnL > 0
  2. STOP_LOSS          — exit_pnl_at_bid <= EXIT_STOP_LOSS_USDC
  3. PROFIT_TARGET      — exit_pnl_at_bid >= EXIT_PROFIT_TARGET_USDC
  4. SIGNAL_INVALIDATION — signal_count_1h == 0 AND position age > EXIT_SIGNAL_TIMEOUT_MINUTES

Exit price (executable only, never mid):
  LONG_YES → yes_bid
  LONG_NO  → 1 - yes_ask

Duplicate protection:
  Skips if a PENDING or RISK_APPROVED CLOSE_POSITION decision already
  exists for the same target_position_id.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.core.logging import get_logger
from app.models.opportunity import Opportunity
from app.models.trade_decision import TradeDecision
from app.repositories import position_repository as pos_repo

logger = get_logger(__name__)


def _position_age_minutes(opened_at: datetime, now: datetime) -> float:
    """Return position age in minutes. Handles tz-naive datetimes defensively."""
    if opened_at.tzinfo is None:
        opened_at = opened_at.replace(tzinfo=timezone.utc)
    return (now - opened_at).total_seconds() / 60.0


def _get_exit_price(side: str, opp: Optional[Opportunity]) -> Optional[float]:
    """
    Return the executable (bid-side) exit price.

    LONG_YES → yes_bid        (sell YES at the best bid)
    LONG_NO  → 1 - yes_ask   (sell NO at implied bid)

    Returns None when the required price is unavailable; the position is
    skipped for this cycle and retried on the next.
    """
    if opp is None:
        return None
    if side == "LONG_YES":
        return opp.yes_bid
    if side == "LONG_NO":
        if opp.yes_ask is None:
            return None
        return round(1.0 - opp.yes_ask, 6)
    return None


def _evaluate_triggers(
    exit_pnl: float,
    minutes_to_expiry: Optional[float],
    signal_count_1h: int,
    position_age_minutes: float,
) -> Optional[str]:
    """
    Evaluate exit triggers in priority order.

    Returns the exit_reason string for the first trigger that fires,
    or None if no trigger fires (position stays open).
    """
    # ── Priority 1: EXPIRY_EXIT ──────────────────────────────────────────────
    if minutes_to_expiry is not None:
        # Hard exit — always close regardless of PnL
        if minutes_to_expiry < settings.EXIT_FORCE_EXPIRY_MINUTES:
            return "EXPIRY_EXIT"
        # Soft exit — close only if already profitable
        if minutes_to_expiry < settings.EXIT_EXPIRY_BUFFER_MINUTES and exit_pnl > 0:
            return "EXPIRY_EXIT"

    # ── Priority 2: STOP_LOSS ────────────────────────────────────────────────
    if exit_pnl <= settings.EXIT_STOP_LOSS_USDC:
        return "STOP_LOSS"

    # ── Priority 3: PROFIT_TARGET ────────────────────────────────────────────
    if exit_pnl >= settings.EXIT_PROFIT_TARGET_USDC:
        return "PROFIT_TARGET"

    # ── Priority 4: SIGNAL_INVALIDATION ─────────────────────────────────────
    if (
        signal_count_1h == 0
        and position_age_minutes > settings.EXIT_SIGNAL_TIMEOUT_MINUTES
    ):
        return "SIGNAL_INVALIDATION"

    return None


class ExitEngine:
    """
    Evaluates all OPEN positions and emits CLOSE_POSITION TradeDecision rows.

    Usage (from FastAPI lifespan or background loop)::

        engine = ExitEngine()
        result = await engine.run(session)
    """

    async def run(self, session: AsyncSession) -> dict:
        """
        Execute one full exit-evaluation cycle.

        Steps:
          1. Load all OPEN positions.
          2. Bulk-load Opportunity rows (one query, no N+1).
          3. Load set of position IDs already covered by a pending exit decision.
          4. For each position: compute exit price → evaluate triggers → emit decision.
          5. Commit.

        Returns a dict with cycle summary statistics.
        """
        started = datetime.now(timezone.utc)

        open_positions = await pos_repo.get_open_positions(session)
        if not open_positions:
            logger.debug("Exit engine: no open positions to evaluate")
            return {
                "evaluated": 0,
                "decisions_created": 0,
                "skipped": 0,
                "errors": 0,
                "duration_ms": 0,
            }

        # ── Build condition_id → Opportunity map (single query) ───────────────
        condition_ids = list({p.condition_id for p in open_positions})
        opp_rows = await session.execute(
            select(Opportunity).where(Opportunity.condition_id.in_(condition_ids))
        )
        opp_map: dict[str, Opportunity] = {
            o.condition_id: o for o in opp_rows.scalars().all()
        }

        # ── Fetch position IDs that already have a pending exit decision ───────
        position_ids = [p.id for p in open_positions]
        pending_exit_ids = await self._get_pending_exit_position_ids(session, position_ids)

        now = datetime.now(timezone.utc)
        decisions_created = 0
        skipped = 0
        errors = 0

        for pos in open_positions:
            try:
                # ── Duplicate protection ──────────────────────────────────────
                if pos.id in pending_exit_ids:
                    skipped += 1
                    logger.debug(
                        "Exit engine: pending close decision exists, skipping",
                        position_id=pos.id,
                        condition_id=pos.condition_id[:12],
                    )
                    continue

                opp = opp_map.get(pos.condition_id)

                # ── Compute executable exit price ─────────────────────────────
                exit_price = _get_exit_price(pos.side, opp)
                if exit_price is None:
                    logger.debug(
                        "Exit engine: no executable price available, skipping",
                        position_id=pos.id,
                        side=pos.side,
                        condition_id=pos.condition_id[:12],
                    )
                    skipped += 1
                    continue

                exit_pnl = round(pos.quantity * (exit_price - pos.entry_price), 6)
                age_minutes = _position_age_minutes(pos.opened_at, now)
                minutes_to_expiry = opp.minutes_to_expiry if opp is not None else None
                signal_count_1h = opp.signal_count_1h if opp is not None else 0

                # ── Evaluate triggers in priority order ───────────────────────
                exit_reason = _evaluate_triggers(
                    exit_pnl=exit_pnl,
                    minutes_to_expiry=minutes_to_expiry,
                    signal_count_1h=signal_count_1h,
                    position_age_minutes=age_minutes,
                )

                if exit_reason is None:
                    continue

                # ── Emit CLOSE_POSITION TradeDecision ─────────────────────────
                decision = TradeDecision(
                    condition_id=pos.condition_id,
                    asset=pos.asset,
                    timeframe=pos.timeframe,
                    decision="CLOSE_POSITION",
                    status="PENDING",
                    opportunity_score=opp.opportunity_score if opp is not None else 0.0,
                    direction=opp.direction if opp is not None else "NEUTRAL",
                    yes_mid=opp.yes_mid if opp is not None else None,
                    yes_bid=opp.yes_bid if opp is not None else None,
                    yes_ask=opp.yes_ask if opp is not None else None,
                    spread_yes=opp.spread_yes if opp is not None else None,
                    skip_reason=None,
                    target_position_id=pos.id,
                    exit_reason=exit_reason,
                )
                session.add(decision)
                decisions_created += 1

                logger.info(
                    "Exit decision created",
                    position_id=pos.id,
                    condition_id=pos.condition_id[:12],
                    asset=pos.asset,
                    timeframe=pos.timeframe,
                    side=pos.side,
                    exit_reason=exit_reason,
                    exit_pnl=exit_pnl,
                    exit_price=exit_price,
                    entry_price=pos.entry_price,
                    position_age_minutes=round(age_minutes, 1),
                )

            except Exception as exc:
                logger.error(
                    "Exit engine error",
                    position_id=pos.id,
                    condition_id=pos.condition_id[:12],
                    error=str(exc),
                )
                errors += 1

        await session.commit()

        elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        logger.info(
            "Exit engine cycle complete",
            evaluated=len(open_positions),
            decisions_created=decisions_created,
            skipped=skipped,
            errors=errors,
            duration_ms=elapsed_ms,
        )
        return {
            "evaluated": len(open_positions),
            "decisions_created": decisions_created,
            "skipped": skipped,
            "errors": errors,
            "duration_ms": elapsed_ms,
        }

    @staticmethod
    async def _get_pending_exit_position_ids(
        session: AsyncSession,
        position_ids: list[int],
    ) -> set[int]:
        """
        Return the set of position IDs that already have a PENDING or
        RISK_APPROVED CLOSE_POSITION decision.

        Single query — no N+1.
        """
        if not position_ids:
            return set()
        result = await session.execute(
            select(TradeDecision.target_position_id).where(
                TradeDecision.decision == "CLOSE_POSITION",
                TradeDecision.status.in_(["PENDING", "RISK_APPROVED"]),
                TradeDecision.target_position_id.in_(position_ids),
            )
        )
        return {row[0] for row in result.all()}
