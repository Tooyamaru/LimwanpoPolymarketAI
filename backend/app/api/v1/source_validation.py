"""
Source Validation API — Sprint 5.

Answers: "Can we reliably discover the exact BTC/ETH/SOL/XRP Up-or-Down market family?"

Endpoints:
    GET  /api/v1/source-validation          Diagnostics: source name + total stored
    GET  /api/v1/source-validation/search   Free-text search on stored markets
    GET  /api/v1/source-validation/audit    All Up/Down candidate markets
    POST /api/v1/source-validation/run      Trigger a fresh validation scan
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.services.source_validator import (
    SourceValidatorService,
    get_audit_results,
    get_total_stored,
    save_validation_run,
    search_results,
)

router = APIRouter(prefix="/source-validation", tags=["source-validation"])
logger = get_logger(__name__)


# ── Response models ───────────────────────────────────────────────────────────

class DiagnosticsResponse(BaseModel):
    source: str
    markets: int


class SearchResult(BaseModel):
    title: str
    slug: Optional[str]
    market_id: str
    event_id: Optional[str]


class AuditResult(BaseModel):
    run_id: str
    source_endpoint: str
    source_market_id: str
    condition_id: str
    source_event_id: Optional[str]
    title: str
    slug: Optional[str]
    detected_asset: Optional[str]
    detected_timeframe: Optional[str]
    is_updown_candidate: bool
    updown_keywords_found: Optional[str]
    matching_rule: Optional[str]


class ValidationRunResponse(BaseModel):
    run_id: str
    run_at: str
    source: str
    total_scanned: int
    total_asset_matched: int
    total_updown_candidates: int
    btc_candidates: int
    eth_candidates: int
    sol_candidates: int
    xrp_candidates: int


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=DiagnosticsResponse,
    summary="Source diagnostics: source name and total stored markets",
)
async def get_diagnostics(
    session: AsyncSession = Depends(get_db_session),
) -> DiagnosticsResponse:
    """Return the source identifier and the total count of stored validation results."""
    total = await get_total_stored(session)
    return DiagnosticsResponse(source="clob", markets=total)


@router.get(
    "/search",
    response_model=list[SearchResult],
    summary="Free-text search across stored source validation markets",
)
async def search_markets(
    q: str = Query(..., min_length=1, description="Search term (title or slug)"),
    limit: int = Query(100, ge=1, le=500, description="Maximum results to return"),
    session: AsyncSession = Depends(get_db_session),
) -> list[SearchResult]:
    """
    Search stored source validation results by market title or slug.

    Returns title, slug, market_id, and event_id for each match.
    """
    rows = await search_results(session, q, limit=limit)
    return [
        SearchResult(
            title=r.title,
            slug=r.slug,
            market_id=r.source_market_id,
            event_id=r.source_event_id,
        )
        for r in rows
    ]


@router.get(
    "/audit",
    response_model=list[AuditResult],
    summary="All Up/Down candidate markets — no filtering",
)
async def get_audit(
    limit: int = Query(1000, ge=1, le=5000, description="Maximum results to return"),
    session: AsyncSession = Depends(get_db_session),
) -> list[AuditResult]:
    """
    Return all markets flagged as Up/Down candidates from source validation.

    No asset or timeframe filtering is applied — every candidate is included
    so the caller can audit the full discovery surface area.
    """
    rows = await get_audit_results(session, limit=limit)
    return [
        AuditResult(
            run_id=r.run_id,
            source_endpoint=r.source_endpoint,
            source_market_id=r.source_market_id,
            condition_id=r.condition_id,
            source_event_id=r.source_event_id,
            title=r.title,
            slug=r.slug,
            detected_asset=r.detected_asset,
            detected_timeframe=r.detected_timeframe,
            is_updown_candidate=r.is_updown_candidate,
            updown_keywords_found=r.updown_keywords_found,
            matching_rule=r.matching_rule,
        )
        for r in rows
    ]


@router.post(
    "/run",
    response_model=ValidationRunResponse,
    summary="Trigger a fresh source validation scan",
    status_code=202,
)
async def run_validation(
    session: AsyncSession = Depends(get_db_session),
) -> ValidationRunResponse:
    """
    Fetch all active Polymarket markets, apply the exact matcher, and
    store source tracing results in ``source_validation_results``.

    This endpoint performs a live paginated scan (~250 pages) and may take
    several minutes to complete.
    """
    svc = SourceValidatorService()
    try:
        run = await svc.validate()
        await save_validation_run(session, run)
    except Exception as exc:
        logger.error("Source validation run failed", error=str(exc))
        raise HTTPException(status_code=500, detail=f"Validation scan failed: {exc}")
    finally:
        await svc.close()

    return ValidationRunResponse(**run.as_dict())
