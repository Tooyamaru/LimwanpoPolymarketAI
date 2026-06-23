"""
Event classification repository tests — Sprint 4.

Uses in-memory SQLite (aiosqlite) for full isolation.
"""

import pytest
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

import app.models
from app.core.database import Base
from app.repositories.event_classification_repository import (
    save_classification,
    get_classifications,
    get_classification_db_stats,
)
from app.services.event_classifier import EventType

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="function")
async def db_session():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


def _now():
    return datetime.now(timezone.utc)


async def _save(session, market_id="mkt-001", event_type=EventType.UPDOWN.value,
                confidence=0.95, rule="updown_phrase", title="BTC Up or Down 5m"):
    return await save_classification(
        session,
        market_id=market_id,
        raw_title=title,
        event_type=event_type,
        confidence=confidence,
        matched_rule=rule,
        created_at=_now(),
    )


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_save_creates_row(db_session):
    row = await _save(db_session)
    await db_session.commit()
    assert row.id is not None
    assert row.event_type == EventType.UPDOWN.value
    assert row.confidence == 0.95


@pytest.mark.anyio
async def test_save_idempotent(db_session):
    r1 = await _save(db_session, market_id="dupe-001")
    await db_session.commit()

    r2 = await _save(db_session, market_id="dupe-001", confidence=0.80)
    await db_session.commit()

    assert r1.id == r2.id
    assert r2.confidence == 0.80  # updated


@pytest.mark.anyio
async def test_save_stores_transparency(db_session):
    row = await save_classification(
        db_session,
        market_id="trans-001",
        raw_title="ETH Up or Down 15m",
        event_type=EventType.UPDOWN.value,
        confidence=0.95,
        matched_rule="updown_phrase",
        created_at=_now(),
    )
    await db_session.commit()
    assert row.raw_title == "ETH Up or Down 15m"
    assert row.matched_rule == "updown_phrase"
    assert row.market_id == "trans-001"


@pytest.mark.anyio
async def test_get_classifications_all(db_session):
    await _save(db_session, "m1", EventType.UPDOWN.value)
    await _save(db_session, "m2", EventType.PRICE_RANGE.value)
    await db_session.commit()

    rows = await get_classifications(db_session)
    assert len(rows) == 2


@pytest.mark.anyio
async def test_get_classifications_filtered(db_session):
    await _save(db_session, "m1", EventType.UPDOWN.value)
    await _save(db_session, "m2", EventType.PRICE_RANGE.value)
    await _save(db_session, "m3", EventType.POLITICS.value)
    await db_session.commit()

    updown = await get_classifications(db_session, event_type=EventType.UPDOWN.value)
    assert len(updown) == 1
    assert updown[0].market_id == "m1"


@pytest.mark.anyio
async def test_stats_counts(db_session):
    await _save(db_session, "u1", EventType.UPDOWN.value)
    await _save(db_session, "u2", EventType.UPDOWN.value)
    await _save(db_session, "p1", EventType.PRICE_RANGE.value)
    await _save(db_session, "n1", EventType.NEWS_EVENT.value)
    await db_session.commit()

    stats = await get_classification_db_stats(db_session)
    assert stats["total"] == 4
    assert stats["updown"] == 2
    assert stats["price_range"] == 1
    assert stats["news_event"] == 1
    assert stats["politics"] == 0
    assert stats["other"] == 0


@pytest.mark.anyio
async def test_stats_empty(db_session):
    stats = await get_classification_db_stats(db_session)
    assert stats["total"] == 0
    assert all(v == 0 for k, v in stats.items() if k != "total")


@pytest.mark.anyio
async def test_default_created_at(db_session):
    row = await save_classification(
        db_session,
        market_id="no-ts-001",
        raw_title="Test",
        event_type=EventType.OTHER.value,
        confidence=1.0,
        matched_rule="no_rule_matched",
    )
    await db_session.commit()
    assert row.created_at is not None
