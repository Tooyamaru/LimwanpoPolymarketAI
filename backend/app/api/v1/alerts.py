"""
Alerts router — Phase 12: Monitoring / Alert / Operator Safety System.

GET /alerts/summary — read-only alert snapshot derived from real DB state,
engine heartbeats, and configured thresholds. Never mutates the database,
never triggers a trade or execution, never exposes secrets.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.schemas.alert import AlertSnapshot
from app.services.alert_service import AlertService

logger = get_logger(__name__)

router = APIRouter(prefix="/alerts", tags=["alerts"])

_service = AlertService()


@router.get("/summary", response_model=AlertSnapshot, summary="Read-only operator alert snapshot")
async def get_alert_summary(
    session: AsyncSession = Depends(get_db_session),
) -> AlertSnapshot:
    snapshot = await _service.snapshot(session)
    return AlertSnapshot(**snapshot)
