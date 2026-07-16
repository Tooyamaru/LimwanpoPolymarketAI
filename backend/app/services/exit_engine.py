"""
Exit Decision Engine — Layer between Opportunity and Strategy.

Evaluates all OPEN positions and emits CLOSE_POSITION TradeDecision rows
when an exit trigger fires.

Exit triggers (evaluated in priority order; first match wins):
  1. EXPIRY_EXIT         — hard: minutes_to_expiry < EXIT_FORCE_EXPIRY_MINUTES
                           soft: minutes_to_expiry < EXIT_EXPIRY_BUFFER_MINUTES AND bid PnL > 0
  2. STOP_LOSS           — Dynamic: exit_pnl ≤ -(position_value × spread × multiplier)
                           Falls back to EXIT_STOP_LOSS_USDC when spread unavailable.
  3. FAST_PROFIT_EXIT    — net_pnl >= MIN_NET_PROFIT_AFTER_COST_USDC AND
                           (gross_pnl >= FAST_PROFIT_TARGET_USDC OR
                            % profit >= FAST_PROFIT_TARGET_PERCENT) AND
                           hold time >= MIN_POSITION_HOLD_SECONDS AND
                           spread <= MAX_ACCEPTABLE_EXIT_SPREAD.
                           Only fires when FAST_PROFIT_EXIT_ENABLED=True.
  4. PROFIT_TARGET       — exit_pnl_at_bid >= EXIT_PROFIT_TARGET_USDC
  5. TRAILING_STOP       — exit_pnl dropped below (peak_pnl − position_value × distance)
                           Only fires when TRAILING_STOP_ENABLED and peak_pnl > 0.
  6. SIGNAL_INVALIDATION — signal_count_1h == 0 AND position age > EXIT_SIGNAL_TIMEOUT_MINUTES

Exit price (executable only, never mid):
  LONG_YES → yes_bid
  LONG_NO  → 1 - yes_ask

Stale price protection:
  When the required bid/ask price is None, position is skipped and retried.
  Returns PRICE_NOT_AVAILABLE / STALE_ORDERBOOK via skip (no decision emitted).

Duplicate protection:
  Skips if a PENDING or RISK_APPROVED CLOSE_POSITION decision already
  exists for the same target_position_id.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.core.logging import get_logger
from app.models.market_universe import MarketUniverse
from app.models.opportunity import Opportunity
from app.models.outcome_learning import OutcomeLearning
from app.models.signal import Signal
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


def _compute_dynamic_stop_loss(
    position_size_usdc: float,
    spread_yes: float,
    multiplier: float,
) -> float:
    """
    Compute the dynamic stop-loss threshold as a negative USDC value.

    Formula:
        SpreadCost = position_size_usdc × spread_yes
        StopLoss   = SpreadCost × multiplier
        Threshold  = -StopLoss

    Proportional to spread cost, so it stays rational regardless of position
    size and prevents stop-outs from normal market noise.
    """
    return round(-(position_size_usdc * spread_yes * multiplier), 6)


def _evaluate_triggers(
    exit_pnl: float,
    minutes_to_expiry: Optional[float],
    signal_count_1h: int,
    position_age_minutes: float,
    position_size_usdc: Optional[float] = None,
    spread_yes: Optional[float] = None,
    peak_pnl_usdc: Optional[float] = None,
    max_hold_minutes: Optional[float] = None,
) -> Optional[str]:
    """
    Evaluate exit triggers in priority order.

    Returns the exit_reason string for the first trigger that fires,
    or None if no trigger fires (position stays open).

    Parameters
    ----------
    exit_pnl : float
        Current PnL in USDC computed at bid-side exit price.
    minutes_to_expiry : float | None
        Minutes remaining until market close; None if unknown.
    signal_count_1h : int
        Direct count of signals for this market in the last hour (from the
        signals table, NOT from the stale opportunity row).
    position_age_minutes : float
        How long the position has been open (minutes).
    position_size_usdc : float | None
        Notional USDC value (quantity × entry_price). Required for dynamic
        stop loss and trailing stop calculations.
    spread_yes : float | None
        Current YES-token bid–ask spread. Required for dynamic stop loss.
    peak_pnl_usdc : float | None
        Highest unrealized PnL recorded while position is OPEN. Required
        for trailing stop.
    max_hold_minutes : float | None
        Override for the MAX_HOLD threshold. Defaults to EXIT_MAX_HOLD_MINUTES
        from settings. Exposed for tests.
    """

    # ── Priority 1: EXPIRY_EXIT ──────────────────────────────────────────────
    if minutes_to_expiry is not None:
        # Hard exit — always close regardless of PnL
        if minutes_to_expiry < settings.EXIT_FORCE_EXPIRY_MINUTES:
            return "EXPIRY_EXIT"
        # Soft exit — close only if already profitable
        if minutes_to_expiry < settings.EXIT_EXPIRY_BUFFER_MINUTES and exit_pnl > 0:
            return "EXPIRY_EXIT"

    # ── Priority 2: STOP_LOSS (dynamic preferred, static as absolute floor) ──
    # Formula: stop_threshold = max(EXIT_STOP_LOSS_USDC, -(pos_size × spread × mult))
    # • When dynamic is tighter (less negative): dynamic wins → stops out sooner.
    # • When dynamic is looser (more negative) than the static floor: floor wins →
    #   prevents wide-spread / large positions from sustaining catastrophic losses.
    if position_size_usdc is not None and spread_yes is not None:
        dynamic_threshold = _compute_dynamic_stop_loss(
            position_size_usdc, spread_yes, settings.EXIT_STOP_LOSS_MULTIPLIER
        )
        stop_threshold = max(settings.EXIT_STOP_LOSS_USDC, dynamic_threshold)
        if exit_pnl <= stop_threshold:
            return "STOP_LOSS"
    else:
        if exit_pnl <= settings.EXIT_STOP_LOSS_USDC:
            return "STOP_LOSS"

    # ── Priority 3: FAST_PROFIT_EXIT ────────────────────────────────────────
    # Lower threshold than PROFIT_TARGET — exits quickly when a small net gain
    # is achievable at an executable bid price after costs.
    # Requires: hold time met, spread acceptable, net PnL positive, gross target.
    if settings.FAST_PROFIT_EXIT_ENABLED:
        hold_seconds = position_age_minutes * 60.0
        if hold_seconds >= settings.MIN_POSITION_HOLD_SECONDS:
            acceptable_spread = (
                spread_yes is None or spread_yes <= settings.MAX_ACCEPTABLE_EXIT_SPREAD
            )
            if acceptable_spread:
                gross_pnl = exit_pnl
                net_pnl = gross_pnl - settings.ESTIMATED_EXIT_COST_USDC
                if net_pnl >= settings.MIN_NET_PROFIT_AFTER_COST_USDC:
                    profit_target_met = gross_pnl >= settings.FAST_PROFIT_TARGET_USDC
                    percent_target_met = (
                        position_size_usdc is not None
                        and position_size_usdc > 0
                        and (gross_pnl / position_size_usdc * 100.0) >= settings.FAST_PROFIT_TARGET_PERCENT
                    )
                    if profit_target_met or percent_target_met:
                        return "FAST_PROFIT_EXIT"

    # ── Priority 4: PROFIT_TARGET ────────────────────────────────────────────
    if exit_pnl >= settings.EXIT_PROFIT_TARGET_USDC:
        return "PROFIT_TARGET"

    # ── Priority 5: TRAILING_STOP ────────────────────────────────────────────
    # Fires when: current_pnl < (peak_pnl - position_value × trailing_distance)
    # Only armed after position has been profitable (peak_pnl > 0).
    if (
        settings.TRAILING_STOP_ENABLED
        and peak_pnl_usdc is not None
        and peak_pnl_usdc > 0
        and position_size_usdc is not None
    ):
        trailing_drawdown_threshold = position_size_usdc * settings.TRAILING_STOP_DISTANCE
        if exit_pnl < (peak_pnl_usdc - trailing_drawdown_threshold):
            return "TRAILING_STOP"

    # ── Priority 6: MAX_HOLD_EXIT ─────────────────────────────────────────────
    # Absolute time backstop — fires unconditionally for any status or market
    # state.  Does NOT depend on signals, opportunities, or universe status.
    # Covers OPEN and PARTIAL positions on active, rolled, or expired markets.
    _max_hold = max_hold_minutes if max_hold_minutes is not None else settings.EXIT_MAX_HOLD_MINUTES
    if position_age_minutes >= _max_hold:
        return "MAX_HOLD_EXIT"

    # ── Priority 7: SIGNAL_INVALIDATION ─────────────────────────────────────
    # Uses direct signal count from the signals table (not the stale
    # opportunity row).  Applies to ALL positions, including those on
    # active markets where the opportunity row may also be stale.
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

        now = datetime.now(timezone.utc)

        # ── Build condition_id → Opportunity map (single query) ───────────────
        condition_ids = list({p.condition_id for p in open_positions})
        opp_rows = await session.execute(
            select(Opportunity).where(Opportunity.condition_id.in_(condition_ids))
        )
        opp_map: dict[str, Opportunity] = {
            o.condition_id: o for o in opp_rows.scalars().all()
        }

        # ── Build market end_time map — needed to detect expired positions ─────
        mkt_rows = await session.execute(
            select(MarketUniverse.condition_id, MarketUniverse.end_time)
            .where(MarketUniverse.condition_id.in_(condition_ids))
        )
        market_end_map: dict[str, datetime] = {
            row[0]: row[1] for row in mkt_rows.all()
        }

        # ── Build resolution map — direct Polymarket outcomes for exit pricing ─
        res_rows = await session.execute(
            select(OutcomeLearning).where(
                OutcomeLearning.condition_id.in_(condition_ids),
                OutcomeLearning.outcome_source == "DIRECT_POLYMARKET_RESOLUTION",
            )
        )
        resolution_map: dict[str, OutcomeLearning] = {
            r.condition_id: r for r in res_rows.scalars().all()
        }

        # ── Direct signal count from signals table (last EXIT_SIGNAL_TIMEOUT_MINUTES) ──
        # Source of truth for SIGNAL_INVALIDATION.  Uses the signals table
        # directly rather than the stale opportunity.signal_count_1h column,
        # which is only updated for ACTIVE markets.  Applied to ALL positions.
        signal_cutoff = now - timedelta(minutes=settings.EXIT_SIGNAL_TIMEOUT_MINUTES)
        sig_rows = await session.execute(
            select(Signal.condition_id, func.count(Signal.id).label("cnt"))
            .where(
                Signal.condition_id.in_(condition_ids),
                Signal.detected_at >= signal_cutoff,
            )
            .group_by(Signal.condition_id)
        )
        direct_signal_count_map: dict[str, int] = {
            row[0]: int(row[1]) for row in sig_rows.all()
        }

        # ── Fetch position IDs that already have a pending exit decision ───────
        position_ids = [p.id for p in open_positions]
        pending_exit_ids = await self._get_pending_exit_position_ids(session, position_ids)

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

                # ── Detect expired market (must run before exit_price logic) ──
                # Opportunity rows retain stale minutes_to_expiry values after
                # a market closes, so the normal EXPIRY_EXIT trigger never fires
                # for positions on expired markets.  We detect expiry via the
                # authoritative market_universe.end_time and force-close using
                # Polymarket resolution evidence.
                #
                # No 0.5 fallback: if resolution data is unavailable the position
                # is skipped this cycle and retried until data arrives.
                forced_expiry_exit = False
                forced_exit_price: Optional[float] = None
                market_end = market_end_map.get(pos.condition_id)
                if market_end is not None:
                    if market_end.tzinfo is None:
                        market_end = market_end.replace(tzinfo=timezone.utc)
                    if market_end <= now:
                        resolution = resolution_map.get(pos.condition_id)
                        if resolution is not None:
                            # Use confirmed Polymarket resolution prices only.
                            # No fallback to 0.5 — a None price means data has not
                            # arrived yet; skip and retry next cycle.
                            if pos.side == "LONG_YES":
                                raw_price = resolution.final_yes_price
                            else:  # LONG_NO
                                raw_price = resolution.final_no_price

                            if raw_price is None:
                                logger.info(
                                    "Exit engine: expired market, resolution row exists but price is None — retrying",
                                    position_id=pos.id,
                                    condition_id=pos.condition_id[:12],
                                    side=pos.side,
                                    market_end=market_end.isoformat(),
                                )
                                skipped += 1
                                continue

                            forced_exit_price = float(raw_price)
                            forced_expiry_exit = True
                            logger.info(
                                "Exit engine: expired market — forced close",
                                position_id=pos.id,
                                condition_id=pos.condition_id[:12],
                                asset=pos.asset,
                                timeframe=pos.timeframe,
                                side=pos.side,
                                forced_exit_price=forced_exit_price,
                                resolution_source=resolution.outcome_source,
                                market_end=market_end.isoformat(),
                            )
                        else:
                            # No resolution data yet — skip and retry.
                            # Never use 0.5 as a synthetic exit price.
                            logger.info(
                                "Exit engine: expired market, no resolution data yet — retrying",
                                position_id=pos.id,
                                condition_id=pos.condition_id[:12],
                                asset=pos.asset,
                                timeframe=pos.timeframe,
                                side=pos.side,
                                market_end=market_end.isoformat(),
                            )
                            skipped += 1
                            continue

                # ── Compute executable exit price ─────────────────────────────
                if forced_expiry_exit:
                    exit_price: Optional[float] = forced_exit_price
                else:
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

                # Multi-lot: evaluate triggers against what's actually still
                # open in this lot (remaining_quantity), not the original
                # entry size — a PARTIAL lot's risk/reward is proportional to
                # what's left, not what was originally bought.
                lot_qty = pos.remaining_quantity if pos.remaining_quantity is not None else pos.quantity
                exit_pnl = round(lot_qty * (exit_price - pos.entry_price), 6)
                age_minutes = _position_age_minutes(pos.opened_at, now)
                minutes_to_expiry = opp.minutes_to_expiry if opp is not None else None
                # Use direct signal count from signals table (source of truth).
                # Ignores the stale opportunity.signal_count_1h column, which
                # is only updated for ACTIVE markets.
                direct_signal_count = direct_signal_count_map.get(pos.condition_id, 0)
                spread_yes = opp.spread_yes if opp is not None else None

                # ── Position notional value for dynamic stop/trailing stop ─────
                position_size_usdc: Optional[float] = None
                if lot_qty and pos.entry_price:
                    position_size_usdc = round(lot_qty * pos.entry_price, 6)

                # ── Peak PnL for trailing stop (Phase 4 Part E) ────────────────
                peak_pnl_usdc: Optional[float] = getattr(pos, "peak_pnl_usdc", None)

                # ── Evaluate triggers in priority order ───────────────────────
                if forced_expiry_exit:
                    exit_reason: Optional[str] = "EXPIRY_EXIT"
                else:
                    exit_reason = _evaluate_triggers(
                        exit_pnl=exit_pnl,
                        minutes_to_expiry=minutes_to_expiry,
                        signal_count_1h=direct_signal_count,
                        position_age_minutes=age_minutes,
                        position_size_usdc=position_size_usdc,
                        spread_yes=spread_yes,
                        peak_pnl_usdc=peak_pnl_usdc,
                    )

                if exit_reason is None:
                    continue

                # ── Emit CLOSE_POSITION TradeDecision ─────────────────────────
                # Phase 10: carry the authoritative forced-expiry exit price
                # (from direct Polymarket resolution) through to the Execution
                # Engine, which must use it verbatim instead of recomputing
                # from live/stale Opportunity bid-ask data.
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
                    spread_yes=spread_yes,
                    skip_reason=None,
                    target_position_id=pos.id,
                    exit_reason=exit_reason,
                    forced_exit_price=(forced_exit_price if forced_expiry_exit else None),
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
                    position_size_usdc=position_size_usdc,
                    spread_yes=spread_yes,
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
