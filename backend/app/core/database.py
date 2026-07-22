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
                # Phase 1 AI Signal Engine: confidence, regime, mtf_confirmed on signals
                ("signal_phase1", "ALTER TABLE signals ADD COLUMN IF NOT EXISTS confidence_score DOUBLE PRECISION NULL"),
                ("signal_phase1", "ALTER TABLE signals ADD COLUMN IF NOT EXISTS regime VARCHAR(16) NULL"),
                ("signal_phase1", "ALTER TABLE signals ADD COLUMN IF NOT EXISTS mtf_confirmed BOOLEAN NULL DEFAULT FALSE"),
                ("signal_phase1", "CREATE INDEX IF NOT EXISTS ix_signals_confidence ON signals (confidence_score)"),
                # Phase 4 Part D: fee simulation on orders
                ("phase4_fees", "ALTER TABLE orders ADD COLUMN IF NOT EXISTS entry_fee_usdc DOUBLE PRECISION NULL DEFAULT 0.0"),
                ("phase4_fees", "ALTER TABLE orders ADD COLUMN IF NOT EXISTS exit_fee_usdc DOUBLE PRECISION NULL DEFAULT 0.0"),
                # Phase 4 Part E: trailing stop on positions
                ("phase4_trailing", "ALTER TABLE positions ADD COLUMN IF NOT EXISTS peak_pnl_usdc DOUBLE PRECISION NULL"),
                # Phase 4 Part D: fee tracking on positions
                ("phase4_pos_fees", "ALTER TABLE positions ADD COLUMN IF NOT EXISTS total_fee_usdc DOUBLE PRECISION NULL DEFAULT 0.0"),
                # Phase 5: trade_evaluations table indexes (table created via metadata)
                ("phase5_te_idx", "CREATE INDEX IF NOT EXISTS ix_te_grade ON trade_evaluations (grade)"),
                ("phase5_te_idx2", "CREATE INDEX IF NOT EXISTS ix_te_quality_score ON trade_evaluations (quality_score)"),
                ("phase5_te_idx3", "CREATE INDEX IF NOT EXISTS ix_te_evaluated_at ON trade_evaluations (evaluated_at)"),
                # Phase Next: market reference (opening_price) on market_universe
                ("market_ref", "ALTER TABLE market_universe ADD COLUMN IF NOT EXISTS opening_price DOUBLE PRECISION NULL"),
                ("market_ref", "ALTER TABLE market_universe ADD COLUMN IF NOT EXISTS opening_price_source VARCHAR(32) NULL"),
                ("market_ref", "ALTER TABLE market_universe ADD COLUMN IF NOT EXISTS opening_price_timestamp TIMESTAMPTZ NULL"),
                ("market_ref", "ALTER TABLE market_universe ADD COLUMN IF NOT EXISTS reference_status VARCHAR(16) NULL DEFAULT 'PENDING'"),
                # Phase Next: Decision Engine evolution — Polymarket-first reasoning columns
                ("decision_v2", "ALTER TABLE decision_logs ADD COLUMN IF NOT EXISTS market_quality_score DOUBLE PRECISION NULL"),
                ("decision_v2", "ALTER TABLE decision_logs ADD COLUMN IF NOT EXISTS market_quality VARCHAR(16) NULL"),
                ("decision_v2", "ALTER TABLE decision_logs ADD COLUMN IF NOT EXISTS market_confidence DOUBLE PRECISION NULL"),
                ("decision_v2", "ALTER TABLE decision_logs ADD COLUMN IF NOT EXISTS market_risk VARCHAR(16) NULL"),
                ("decision_v2", "ALTER TABLE decision_logs ADD COLUMN IF NOT EXISTS market_context_status VARCHAR(16) NULL"),
                ("decision_v2", "ALTER TABLE decision_logs ADD COLUMN IF NOT EXISTS market_context_confidence DOUBLE PRECISION NULL"),
                ("decision_v2", "ALTER TABLE decision_logs ADD COLUMN IF NOT EXISTS orderbook_direction VARCHAR(16) NULL"),
                ("decision_v2", "ALTER TABLE decision_logs ADD COLUMN IF NOT EXISTS orderbook_confidence DOUBLE PRECISION NULL"),
                ("decision_v2", "ALTER TABLE decision_logs ADD COLUMN IF NOT EXISTS funding_direction VARCHAR(16) NULL"),
                ("decision_v2", "ALTER TABLE decision_logs ADD COLUMN IF NOT EXISTS funding_confidence DOUBLE PRECISION NULL"),
                ("decision_v2", "ALTER TABLE decision_logs ADD COLUMN IF NOT EXISTS news_sentiment VARCHAR(16) NULL"),
                ("decision_v2", "ALTER TABLE decision_logs ADD COLUMN IF NOT EXISTS news_confidence DOUBLE PRECISION NULL"),
                ("decision_v2", "ALTER TABLE decision_logs ADD COLUMN IF NOT EXISTS supporting_engines TEXT NULL"),
                ("decision_v2", "CREATE INDEX IF NOT EXISTS ix_market_quality_condition_id ON market_quality_scores (condition_id)"),
                ("market_behaviour", "ALTER TABLE market_quality_scores ADD COLUMN IF NOT EXISTS market_behaviours TEXT NULL"),
                # Phase Next — Decision Engine Intelligence Upgrade
                # Phase 1: Consensus Engine
                ("decision_intelligence", "ALTER TABLE decision_logs ADD COLUMN IF NOT EXISTS consensus_score DOUBLE PRECISION NULL"),
                ("decision_intelligence", "ALTER TABLE decision_logs ADD COLUMN IF NOT EXISTS agreement_level DOUBLE PRECISION NULL"),
                ("decision_intelligence", "ALTER TABLE decision_logs ADD COLUMN IF NOT EXISTS conflict_detected BOOLEAN NULL"),
                # Phase 3: Entry Quality Engine
                ("decision_intelligence", "ALTER TABLE decision_logs ADD COLUMN IF NOT EXISTS entry_quality_score DOUBLE PRECISION NULL"),
                # Phase 8: stats index for fast conflict/consensus queries
                ("decision_intelligence", "CREATE INDEX IF NOT EXISTS ix_decision_conflict ON decision_logs (conflict_detected)"),
                # Priority 1: Outcome Learning — indexes (table created via metadata)
                ("outcome_learning", "CREATE INDEX IF NOT EXISTS ix_ol_evaluated_at ON outcome_learnings (evaluated_at)"),
                ("outcome_learning", "CREATE INDEX IF NOT EXISTS ix_ol_correct ON outcome_learnings (correct)"),
                ("outcome_learning", "CREATE INDEX IF NOT EXISTS ix_ol_prediction ON outcome_learnings (prediction)"),
                # Priority 2: Engine Performance Stats — indexes (table created via metadata)
                ("engine_performance", "CREATE INDEX IF NOT EXISTS ix_ep_accuracy ON engine_performance_stats (accuracy)"),
                # Priority 3: Engine Weights — indexes (table created via metadata)
                ("engine_weights", "CREATE INDEX IF NOT EXISTS ix_ew_last_adjusted ON engine_weights (last_adjusted_at)"),
                # Phase 9D: Direct Polymarket resolution fields on outcome_learnings
                ("phase9d_resolution", "ALTER TABLE outcome_learnings ADD COLUMN IF NOT EXISTS outcome_source VARCHAR(64) NULL"),
                ("phase9d_resolution", "ALTER TABLE outcome_learnings ADD COLUMN IF NOT EXISTS winning_side VARCHAR(8) NULL"),
                ("phase9d_resolution", "ALTER TABLE outcome_learnings ADD COLUMN IF NOT EXISTS winning_token_id VARCHAR(256) NULL"),
                ("phase9d_resolution", "ALTER TABLE outcome_learnings ADD COLUMN IF NOT EXISTS final_yes_price DOUBLE PRECISION NULL"),
                ("phase9d_resolution", "ALTER TABLE outcome_learnings ADD COLUMN IF NOT EXISTS final_no_price DOUBLE PRECISION NULL"),
                ("phase9d_resolution", "ALTER TABLE outcome_learnings ADD COLUMN IF NOT EXISTS resolution_note TEXT NULL"),
                ("phase9d_resolution", "CREATE INDEX IF NOT EXISTS ix_ol_outcome_source ON outcome_learnings (outcome_source)"),
                ("phase9d_resolution", "CREATE INDEX IF NOT EXISTS ix_ol_winning_side ON outcome_learnings (winning_side)"),
                # Timestamp-slug discovery: prediction window stored on market_universe
                ("pw_discovery", "ALTER TABLE market_universe ADD COLUMN IF NOT EXISTS prediction_window_start TIMESTAMPTZ NULL"),
                ("pw_discovery", "ALTER TABLE market_universe ADD COLUMN IF NOT EXISTS prediction_window_end TIMESTAMPTZ NULL"),
                ("pw_discovery", "ALTER TABLE market_universe ADD COLUMN IF NOT EXISTS prediction_window_source VARCHAR(32) NULL"),
                ("pw_discovery", "ALTER TABLE market_universe ADD COLUMN IF NOT EXISTS prediction_window_validated_at TIMESTAMPTZ NULL"),
                ("pw_discovery", "CREATE INDEX IF NOT EXISTS ix_mu_pw_start ON market_universe (prediction_window_start)"),
                ("pw_discovery", "CREATE INDEX IF NOT EXISTS ix_mu_pw_end ON market_universe (prediction_window_end)"),
                # event_slug — exact rolling 5m event identity persisted on upsert
                ("event_slug_persist", "ALTER TABLE market_universe ADD COLUMN IF NOT EXISTS event_slug VARCHAR(128) NULL"),
                ("event_slug_persist", "CREATE INDEX IF NOT EXISTS ix_mu_event_slug ON market_universe (event_slug)"),
                # Phase 10: authoritative forced-expiry exit price carried from
                # ExitEngine to ExecutionEngine (fixes stale-price close bug)
                ("phase10_forced_exit", "ALTER TABLE trade_decisions ADD COLUMN IF NOT EXISTS forced_exit_price DOUBLE PRECISION NULL"),
                # Multi-entry / multi-exit per market: lot bookkeeping on positions
                ("multi_lot", "ALTER TABLE positions ADD COLUMN IF NOT EXISTS remaining_quantity DOUBLE PRECISION NULL"),
                ("multi_lot", "ALTER TABLE positions ADD COLUMN IF NOT EXISTS entry_sequence INTEGER NULL"),
                ("multi_lot", "ALTER TABLE positions ADD COLUMN IF NOT EXISTS scale_in_reason VARCHAR(32) NULL"),
                # Backfill existing rows: remaining_quantity mirrors quantity for OPEN,
                # 0 for CLOSED (best-effort — pre-existing CLOSED rows have no lot left).
                ("multi_lot", "UPDATE positions SET remaining_quantity = CASE WHEN status = 'CLOSED' THEN 0 ELSE quantity END WHERE remaining_quantity IS NULL"),
                ("multi_lot", "UPDATE positions SET entry_sequence = 1 WHERE entry_sequence IS NULL"),
                ("multi_lot", "CREATE INDEX IF NOT EXISTS ix_position_condition_status ON positions (condition_id, status)"),
                # Chainlink RTDS — target / Price to Beat fields on market_universe
                ("chainlink_target", "ALTER TABLE market_universe ADD COLUMN IF NOT EXISTS target_price DOUBLE PRECISION NULL"),
                ("chainlink_target", "ALTER TABLE market_universe ADD COLUMN IF NOT EXISTS target_source VARCHAR(64) NULL"),
                ("chainlink_target", "ALTER TABLE market_universe ADD COLUMN IF NOT EXISTS target_raw_source VARCHAR(256) NULL"),
                ("chainlink_target", "ALTER TABLE market_universe ADD COLUMN IF NOT EXISTS target_source_timestamp TIMESTAMPTZ NULL"),
                ("chainlink_target", "ALTER TABLE market_universe ADD COLUMN IF NOT EXISTS target_locked_at TIMESTAMPTZ NULL"),
                ("chainlink_target", "ALTER TABLE market_universe ADD COLUMN IF NOT EXISTS target_event_slug VARCHAR(128) NULL"),
                ("chainlink_target", "ALTER TABLE market_universe ADD COLUMN IF NOT EXISTS target_condition_id VARCHAR(256) NULL"),
                ("chainlink_target", "ALTER TABLE market_universe ADD COLUMN IF NOT EXISTS target_verified BOOLEAN NOT NULL DEFAULT FALSE"),
                ("chainlink_target", "ALTER TABLE market_universe ADD COLUMN IF NOT EXISTS target_stale BOOLEAN NOT NULL DEFAULT TRUE"),
                ("chainlink_target", "ALTER TABLE market_universe ADD COLUMN IF NOT EXISTS target_validation_error VARCHAR(512) NULL"),
                ("chainlink_target", "CREATE INDEX IF NOT EXISTS ix_mu_target_verified ON market_universe (target_verified)"),
                # Target reconciliation diagnostics (spec §5 / §10)
                ("target_reconcile", "ALTER TABLE market_universe ADD COLUMN IF NOT EXISTS target_candidate_rule VARCHAR(64) NULL"),
                ("target_reconcile", "ALTER TABLE market_universe ADD COLUMN IF NOT EXISTS target_official_comparison_value DOUBLE PRECISION NULL"),
                ("target_reconcile", "ALTER TABLE market_universe ADD COLUMN IF NOT EXISTS target_difference DOUBLE PRECISION NULL"),
                ("target_reconcile", "ALTER TABLE market_universe ADD COLUMN IF NOT EXISTS target_retry_count INTEGER NOT NULL DEFAULT 0"),
                ("target_reconcile", "ALTER TABLE market_universe ADD COLUMN IF NOT EXISTS target_last_attempt_at TIMESTAMPTZ NULL"),
                ("target_reconcile", "ALTER TABLE market_universe ADD COLUMN IF NOT EXISTS target_next_attempt_at TIMESTAMPTZ NULL"),
                ("target_reconcile", "ALTER TABLE market_universe ADD COLUMN IF NOT EXISTS target_last_error VARCHAR(512) NULL"),
                # Official PTB API source traceability (Priority 0)
                ("ptb_source_trace", "ALTER TABLE market_universe ADD COLUMN IF NOT EXISTS target_source_url VARCHAR(1024) NULL"),
                ("ptb_source_trace", "ALTER TABLE market_universe ADD COLUMN IF NOT EXISTS target_source_field_path VARCHAR(64) NULL"),
                # Phase A: window binding — event slug + prediction window on trade_decisions
                ("window_binding", "ALTER TABLE trade_decisions ADD COLUMN IF NOT EXISTS decision_event_slug VARCHAR(128) NULL"),
                ("window_binding", "ALTER TABLE trade_decisions ADD COLUMN IF NOT EXISTS decision_prediction_window_start TIMESTAMPTZ NULL"),
                ("window_binding", "ALTER TABLE trade_decisions ADD COLUMN IF NOT EXISTS decision_prediction_window_end TIMESTAMPTZ NULL"),
                # 14A2A: exact-side CLOB fields on opportunities
                ("14a2a_opp", "ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS no_bid DOUBLE PRECISION NULL"),
                ("14a2a_opp", "ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS no_ask DOUBLE PRECISION NULL"),
                ("14a2a_opp", "ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS clob_fetched_at TIMESTAMPTZ NULL"),
                # 14A2A: exact-side audit fields on trade_decisions
                ("14a2a_td", "ALTER TABLE trade_decisions ADD COLUMN IF NOT EXISTS no_mid DOUBLE PRECISION NULL"),
                ("14a2a_td", "ALTER TABLE trade_decisions ADD COLUMN IF NOT EXISTS no_bid DOUBLE PRECISION NULL"),
                ("14a2a_td", "ALTER TABLE trade_decisions ADD COLUMN IF NOT EXISTS no_ask DOUBLE PRECISION NULL"),
                ("14a2a_td", "ALTER TABLE trade_decisions ADD COLUMN IF NOT EXISTS spread_no DOUBLE PRECISION NULL"),
                ("14a2a_td", "ALTER TABLE trade_decisions ADD COLUMN IF NOT EXISTS clob_fetched_at TIMESTAMPTZ NULL"),
                ("14a2a_td", "ALTER TABLE trade_decisions ADD COLUMN IF NOT EXISTS selected_token_id VARCHAR(256) NULL"),
                ("14a2a_td", "ALTER TABLE trade_decisions ADD COLUMN IF NOT EXISTS selected_price_source VARCHAR(32) NULL"),
                # 14A2A: exact token traceability on orders
                ("14a2a_ord", "ALTER TABLE orders ADD COLUMN IF NOT EXISTS token_id VARCHAR(256) NULL"),
                ("14a2a_ord", "ALTER TABLE orders ADD COLUMN IF NOT EXISTS price_source VARCHAR(32) NULL"),
                ("14a2a_ord", "ALTER TABLE orders ADD COLUMN IF NOT EXISTS clob_fetched_at TIMESTAMPTZ NULL"),
            ]
            for label, stmt in all_migrations:
                await run_migration(conn, stmt, label)

        logger.info("Database tables initialised")
    except Exception as exc:
        logger.error("Database init failed — cannot start without database", error=str(exc))
        raise RuntimeError(f"Database initialisation failed: {exc}") from exc


async def close_db() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
    logger.info("Database connection closed")
