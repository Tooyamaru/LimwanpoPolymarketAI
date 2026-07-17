"""
Market Universe Service — timestamp-slug primary discovery.

5M-ONLY: Syncs exactly 4 known Gamma Series (BTC/ETH/SOL/XRP 5m) into
the market_universe table.  15m and 1H series are no longer discovered
or entered.  Historical data for 15m/1H positions is preserved in the DB
and remains accessible via history endpoints.

DISCOVERY FIX (timestamp-slug):
  Each 5-minute Polymarket market has an individual event slug:
      {asset}-updown-5m-{unix_slot}
  where unix_slot = floor(now / 300) * 300.

  Primary discovery fetches the exact current and adjacent slots via
  GET /events?slug={slug} — this finds the live market regardless of how
  long ago it was deployed.  The previous paginated approach (limit=20,
  order=startDate DESC) missed markets created >20 pages ago.

SELECTION FIX (prediction window):
  The correct "current" market is selected by:
      prediction_window_start <= now < prediction_window_end
  NOT by contract end_time, deployment startDate, or status='active'.

  The prediction_window_* fields are parsed from the question text and
  stored in the DB on every upsert, so selection is always accurate.

Sprint 8.5 / Sprint 9.1 / timestamp-slug rewrite.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from app.core.database import get_session_factory
from app.core.logging import get_logger
from app.services.gamma_series_client import GammaSeriesClient, GammaEvent, GammaMarket
from app.services.market_reference_service import resolve_market_reference
from app.repositories.universe_repository import (
    demote_excess_active_markets,
    expire_stale_markets,
    retire_non_catalog_timeframes,
    upsert_universe_market,
)
from app.utils.prediction_window import (
    SLOT_SECONDS,
    build_event_slug,
    get_candidate_slots,
    slot_to_datetime,
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
    Canonical lifecycle classifier for a MarketUniverse row.

    Uses start_time / end_time (contract window), not prediction_window_*.

    Returns one of:
        PRE_MARKET         — now < start_time
        ACTIVE             — start_time <= now < end_time
        EXPIRED            — now >= end_time
        INVALID_TIME_STATE — start_time or end_time is None, or start >= end
    """
    if now is None:
        now = datetime.now(timezone.utc)

    start = market.start_time
    end   = market.end_time

    if start is None or end is None:
        return LIFECYCLE_INVALID

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

SERIES_CATALOG: list[dict] = [
    {"slug": "btc-up-or-down-5m", "asset": "BTC", "timeframe": "5m"},
    {"slug": "eth-up-or-down-5m", "asset": "ETH", "timeframe": "5m"},
    {"slug": "sol-up-or-down-5m", "asset": "SOL", "timeframe": "5m"},
    {"slug": "xrp-up-or-down-5m", "asset": "XRP", "timeframe": "5m"},
]


def _parse_slot_from_event_slug(event_slug: Optional[str]) -> Optional[int]:
    """
    Extract the Unix slot integer from an event slug.

    Format: {asset}-updown-5m-{slot}
    Example: btc-updown-5m-1784271300 → 1784271300

    The slot is the START of the 5-minute TRADING WINDOW, not the outcome window.
    Returns None if the slug doesn't match the expected pattern.
    """
    if not event_slug:
        return None
    parts = event_slug.rsplit("-", 1)
    if len(parts) != 2:
        return None
    try:
        slot = int(parts[1])
        # Sanity check: must be a multiple of 300 and plausible (year 2020+)
        if slot % SLOT_SECONDS == 0 and slot > 1577836800:
            return slot
    except (ValueError, TypeError):
        pass
    return None


def _prediction_window_from_slot(
    slot: int,
) -> tuple[datetime, datetime, str]:
    """
    Compute the 5-minute trading-slot prediction window from a slot timestamp.

    Returns (pw_start, pw_end, "slug") where:
        pw_start = datetime(slot) UTC
        pw_end   = datetime(slot + 300) UTC
    """
    return (
        slot_to_datetime(slot),
        slot_to_datetime(slot + SLOT_SECONDS),
        "slug",
    )


