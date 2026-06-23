"""
Orders router — Layer 7: Execution Engine (Paper Mode).

GET /orders          — all orders (newest first)
GET /orders/open     — orders with status PENDING
GET /orders/stats    — aggregate fill counts and average prices
GET /orders/{id}     — single order detail
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.services import order_repository as repo

logger = get_logger(__name__)

router = APIRouter(prefix="/orders", tags=["orders"])


# ── Response schemas ───────────────────────────────────────────────────────────

class OrderResponse(BaseModel):
    id: int
    decision_id: int
    condition_id: str
    asset: str
    timeframe: str

    side: str
    order_type: str
    quantity: float

    requested_price: Optional[float]
    filled_price: Optional[float]

    status: str
    created_at: datetime
    filled_at: Optional[datetime]

    model_config = {"from_attributes": True}


class OrderStatsResponse(BaseModel):
    total_orders: int
    filled: int
    pending: int
    cancelled: int
    failed: int
    long_yes_filled: int
    long_no_filled: int
    avg_fill_price_yes: float
    avg_fill_price_no: float


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("", response_model=list[OrderResponse])
async def get_orders(
    status: Optional[str] = Query(
        default=None,
        description="Filter by status: PENDING | FILLED | CANCELLED | FAILED",
    ),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
):
    """Return all orders, newest first. Optionally filter by status."""
    rows = await repo.get_orders(session, status_filter=status, limit=limit)
    return [OrderResponse.model_validate(r) for r in rows]


@router.get("/open", response_model=list[OrderResponse])
async def get_open_orders(
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db_session),
):
    """Return all orders with status PENDING."""
    rows = await repo.get_open_orders(session, limit=limit)
    return [OrderResponse.model_validate(r) for r in rows]


@router.get("/stats", response_model=OrderStatsResponse)
async def get_order_stats(
    session: AsyncSession = Depends(get_db_session),
):
    """Return aggregate order statistics grouped by status and side."""
    stats = await repo.get_order_stats(session)
    return OrderStatsResponse(**stats)


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    """Return a single order by its ID."""
    order = await repo.get_order(session, order_id)
    if order is None:
        raise HTTPException(
            status_code=404,
            detail=f"Order id={order_id} not found",
        )
    return OrderResponse.model_validate(order)
