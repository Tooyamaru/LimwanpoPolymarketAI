from collections.abc import AsyncGenerator
from typing import Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config.settings import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class Base(DeclarativeBase):
    pass


# Lazy singletons — created on first use, not at import time
_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def _needs_ssl() -> bool:
    """Return True when the original DATABASE_URL referenced sslmode=require."""
    import os
    raw = os.environ.get("DATABASE_URL", "")
    return "sslmode=require" in raw or "sslmode=verify" in raw


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        connect_args: dict = {}
        if _needs_ssl():
            connect_args["ssl"] = True

        _engine = create_async_engine(
            settings.DATABASE_URL,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_timeout=settings.DB_POOL_TIMEOUT,
            pool_recycle=settings.DB_POOL_RECYCLE,
            pool_pre_ping=True,
            echo=settings.DEBUG,
            connect_args=connect_args,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_db_health() -> bool:
    from sqlalchemy import text

    try:
        factory = get_session_factory()
        async with factory() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.error("Database health check failed", error=str(exc))
        return False


async def init_db() -> None:
    """
    Create all tables, then apply additive column migrations for tables that
    already exist.  Uses ADD COLUMN IF NOT EXISTS so it is safe to run on
    every startup — it is a no-op when the column already exists.
    Each migration runs in its own savepoint so a failure doesn't abort the
    entire transaction.
    """
    import app.models  # noqa: F401 — ensure all ORM models are registered
    from sqlalchemy import text

    async def run_migration(conn, stmt: str, label: str) -> None:
        try:
            await conn.execute(text("SAVEPOINT _mig"))
            await conn.execute(text(stmt))
            await conn.execute(text("RELEASE SAVEPOINT _mig"))
        except Exception as exc:
            await conn.execute(text("ROLLBACK TO SAVEPOINT _mig"))
            logger.debug(f"{label} migration skipped", stmt=stmt, error=str(exc))

    try:
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

            # Sprint 4: add classification count columns to discovery_runs
            # (table already existed from Sprint 3 without these columns)
            all_migrations = [
                # Sprint 4: classification count columns on discovery_runs
                ("sprint4", "ALTER TABLE discovery_runs ADD COLUMN IF NOT EXISTS updown_count INTEGER NOT NULL DEFAULT 0"),
                ("sprint4", "ALTER TABLE discovery_runs ADD COLUMN IF NOT EXISTS price_range_count INTEGER NOT NULL DEFAULT 0"),
                ("sprint4", "ALTER TABLE discovery_runs ADD COLUMN IF NOT EXISTS news_event_count INTEGER NOT NULL DEFAULT 0"),
                ("sprint4", "ALTER TABLE discovery_runs ADD COLUMN IF NOT EXISTS politics_count INTEGER NOT NULL DEFAULT 0"),
                ("sprint4", "ALTER TABLE discovery_runs ADD COLUMN IF NOT EXISTS other_count INTEGER NOT NULL DEFAULT 0"),
                # Sprint 7: market_universe indexes
                ("sprint7", "CREATE INDEX IF NOT EXISTS ix_market_universe_status ON market_universe (status)"),
                ("sprint7", "CREATE INDEX IF NOT EXISTS ix_market_universe_end_time ON market_universe (end_time)"),
                # Sprint 9: price snapshot index
                ("sprint9", "CREATE INDEX IF NOT EXISTS ix_mps_condition_captured ON market_price_snapshots (condition_id, captured_at DESC)"),
                # Layer 8: positions indexes
                ("layer8", "CREATE INDEX IF NOT EXISTS ix_position_status ON positions (status)"),
                ("layer8", "CREATE INDEX IF NOT EXISTS ix_position_condition_id ON positions (condition_id)"),
                # Layer 9: risk_events indexes
                ("layer9", "CREATE INDEX IF NOT EXISTS ix_risk_event_result ON risk_events (result)"),
                ("layer9", "CREATE INDEX IF NOT EXISTS ix_risk_event_decision_id ON risk_events (decision_id)"),
                # Exit engine: trade_decisions columns
                ("exit_engine", "ALTER TABLE trade_decisions ADD COLUMN IF NOT EXISTS target_position_id INTEGER NULL"),
                ("exit_engine", "ALTER TABLE trade_decisions ADD COLUMN IF NOT EXISTS exit_reason VARCHAR(64) NULL"),
                ("exit_engine", "CREATE INDEX IF NOT EXISTS ix_td_target_position_id ON trade_decisions (target_position_id) WHERE target_position_id IS NOT NULL"),
                # Layer 13: position sizing
                ("layer13", "ALTER TABLE trade_decisions ADD COLUMN IF NOT EXISTS position_size_usdc DOUBLE PRECISION NULL"),
                # Layer 12: exit audit trail on positions
                ("layer12", "ALTER TABLE positions ADD COLUMN IF NOT EXISTS close_reason VARCHAR(64) NULL"),
                ("layer12", "ALTER TABLE positions ADD COLUMN IF NOT EXISTS exit_price DOUBLE PRECISION NULL"),
                ("layer12", "ALTER TABLE positions ADD COLUMN IF NOT EXISTS close_decision_id INTEGER NULL"),
                ("layer12", "ALTER TABLE positions ADD COLUMN IF NOT EXISTS close_order_id INTEGER NULL"),
            ]
            for label, stmt in all_migrations:
                await run_migration(conn, stmt, label)

        logger.info("Database tables initialised")
    except Exception as exc:
        logger.warning("Database init skipped — DB not reachable at startup", error=str(exc))


async def close_db() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
    logger.info("Database connection closed")
