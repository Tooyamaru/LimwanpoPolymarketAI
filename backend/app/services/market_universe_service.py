"""
Market Universe Service — Sprint 7 / Sprint 8.5 / Sprint 9.1 fix.

5M-ONLY: Syncs exactly 4 known Gamma Series (BTC/ETH/SOL/XRP 5m) into
the market_universe table.  15m and 1H series are no longer discovered
or entered.  Historical data for 15m/1H positions is preserved in the DB
and remains accessible via history endpoints.

Determines status (active / upcoming / expired) for each market
and keeps the universe current on every sync cycle.

Sprint 8.5 fix:
  Events returned by the series endpoint all carry active=True,
  closed=False.  Status is now determined by sort position:
    - The event with the soonest future end_time → active
    - All other open events → upcoming
    - expire_stale_markets() handles past-end_time cleanup

Sprint 9.1 fix (active-market lifecycle bug):
  The previous implementation assigned active/upcoming at the EVENT
  level (idx == 0).  When a single Gamma event contains multiple
  markets, or when two events are very close in end_time, every market
  inside the first event was marked active — violating the invariant
  "exactly one active market per (asset, timeframe)".

  Fix: flatten ALL (event, market) pairs for a series, filter out
  closed and past-end_time markets, sort by market end_time ascending,
  then mark ONLY the market with the smallest end_time as active.
  All remaining markets are marked upcoming regardless of which event
  they belong to.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from app.core.database import get_session_factory
from app.core.logging import get_logger
from app.services.gamma_series_client import GammaSeriesClient
from app.services.market_reference_service import resolve_market_reference
from app.repositories.universe_repository import (
    demote_excess_active_markets,
    expire_stale_markets,
    upsert_universe_market,
)

logger = get_logger(__name__)


# ── Canonical lifecycle state constants ───────────────────────────────────────

LIFECYCLE_PRE_MARKET         = "PRE_MARKET"
LIFECYCLE_ACTIVE             = "ACTIVE"
LIFECYCLE_EXPIRED            = "EXPIRED"
LIFECYCLE_RESOLUTION_PENDING = "RESOLUTION_PENDING"
LIFECYCLE_RESOLVED           = "RESOLVED"
LIFECYCLE_INVALID            = "INVALID_TIME_STATE"


def get_market_lifecycle_state(market: Any, now: Optional[datetime] = None) -> str:
    """
    Canonical lifecycle classifier for a MarketUniverse row (or any object with
    .start_time and .end_time datetime fields).

    Returns one of:
        PRE_MARKET         — now < start_time; seed data may exist, execution forbidden
        ACTIVE             — start_time <= now < end_time; live trading window
        EXPIRED            — now >= end_time; no new entry allowed
        INVALID_TIME_STATE — start_time or end_time is None, or start >= end

    Notes:
        RESOLUTION_PENDING and RESOLVED require cross-referencing outcome_learnings data.
        Those states are not determined here; callers that need them must check the
        outcomes table separately.  EXPIRED is the safe fallback until resolution arrives.

    All comparisons use UTC.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    start = market.start_time
    end   = market.end_time

    if start is None or end is None:
        return LIFECYCLE_INVALID

    # Ensure timezone-aware comparisons
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)

    if start >= end:
        return LIFECYCLE_INVALID

    if now < start:
        return LIFECYCLE_PRE_MARKET

    if now >= end:
        return LIFECYCLE_EXPIRED

    return LIFECYCLE_ACTIVE


# ── Known series catalog (5M-ONLY) ────────────────────────────────────────────
# Only BTC/ETH/SOL/XRP 5-minute series are active.
# 15m and 1H series have been removed from active discovery.
# Historical positions opened under 15m/1H condition_ids remain in the DB
# and are processed by the Exit Engine until fully CLOSED.

SERIES_CATALOG: list[dict] = [
    {"slug": "btc-up-or-down-5m", "asset": "BTC", "timeframe": "5m"},
    {"slug": "eth-up-or-down-5m", "asset": "ETH", "timeframe": "5m"},
    {"slug": "sol-up-or-down-5m", "asset": "SOL", "timeframe": "5m"},
    {"slug": "xrp-up-or-down-5m", "asset": "XRP", "timeframe": "5m"},
]


