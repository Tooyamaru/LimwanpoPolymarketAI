from collections.abc import AsyncGenerator
from typing import Optional
from urllib.parse import urlparse

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
    """
    from sqlalchemy import text

    try:
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

            # Sprint 4: add classification count columns to discovery_runs
            # (table already existed from Sprint 3 without these columns)
            sprint4_migrations = [
                "ALTER TABLE discovery_runs ADD COLUMN IF NOT EXISTS updown_count INTEGER NOT NULL DEFAULT 0",
                "ALTER TABLE discovery_runs ADD COLUMN IF NOT EXISTS price_range_count INTEGER NOT NULL DEFAULT 0",
                "ALTER TABLE discovery_runs ADD COLUMN IF NOT EXISTS news_event_count INTEGER NOT NULL DEFAULT 0",
                "ALTER TABLE discovery_runs ADD COLUMN IF NOT EXISTS politics_count INTEGER NOT NULL DEFAULT 0",
                "ALTER TABLE discovery_runs ADD COLUMN IF NOT EXISTS other_count INTEGER NOT NULL DEFAULT 0",
            ]
            for stmt in sprint4_migrations:
                try:
                    await conn.execute(text(stmt))
                except Exception as col_exc:
                    logger.debug("Column migration skipped", stmt=stmt, error=str(col_exc))

            # Sprint 7: market_universe table is created by create_all above.
            # Add updated_at index for efficient stale-market queries if not present.
            sprint7_migrations = [
                "CREATE INDEX IF NOT EXISTS ix_market_universe_status ON market_universe (status)",
                "CREATE INDEX IF NOT EXISTS ix_market_universe_end_time ON market_universe (end_time)",
            ]
            for stmt in sprint7_migrations:
                try:
                    await conn.execute(text(stmt))
                except Exception as col_exc:
                    logger.debug("Sprint 7 migration skipped", stmt=stmt, error=str(col_exc))

            # Sprint 9: market_price_snapshots created by create_all above.
            # Add performance indexes for common query patterns.
            sprint9_migrations = [
                "CREATE INDEX IF NOT EXISTS ix_mps_condition_captured ON market_price_snapshots (condition_id, captured_at DESC)",
            ]
            for stmt in sprint9_migrations:
                try:
                    await conn.execute(text(stmt))
                except Exception as col_exc:
                    logger.debug("Sprint 9 migration skipped", stmt=stmt, error=str(col_exc))

            # Layer 8: positions table created by create_all above.
            # Indexes declared in the model; ensure status index is present for
            # the open-position filter that runs every 30 s.
            layer8_migrations = [
                "CREATE INDEX IF NOT EXISTS ix_position_status ON positions (status)",
                "CREATE INDEX IF NOT EXISTS ix_position_condition_id ON positions (condition_id)",
            ]
            for stmt in layer8_migrations:
                try:
                    await conn.execute(text(stmt))
                except Exception as col_exc:
                    logger.debug("Layer 8 migration skipped", stmt=stmt, error=str(col_exc))

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
