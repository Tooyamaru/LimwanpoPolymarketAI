"""
Universe API endpoints — Sprint 7.

GET  /api/v1/universe           — all markets in the universe
GET  /api/v1/universe/active    — active markets only
GET  /api/v1/universe/upcoming  — upcoming markets only
GET  /api/v1/universe/stats     — counts by asset × timeframe × status
POST /api/v1/universe/sync      — trigger an immediate sync

All list responses include computed lifecycle fields:
  lifecycle_state, execution_allowed, is_pre_market, is_active_market,
  is_expired, display_status, data_mode
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.repositories.universe_repository import (
    get_active_universe,
    get_all_universe,
    get_upcoming_universe,
    get_universe_stats,
    get_window_live_universe,
)
from app.schemas.universe import (
    AssetStats,
    SyncResponse,
    TimeframeStats,
    UniverseMarketResponse,
    UniverseStatsResponse,
)
from app.services.market_universe_service import (
    LIFECYCLE_ACTIVE,
    LIFECYCLE_EXPIRED,
    LIFECYCLE_INVALID,
    LIFECYCLE_PRE_MARKET,
    LIFECYCLE_RESOLUTION_PENDING,
    LIFECYCLE_RESOLVED,
    get_market_lifecycle_state,
)
from app.utils.prediction_window import (
    PRED_WINDOW_LIVE,
    get_prediction_window_lifecycle,
)

router = APIRouter(prefix="/universe", tags=["universe"])

_log = logging.getLogger(__name__)

# ── Prediction-window parser ──────────────────────────────────────────────────

_ET = ZoneInfo("America/New_York")

_MONTH_MAP: dict[str, int] = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}

# "July 18"
_DATE_RE = re.compile(
    r"(?P<month>January|February|March|April|May|June|July|August|"
    r"September|October|November|December)\s+(?P<day>\d{1,2})",
    re.IGNORECASE,
)

# "3:55AM–4:00AM ET" — supports -, –, — and optional spaces around separator;
# AM/PM optional on either or both times.
_TIME_RE = re.compile(
    r"(?P<h1>\d{1,2}):(?P<m1>\d{2})\s*(?P<p1>[AaPp][Mm])?"
    r"\s*[-\u2013\u2014]\s*"
    r"(?P<h2>\d{1,2}):(?P<m2>\d{2})\s*(?P<p2>[AaPp][Mm])?"
    r"(?:\s+ET)?"
)


def _parse_prediction_window(
    question: str,
    market_end_time: "datetime | None" = None,
) -> "tuple[datetime | None, datetime | None, str]":
    """
    Parse the exact 5-minute prediction interval from a Polymarket question string.

    Handles:
      • hyphen, en-dash, em-dash separators
      • optional whitespace around the separator
      • AM/PM on one or both times
      • midnight-crossing intervals
      • year inference from market_end_time (or server year as fallback)
      • year-rollover edge cases (Dec → Jan)

    Returns:
        (start_utc, end_utc, "question_interval")  on success
        (None, None, "missing")                    on any failure
    """
    # 1. Find the date (Month Day)
    dm = _DATE_RE.search(question)
    if not dm:
        _log.debug("pw_parse.no_date q=%s", question[:80])
        return None, None, "missing"
    month = _MONTH_MAP[dm.group("month").lower()]
    day = int(dm.group("day"))

    # 2. Infer reference time for year selection
    now_utc = datetime.now(timezone.utc)
    if market_end_time is not None:
        ref = (
            market_end_time
            if market_end_time.tzinfo
            else market_end_time.replace(tzinfo=timezone.utc)
        )
    else:
        ref = now_utc
    base_year = ref.year

    # 3. Find the time range
    tm = _TIME_RE.search(question)
    if not tm:
        _log.debug("pw_parse.no_time q=%s", question[:80])
        return None, None, "missing"

    h1, m1 = int(tm.group("h1")), int(tm.group("m1"))
    h2, m2 = int(tm.group("h2")), int(tm.group("m2"))
    p1 = (tm.group("p1") or "").upper()
    p2 = (tm.group("p2") or "").upper()

    # Propagate AM/PM if only one side carries it
    if p1 and not p2:
        p2 = p1
    elif p2 and not p1:
        p1 = p2
    if not p1:
        _log.debug("pw_parse.no_ampm q=%s", question[:80])
        return None, None, "missing"

    def _to24(h: int, ampm: str) -> int:
        if ampm == "AM":
            return 0 if h == 12 else h
        return h if h == 12 else h + 12  # PM

    h1_24 = _to24(h1, p1)
    h2_24 = _to24(h2, p2)

    # 4. Build start/end in ET for a candidate year; handle midnight crossing
    def _try_year(yr: int) -> "tuple[datetime | None, datetime | None]":
        try:
            start_et = datetime(yr, month, day, h1_24, m1, 0, tzinfo=_ET)
        except (ValueError, OverflowError):
            return None, None

        end_min = h2_24 * 60 + m2
        start_min = h1_24 * 60 + m1
        if end_min <= start_min:
            # Midnight-crossing: end is on the next calendar day
            next_date = start_et.date() + timedelta(days=1)
            try:
                end_et = datetime(
                    next_date.year, next_date.month, next_date.day,
                    h2_24, m2, 0, tzinfo=_ET,
                )
            except (ValueError, OverflowError):
                return None, None
        else:
            try:
                end_et = datetime(yr, month, day, h2_24, m2, 0, tzinfo=_ET)
            except (ValueError, OverflowError):
                return None, None

        return start_et.astimezone(timezone.utc), end_et.astimezone(timezone.utc)

    # Pick the candidate year whose result is closest to ref
    best_start: "datetime | None" = None
    best_end: "datetime | None" = None
    best_dist = float("inf")
    for yr in (base_year, base_year + 1, base_year - 1):
        s, e = _try_year(yr)
        if s is None:
            continue
        dist = abs((s - ref).total_seconds())
        if dist < best_dist:
            best_start, best_end, best_dist = s, e, dist

    if best_start is None or best_end is None:
        _log.debug("pw_parse.build_failed q=%s", question[:80])
        return None, None, "missing"

    # Reject windows more than ~6 months away from ref (indicates bad year inference)
    if best_dist > 180 * 24 * 3600:
        _log.warning("pw_parse.year_too_far dist_days=%.1f q=%s",
                     best_dist / 86400, question[:80])
        return None, None, "missing"

    # 5. Validate: duration must be exactly 300 seconds
    duration = (best_end - best_start).total_seconds()
    if duration != 300:
        _log.warning("pw_parse.invalid_duration duration=%.0f q=%s",
                     duration, question[:80])
        return None, None, "missing"

    return best_start, best_end, "question_interval"


# ── Lifecycle annotation helper ───────────────────────────────────────────────

def _annotate_lifecycle(m) -> UniverseMarketResponse:
    """
    Build a UniverseMarketResponse from an ORM row and populate all lifecycle
    state fields (computed from start_time/end_time, not stored in DB).

    Countdown semantics (spec §4):
      prediction_window_start/end — parsed from market question text (exact 5-min interval)
      trading_open_time           — market contract start_time (when trading opens)
      countdown_mode              — STARTS_IN | ENDS_IN | RESOLVING | SYNCING
      countdown_target            — ISO UTC timestamp the frontend ticks toward
      countdown_seconds           — integer seconds remaining (0–300 for ENDS_IN)
      countdown_source            — question_interval | missing
      countdown_data_stale        — True when interval cannot be parsed
    """
    now = datetime.now(timezone.utc)
    server_time_iso = now.isoformat()

    # ── trading_open_time: when the market contract starts trading (start_time) ──
    raw_start = m.start_time
    trading_open_time_iso: str | None = None
    if raw_start is not None:
        if raw_start.tzinfo is None:
            raw_start = raw_start.replace(tzinfo=timezone.utc)
        trading_open_time_iso = raw_start.isoformat()

    # ── Prediction window: use stored DB value first, fall back to re-parsing ──
    raw_end = m.end_time
    if raw_end is not None and raw_end.tzinfo is None:
        raw_end = raw_end.replace(tzinfo=timezone.utc)

    stored_pw_start = getattr(m, "prediction_window_start", None)
    stored_pw_end   = getattr(m, "prediction_window_end", None)
    stored_pw_src   = getattr(m, "prediction_window_source", None)

    if stored_pw_start is not None and stored_pw_end is not None:
        # Stored from discovery — most accurate, use directly
        pw_start  = stored_pw_start if stored_pw_start.tzinfo else stored_pw_start.replace(tzinfo=timezone.utc)
        pw_end    = stored_pw_end   if stored_pw_end.tzinfo   else stored_pw_end.replace(tzinfo=timezone.utc)
        pw_source = stored_pw_src or "question_interval"
    else:
        # Not yet stored — parse from question text as fallback
        pw_start, pw_end, pw_source = _parse_prediction_window(
            m.question or "", raw_end
        )

    prediction_window_start_iso: str | None = (
        pw_start.isoformat() if pw_start is not None else None
    )
    prediction_window_end_iso: str | None = (
        pw_end.isoformat() if pw_end is not None else None
    )

    # ── Countdown semantics (spec §4) ─────────────────────────────────────────
    if pw_start is None or pw_end is None:
        # Cannot parse question interval → SYNCING
        countdown_mode = "SYNCING"
        countdown_target: str | None = None
        countdown_seconds: int | None = None
        countdown_data_stale = True
        countdown_source = "missing"
    elif now < pw_start:
        # Before prediction window → STARTS_IN
        countdown_mode = "STARTS_IN"
        countdown_target = pw_start.isoformat()
        countdown_seconds = max(0, int((pw_start - now).total_seconds()))
        countdown_data_stale = False
        countdown_source = pw_source
    elif now <= pw_end:
        # During prediction window → ENDS_IN (0–300 s)
        countdown_mode = "ENDS_IN"
        countdown_target = pw_end.isoformat()
        secs = int((pw_end - now).total_seconds())
        countdown_seconds = max(0, min(300, secs))
        countdown_data_stale = False
        countdown_source = pw_source
    else:
        # After prediction window → RESOLVING
        countdown_mode = "RESOLVING"
        countdown_target = None
        countdown_seconds = 0
        countdown_data_stale = False
        countdown_source = pw_source

    # ── Prediction-window lifecycle (from canonical utility, never from start/end_time) ──
    pw_lc = get_prediction_window_lifecycle(pw_start, pw_end)
    pred_lc_state             = pw_lc["state"]
    pred_window_valid         = pw_lc["valid"]
    pred_window_validation_error = pw_lc["validation_error"]

    # ── Lifecycle state (contract) ────────────────────────────────────────────
    resp = UniverseMarketResponse.model_validate(m)
    lc = get_market_lifecycle_state(m)

    is_active   = lc == LIFECYCLE_ACTIVE
    is_pre      = lc == LIFECYCLE_PRE_MARKET
    is_exp      = lc in (LIFECYCLE_EXPIRED, LIFECYCLE_RESOLUTION_PENDING)
    is_resolved = lc == LIFECYCLE_RESOLVED

    if lc == LIFECYCLE_PRE_MARKET:
        display = "PRE-MARKET"
        mode    = "SEED"
    elif lc == LIFECYCLE_ACTIVE:
        display = "ACTIVE"
        mode    = "LIVE"
    elif lc in (LIFECYCLE_EXPIRED, LIFECYCLE_RESOLUTION_PENDING):
        display = "EXPIRED"
        mode    = "FINAL"
    elif lc == LIFECYCLE_RESOLVED:
        display = "RESOLVED"
        mode    = "FINAL"
    else:  # INVALID_TIME_STATE
        display = "UNKNOWN"
        mode    = "SEED"

    # ── execution_allowed: requires valid live prediction window ──────────────
    # Spec: only True when prediction_window_valid=True AND state=WINDOW_LIVE.
    # Exception: when no prediction window data exists (pw_start/pw_end both None),
    # fall back to contract lifecycle — covers hourly markets without 5m slots.
    if pw_start is None or pw_end is None:
        execution_allowed = is_active
    else:
        execution_allowed = pred_window_valid and pred_lc_state == PRED_WINDOW_LIVE

    # ── event_slug and market_slot_timestamp ─────────────────────────────────
    # Use isinstance guard: getattr on a MagicMock returns a MagicMock (never None),
    # so a plain truthiness check would pass and cause re.search to fail on a mock.
    _raw_slug = getattr(m, "event_slug", None)
    event_slug_val: str | None = _raw_slug if isinstance(_raw_slug, str) else None
    market_slot_ts: int | None = None
    if event_slug_val:
        _slug_match = re.search(r"-(\d{10})$", event_slug_val)
        if _slug_match:
            market_slot_ts = int(_slug_match.group(1))

    return resp.model_copy(update={
        # ── contract lifecycle (backward compat) ──────────────────────────────
        "lifecycle_state":                    lc,
        "contract_lifecycle_state":           lc,
        # ── prediction-window lifecycle (new) ─────────────────────────────────
        "prediction_lifecycle_state":         pred_lc_state,
        "prediction_window_valid":            pred_window_valid,
        "prediction_window_validation_error": pred_window_validation_error,
        # ── execution gate ────────────────────────────────────────────────────
        "execution_allowed":                  execution_allowed,
        # ── other lifecycle flags ─────────────────────────────────────────────
        "is_pre_market":                      is_pre,
        "is_active_market":                   is_active,
        "is_expired":                         is_exp,
        "display_status":                     display,
        "data_mode":                          mode,
        # ── timing ───────────────────────────────────────────────────────────
        "server_time":                        server_time_iso,
        "generated_at":                       server_time_iso,
        "countdown_seconds":                  countdown_seconds,
        "countdown_source":                   countdown_source,
        "countdown_data_stale":               countdown_data_stale,
        "countdown_mode":                     countdown_mode,
        "prediction_window_start":            prediction_window_start_iso,
        "prediction_window_end":              prediction_window_end_iso,
        "prediction_window_source":           pw_source,
        "countdown_target":                   countdown_target,
        "trading_open_time":                  trading_open_time_iso,
        # ── identity ─────────────────────────────────────────────────────────
        "event_slug":                         event_slug_val,
        "market_slot_timestamp":              market_slot_ts,
    })


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=list[UniverseMarketResponse],
    summary="List all markets in the universe",
)
async def list_universe(
    session: AsyncSession = Depends(get_db_session),
) -> list[UniverseMarketResponse]:
    markets = await get_all_universe(session)
    return [_annotate_lifecycle(m) for m in markets]


@router.get(
    "/active",
    response_model=list[UniverseMarketResponse],
    summary="List active universe markets",
)
async def list_active(
    session: AsyncSession = Depends(get_db_session),
) -> list[UniverseMarketResponse]:
    # Primary: prediction-window-based selection (trading slot window live right now).
    # This is the correct query for 5m markets whose prediction_window_* columns are set.
    markets = await get_window_live_universe(session)
    if not markets:
        # Fallback: status-field-based query (covers legacy rows without pw data
        # and markets where the window was missed during a sync gap).
        markets = await get_active_universe(session)
    return [_annotate_lifecycle(m) for m in markets]


@router.get(
    "/upcoming",
    response_model=list[UniverseMarketResponse],
    summary="List upcoming universe markets",
)
async def list_upcoming(
    session: AsyncSession = Depends(get_db_session),
) -> list[UniverseMarketResponse]:
    markets = await get_upcoming_universe(session)
    return [_annotate_lifecycle(m) for m in markets]


@router.get(
    "/stats",
    response_model=UniverseStatsResponse,
    summary="Universe statistics by asset, timeframe, and status",
)
async def universe_stats(
    session: AsyncSession = Depends(get_db_session),
) -> UniverseStatsResponse:
    raw = await get_universe_stats(session)

    by_asset: dict[str, AssetStats] = {}
    for asset, data in raw["by_asset"].items():
        by_tf: dict[str, TimeframeStats] = {}
        for tf, counts in data["by_timeframe"].items():
            by_tf[tf] = TimeframeStats(
                active=counts.get("active", 0),
                upcoming=counts.get("upcoming", 0),
                expired=counts.get("expired", 0),
            )
        by_asset[asset] = AssetStats(total=data["total"], by_timeframe=by_tf)

    return UniverseStatsResponse(
        total=raw["total"],
        by_status=raw["by_status"],
        by_asset=by_asset,
        by_timeframe=raw["by_timeframe"],
    )


@router.post(
    "/sync",
    response_model=SyncResponse,
    summary="Trigger an immediate universe sync",
)
async def trigger_sync(request: Request) -> SyncResponse:
    """
    Runs a full universe sync right now.
    Uses the shared MarketUniverseService from app.state if available,
    otherwise creates a temporary one.
    """
    universe_service = getattr(request.app.state, "universe_service", None)

    if universe_service is not None:
        result = await universe_service.sync()
    else:
        from app.services.market_universe_service import MarketUniverseService
        svc = MarketUniverseService()
        try:
            result = await svc.sync()
        finally:
            await svc.close()

    return SyncResponse(**result)