def _determine_status(
    is_active: bool,
    is_closed: bool,
    start_time: Optional[datetime],
    end_time: Optional[datetime],
) -> str:
    """
    Map Gamma API flags + timestamps to our three-state status.

      active   — currently running market (start_time has passed, end_time in future)
      upcoming — not yet started
      expired  — closed or end_time passed

    Lifecycle guard: Gamma can set active=True before start_time arrives (the
    market book is open for seeding but the prediction window hasn't started).
    We only promote a market to "active" once start_time <= now.
    """
    now = datetime.now(timezone.utc)

    if is_closed:
        return "expired"
    if end_time and end_time.replace(tzinfo=timezone.utc if end_time.tzinfo is None else end_time.tzinfo) < now:
        return "expired"
    if is_active:
        # Only mark active if the prediction window has actually opened.
        # Gamma marks markets active before start_time for order-book seeding.
        if start_time:
            st = start_time if start_time.tzinfo else start_time.replace(tzinfo=timezone.utc)
            if st > now:
                return "upcoming"
        return "active"
    if start_time:
        st = start_time if start_time.tzinfo else start_time.replace(tzinfo=timezone.utc)
        if st > now:
            return "upcoming"
    return "upcoming"


class MarketUniverseService:
    """
    Orchestrates a full universe sync across all 4 known 5m series.
    (5M-ONLY: BTC/ETH/SOL/XRP 5-minute markets only.)

    Usage (from FastAPI lifespan or scheduler):
        service = MarketUniverseService()
        result = await service.sync()
        await service.close()
    """

    def __init__(self) -> None:
        self._client = GammaSeriesClient()
        self._last_sync: Optional[datetime] = None
        self._last_sync_duration_ms: Optional[float] = None

    async def sync(self) -> dict:
        """
        Sync the entire universe.  Returns a summary dict.
        5M-ONLY: processes exactly 4 series (BTC/ETH/SOL/XRP 5m).

        Sprint 9.1: markets are flattened across all events for a series,
        then sorted by market end_time ascending.  Only the single market
        with the smallest future end_time is marked active; all others are
        marked upcoming.  This enforces the invariant that exactly ONE
        active market exists per (asset, timeframe) regardless of how many
        consecutive windows Polymarket has open simultaneously.
        """
        started_at = datetime.now(timezone.utc)
        logger.info("Universe sync started", series_count=len(SERIES_CATALOG))

        total_upserted = 0
        total_expired_by_time = 0
        errors: list[str] = []
        gamma_series_ok = 0       # series that returned ≥1 event with markets
        gamma_series_empty = 0    # series reachable but returned 0 events
        gamma_series_failed = 0   # series that raised an exception

        factory = get_session_factory()

        for entry in SERIES_CATALOG:
            slug = entry["slug"]
            asset = entry["asset"]
            timeframe = entry["timeframe"]

            try:
                series = await self._client.fetch_series(slug)
                series_id = series.series_id if series else None

                # fetch_events returns events pre-sorted by end_time ascending
                # with closed/expired events already filtered out.
                events = await self._client.fetch_events(slug, limit=20)

                # Track Gamma fetch quality
                if events:
                    gamma_series_ok += 1
                else:
                    gamma_series_empty += 1

                # ── Sprint 9.1 fix ────────────────────────────────────────────
                # Flatten all (event, market) pairs across every returned event,
                # then sort the flat list by market end_time ascending.
                # Only the first item (smallest end_time) becomes "active".
                # All remaining items become "upcoming".
                #
                # This is strictly safer than the previous idx==0 logic, which
                # assigned active status at the event level: if a Gamma event
                # contained multiple markets with different end_times, every
                # market in that event was incorrectly marked active.
                now = datetime.now(timezone.utc)
                flat: list[tuple[datetime, "GammaEvent", "GammaMarket"]] = []
                for event in events:
                    for market in event.markets:
                        if market.is_closed:
                            continue
                        market_end = market.end_time or event.end_time
                        if market_end is None or market_end <= now:
                            continue
                        flat.append((market_end, event, market))

                # Sort by market end_time ascending: index 0 = soonest = active
                flat.sort(key=lambda t: t[0])

                # Determine which condition_id is the true active market so we
                # can pass it to demote_excess_active_markets below.
                active_condition_id: Optional[str] = flat[0][2].condition_id if flat else None

                # Collect markets that need reference resolution after DB commit.
                # We resolve outside the session to avoid holding the transaction
                # open during the Binance HTTP call.
                pending_refs: list[tuple[str, str, str, Optional[datetime]]] = []

                async with factory() as session:
                    upserted_this_series = 0
                    for rank, (market_end, event, market) in enumerate(flat):
                        effective_active = rank == 0
                        status = _determine_status(
                            is_active=effective_active,
                            is_closed=market.is_closed,
                            start_time=market.start_time,
                            end_time=market.end_time,
                        )
                        row = await upsert_universe_market(
                            session,
                            asset=asset,
                            timeframe=timeframe,
                            series_slug=slug,
                            series_id=series_id,
                            event_id=event.event_id,
                            condition_id=market.condition_id,
                            yes_token_id=market.yes_token_id,
                            no_token_id=market.no_token_id,
                            question=market.question or event.title,
                            start_time=market.start_time or event.start_time,
                            end_time=market.end_time or event.end_time,
                            status=status,
                        )
                        upserted_this_series += 1

                        # Queue reference resolution for markets without
                        # an opening_price (new markets or past-PENDING ones).
                        if row.opening_price is None:
                            market_start = market.start_time or event.start_time
                            pending_refs.append(
                                (market.condition_id, asset, timeframe, market_start)
                            )

                    # Sprint 9.1: demote any stale "active" records for this
                    # (asset, timeframe) that were NOT chosen as the active
                    # market in this cycle.  This cleans up records that
                    # fell off the current fetch_events page but whose
                    # end_time is still future (so expire_stale_markets
                    # cannot touch them).
                    await demote_excess_active_markets(
                        session, asset, timeframe, active_condition_id
                    )

                    expired = await expire_stale_markets(session)
                    await session.commit()

                    total_upserted += upserted_this_series
                    total_expired_by_time += expired

                    logger.debug(
                        "Series synced",
                        slug=slug,
                        upserted=upserted_this_series,
                        stale_expired=expired,
                    )

                # Resolve opening_price for any markets that don't have one yet.
                # Done after the session is closed to avoid long-lived transactions.
                for cond_id, ref_asset, ref_tf, ref_start in pending_refs:
                    try:
                        await resolve_market_reference(
                            condition_id=cond_id,
                            asset=ref_asset,
                            timeframe=ref_tf,
                            start_time=ref_start,
                        )
                    except Exception as ref_exc:
                        logger.warning(
                            "Market reference resolution failed",
                            condition_id=cond_id,
                            error=str(ref_exc),
                        )

            except Exception as exc:
                msg = f"{slug}: {exc}"
                errors.append(msg)
                gamma_series_failed += 1
                logger.error("Series sync failed", slug=slug, error=str(exc))

        elapsed_ms = (
            datetime.now(timezone.utc) - started_at
        ).total_seconds() * 1000
        self._last_sync = datetime.now(timezone.utc)
        self._last_sync_duration_ms = elapsed_ms

        # ── Gamma ingestion status classification ─────────────────────────────
        total_series = len(SERIES_CATALOG)
        if gamma_series_failed == total_series:
            # Every series raised an exception — check for SSL signature
            first_error = errors[0] if errors else ""
            if "SSL" in first_error.upper() or "CERTIFICATE" in first_error.upper():
                gamma_status = "GAMMA_SSL_ERROR"
            else:
                gamma_status = "GAMMA_UNREACHABLE"
        elif gamma_series_ok == 0 and gamma_series_failed == 0:
            gamma_status = "GAMMA_EMPTY_RESPONSE"
        elif gamma_series_ok == 0 and gamma_series_failed > 0:
            gamma_status = "GAMMA_UNREACHABLE"
        elif gamma_series_failed > 0:
            gamma_status = "GAMMA_PARTIAL_SUCCESS"
        else:
            gamma_status = "GAMMA_OK"

        if gamma_status != "GAMMA_OK":
            logger.warning(
                "Universe sync Gamma ingestion issue",
                gamma_status=gamma_status,
                series_ok=gamma_series_ok,
                series_empty=gamma_series_empty,
                series_failed=gamma_series_failed,
                markets_upserted=total_upserted,
            )

        summary = {
            "synced_at": self._last_sync.isoformat(),
            "duration_ms": round(elapsed_ms, 1),
            "series_processed": total_series,
            "markets_upserted": total_upserted,
            "markets_expired_by_time": total_expired_by_time,
            "gamma_status": gamma_status,
            "gamma_series_ok": gamma_series_ok,
            "gamma_series_empty": gamma_series_empty,
            "gamma_series_failed": gamma_series_failed,
            "errors": errors,
        }

        logger.info(
            "Universe sync complete",
            duration_ms=round(elapsed_ms, 1),
            markets_upserted=total_upserted,
            gamma_status=gamma_status,
            errors=len(errors),
        )
        return summary

    async def close(self) -> None:
        await self._client.close()

    @property
    def last_sync(self) -> Optional[datetime]:
        return self._last_sync

    @property
    def last_sync_duration_ms(self) -> Optional[float]:
        return self._last_sync_duration_ms
