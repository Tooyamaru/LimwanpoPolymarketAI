"""
Feed repository — Phase 5: Source Stabilization.

Builds a real, chronological "AI Activity" feed strictly from rows the
engines themselves already write: Signal (Layer 4), RiskEvent (Layer 9),
and DecisionLog (Decision Engine). No fabricated, random, or hardcoded
events — every line traces back to an actual database row and timestamp.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.decision_log import DecisionLog
from app.models.risk_event import RiskEvent
from app.models.signal import Signal


async def get_recent_events(session: AsyncSession, limit: int = 8) -> list[dict]:
    """
    Return the most recent `limit` real engine events, merged and sorted
    chronologically (most recent first) across Signal, RiskEvent, and
    DecisionLog tables.
    """
    events: list[dict] = []

    sig_rows = (
        await session.execute(
            select(Signal).order_by(Signal.detected_at.desc()).limit(limit)
        )
    ).scalars().all()
    for s in sig_rows:
        conf = f" · confidence {s.confidence_score:.0f}%" if s.confidence_score is not None else ""
        events.append(
            {
                "tag": "SIGNAL",
                "message": f"{s.asset}/{s.timeframe} {s.signal_type} detected{conf}",
                "timestamp": s.detected_at,
            }
        )

    risk_rows = (
        await session.execute(
            select(RiskEvent).order_by(RiskEvent.checked_at.desc()).limit(limit)
        )
    ).scalars().all()
    for r in risk_rows:
        outcome = "allowed" if r.result == "ALLOW" else f"blocked ({r.reason})"
        events.append(
            {
                "tag": "RISK",
                "message": (
                    f"{r.asset}/{r.timeframe} prediction {outcome} — "
                    f"{r.open_positions_count} active prediction(s)"
                ),
                "timestamp": r.checked_at,
            }
        )

    dec_rows = (
        await session.execute(
            select(DecisionLog).order_by(DecisionLog.created_at.desc()).limit(limit)
        )
    ).scalars().all()
    for d in dec_rows:
        events.append(
            {
                "tag": "DECISION",
                "message": (
                    f"{d.asset}/{d.timeframe} decision engine → {d.decision} "
                    f"· confidence {d.confidence:.0f}%"
                ),
                "timestamp": d.created_at,
            }
        )

    # Priority ordering: Decision (0) → Risk (1) → Signal (2).
    # Within the same priority tier, most-recent first.
    # This ensures Decision Engine output is always surfaced above risk blocks
    # and signal noise, even when all events share the same timestamp.
    _PRIORITY = {"DECISION": 0, "RISK": 1, "SIGNAL": 2}
    events.sort(
        key=lambda e: (
            _PRIORITY.get(e["tag"], 99),
            -(e["timestamp"].timestamp()),
        )
    )
    return events[:limit]
