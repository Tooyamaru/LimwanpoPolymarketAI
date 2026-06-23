"""
Source validation response schemas — Sprint 5.
"""

from typing import Optional

from pydantic import BaseModel


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