def _determine_status(
    is_active: bool,
    is_closed: bool,
    start_time: Optional[datetime],
    end_time: Optional[datetime],
) -> str:
    """
    Map Gamma API flags + timestamps to our three-state status.

      active   — currently running market
      upcoming — not yet started
      expired  — closed or end_time passed
    """
    now = datetime.now(timezone.utc)

    if is_closed:
        return "expired"
    if end_time:
        et = end_time if end_time.tzinfo else end_time.replace(tzinfo=timezone.utc)
        if et < now:
            return "expired"
    if is_active:
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

    Primary discovery (timestamp-slug):
        For each asset, fetch events by exact timestamp-slug for the
        current slot and adjacent slots (prev + next 1-3). This
        guarantees the live market is found regardless of when it
        was deployed.

    Paginated backfill:
        Also runs the paginated series query (limit=20) to warm
        future slots into the DB. Uses flat+sort+rank logic (Sprint 9.1):
        markets sorted by end_time ascending, rank 0 = active, rest = upcoming.

    Usage:
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

        Step 1: Timestamp-slug lookup — fetch current + adjacent slots
                for each asset via GET /events?slug={slug}.
        Step 2: Paginated backfill — flat+sort+rank (Sprint 9.1) via
                GET /events?series_slug={slug}&order=startDate&ascending=false.
        Step 3: Enforce invariants — expire stale, demote excess active,
                retire non-catalog timeframes.
        """
        started_at = datetime.now(timezone.utc)
        logger.info("Universe sync started (timestamp-slug mode)", series_count=len(SERIES_CATALOG))

        total_upserted = 0
        total_expired_by_time = 0
        total_retired_non_catalog = 0
        errors: list[str] = []
        gamma_series_ok = 0
        gamma_series_empty = 0
        gamma_series_failed = 0

        factory = get_session_factory()

        # ── Step 0: retire legacy non-catalog timeframe markets ───────────────
        from app.config.settings import settings as _settings
        async with factory() as session:
            total_retired_non_catalog = await retire_non_catalog_timeframes(
                session, _settings.ENABLED_TIMEFRAME
            )
            await session.commit()

        for entry in SERIES_CATALOG:
            series_slug = entry["slug"]
            asset = entry["asset"]
            timeframe = entry["timeframe"]

            try:
                # ── Step 1: Series metadata ───────────────────────────────────
                series = await self._client.fetch_series(series_slug)
                series_id = series.series_id if series else None

                now = datetime.now(timezone.utc)
                pending_refs: list[tuple[str, str, str, Optional[datetime]]] = []
                slug_found = 0
                slug_active_cid: Optional[str] = None  # set by current-slot discovery

                # ── Step 2: Timestamp-slug primary discovery ───────────────────
                #
                # prediction_window = trading slot window (slug timestamp based),
                # NOT the outcome/resolution window embedded in the question text.
                #   pw_start = slot_start (when seed orders open)
                #   pw_end   = slot_start + 300 (when seed orders close)
                # Selection query "prediction_window_start <= now < prediction_window_end"
                # then correctly identifies the single market accepting orders right now.
                candidate_slots = get_candidate_slots(now, lookahead=3)
                for slot in candidate_slots:
                    event_slug = build_event_slug(asset, slot)
                    event = await self._client.fetch_event_by_slug(event_slug)
                    if event is None:
                        continue

                    logger.info(
                        "Timestamp-slug: found event",
                        asset=asset,
                        event_slug=event_slug,
                        markets_count=len(event.markets),
                    )
                    slug_found += 1

                    pw_start, pw_end, pw_source = _prediction_window_from_slot(slot)

                    # status: current slot → active; adjacent → upcoming
                    current_slot = candidate_slots[1]  # index 1 = current slot
                    is_current_slot = (slot == current_slot)
                    if is_current_slot and event.markets:
                        slug_active_cid = event.markets[0].condition_id

                    async with factory() as session:
                        for market in event.markets:
                            if market.is_closed:
                                continue

                            market_start = market.start_time or event.start_time
                            status = "active" if is_current_slot else "upcoming"

                            row = await upsert_universe_market(
                                session,
                                asset=asset,
                                timeframe=timeframe,
                                series_slug=series_slug,
                                series_id=series_id,
                                event_id=event.event_id,
                                condition_id=market.condition_id,
                                yes_token_id=market.yes_token_id,
                                no_token_id=market.no_token_id,
                                question=market.question or event.title,
                                start_time=market_start,
                                end_time=market.end_time or event.end_time,
                                status=status,
                                prediction_window_start=pw_start,
                                prediction_window_end=pw_end,
                                prediction_window_source=pw_source,
                                prediction_window_validated_at=now,
                                event_slug=event_slug,
                            )
                            total_upserted += 1
                            if row.opening_price is None:
                                pending_refs.append((market.condition_id, asset, timeframe, market_start))

                        await session.commit()

                # ── Step 3: Paginated backfill (flat+sort+rank, Sprint 9.1) ────
                events = await self._client.fetch_events(series_slug, limit=20)
                if events:
                    gamma_series_ok += 1
                else:
                    gamma_series_empty += 1

                # Flatten all (market_end, event, market) pairs across all events,
                # filter out closed/past-end_time markets, sort by end_time ascending.
                # index 0 = soonest = active; all others = upcoming.
                now = datetime.now(timezone.utc)
                flat: list[tuple[datetime, GammaEvent, GammaMarket]] = []
                for event in events:
                    for market in event.markets:
                        if market.is_closed:
                            continue
                        market_end = market.end_time or event.end_time
                        if market_end is None:
                            continue
                        et = market_end if market_end.tzinfo else market_end.replace(tzinfo=timezone.utc)
                        if et <= now:
                            continue
                        flat.append((et, event, market))

                flat.sort(key=lambda t: t[0])

                # Determine rank-0 (active) condition_id from paginated backfill.
                # This is also used for demote_excess_active_markets below.
                paginated_active_cid: Optional[str] = flat[0][2].condition_id if flat else None

                async with factory() as session:
                    for rank, (market_end, event, market) in enumerate(flat):
                        # Paginated backfill: all markets upserted as "upcoming".
                        # The slug-based discovery is the sole authority on "active".
                        # demote_excess_active_markets (called below) enforces the
                        # single-active invariant using slug_active_cid.
                        market_start = market.start_time or event.start_time

                        # Slot-based prediction window from event.slug if available.
                        # Falls back to Sprint 9.1 rank-based status for compatibility
                        # with tests that don't provide event slugs.
                        event_slot = _parse_slot_from_event_slug(event.slug)
                        if event_slot is not None:
                            pw_start, pw_end, pw_source = _prediction_window_from_slot(event_slot)
                        else:
                            pw_start = pw_end = None
                            pw_source = "missing"

                        # Sprint 9.1: rank==0 (soonest end_time) gets active status.
                        # This preserves backward compat when slug_active_cid is None
                        # (e.g., slug lookup found nothing / tests without live events).
                        if slug_active_cid is None and rank == 0:
                            status = "active"
                        elif slug_active_cid is not None and market.condition_id == slug_active_cid:
                            status = "active"
                        else:
                            status = "upcoming"

                        row = await upsert_universe_market(
                            session,
                            asset=asset,
                            timeframe=timeframe,
                            series_slug=series_slug,
                            series_id=series_id,
                            event_id=event.event_id,
                            condition_id=market.condition_id,
                            yes_token_id=market.yes_token_id,
                            no_token_id=market.no_token_id,
                            question=market.question or event.title,
                            start_time=market_start,
                            end_time=market.end_time or event.end_time,
                            status=status,
                            event_slug=event.slug if event.slug and "updown-5m" in event.slug else None,
                            prediction_window_start=pw_start,
                            prediction_window_end=pw_end,
                            prediction_window_source=pw_source,
                            prediction_window_validated_at=now if pw_start is not None else None,
                        )
                        total_upserted += 1
                        if row.opening_price is None:
                            pending_refs.append((market.condition_id, asset, timeframe, market_start))

                    # Enforce "exactly one active" for this series.
                    # Prefer slug_active_cid (from current trading slot) over rank-0.
                    # If slug lookup found nothing, fall back to paginated rank-0 cid.
                    effective_active_cid = slug_active_cid or paginated_active_cid
                    await demote_excess_active_markets(
                        session, asset, timeframe, effective_active_cid
                    )
                    expired = await expire_stale_markets(session)
                    await session.commit()
                    total_expired_by_time += expired

                # ── Step 4: Opening price resolution ──────────────────────────
                seen_cids: set[str] = set()
                for cond_id, ref_asset, ref_tf, ref_start in pending_refs:
                    if cond_id in seen_cids:
                        continue
                    seen_cids.add(cond_id)
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

                logger.debug(
                    "Series sync complete",
                    asset=asset,
                    slug_events_found=slug_found,
                    paginated_events=len(events),
                    paginated_active_cid=paginated_active_cid,
                )

            except Exception as exc:
                msg = f"{series_slug}: {exc}"
                errors.append(msg)
                gamma_series_failed += 1
                logger.error("Series sync failed", slug=series_slug, error=str(exc))

        elapsed_ms = (datetime.now(timezone.utc) - started_at).total_seconds() * 1000
        self._last_sync = datetime.now(timezone.utc)
        self._last_sync_duration_ms = elapsed_ms

        # ── Gamma ingestion status classification ─────────────────────────────
        total_series = len(SERIES_CATALOG)
        if gamma_series_failed == total_series:
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
            "markets_retired_non_catalog": total_retired_non_catalog,
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
