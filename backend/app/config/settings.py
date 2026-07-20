from functools import lru_cache
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    APP_NAME: str = "Polymarket Quant Bot"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    DEBUG: bool = False

    # ── 5M-ONLY active market configuration (central source of truth) ──────────
    # All entry pipelines (universe sync, signal, opportunity, strategy, decision)
    # must read these values.  Exit Engine ignores these — it processes ALL open
    # positions regardless of timeframe to safely close legacy lots.
    ENABLED_ASSETS: list[str] = ["BTC", "ETH", "SOL", "XRP"]
    ENABLED_TIMEFRAME: str = "5m"

    # API
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/polymarket"
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_POOL_SIZE: int = 10
    REDIS_DECODE_RESPONSES: bool = True

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    # CORS
    ALLOWED_ORIGINS: list[str] = ["*"]

    # Universe sync (Gamma Series — Sprint 7)
    UNIVERSE_SYNC_INTERVAL_SECONDS: int = 60
    UNIVERSE_SYNC_ENABLED: bool = True
    UNIVERSE_SYNC_RUN_ON_STARTUP: bool = True

    # Price refresh (CLOB market data — Sprint 9)
    PRICE_REFRESH_SECONDS: int = 10
    PRICE_REFRESH_ENABLED: bool = True
    PRICE_REFRESH_RUN_ON_STARTUP: bool = True

    # Signal engine (Layer 4)
    SIGNAL_ENGINE_ENABLED: bool = True
    SIGNAL_ENGINE_INTERVAL_SECONDS: int = 10
    SIGNAL_ENGINE_RUN_ON_STARTUP: bool = True

    # Opportunity engine (Layer 5)
    OPPORTUNITY_ENGINE_ENABLED: bool = True
    OPPORTUNITY_ENGINE_INTERVAL_SECONDS: int = 30
    OPPORTUNITY_ENGINE_RUN_ON_STARTUP: bool = True

    # Opportunity Engine — scoring constants (Phase 9B: moved out of
    # opportunity_engine.py inline literals; values unchanged, same formulas).
    OPPORTUNITY_SEED_PRICE: float = 0.50
    OPPORTUNITY_DIRECTION_THRESHOLD: float = 0.005   # ±0.5% from seed triggers directional hint

    # score_mid_movement (0-30): min(CAP, |yes_mid - SEED_PRICE| * MULTIPLIER)
    OPPORTUNITY_MID_MOVEMENT_CAP: float = 30.0
    OPPORTUNITY_MID_MOVEMENT_MULTIPLIER: float = 600.0

    # score_spread (0-20): max(0, min(CAP, (THRESHOLD - spread_yes) * MULTIPLIER))
    OPPORTUNITY_SPREAD_CAP: float = 20.0
    OPPORTUNITY_SPREAD_THRESHOLD: float = 0.02
    OPPORTUNITY_SPREAD_MULTIPLIER: float = 2000.0

    # score_depth_imbalance (0-20): min(CAP, |spread_no - spread_yes| * MULTIPLIER)
    OPPORTUNITY_DEPTH_IMBALANCE_CAP: float = 20.0
    OPPORTUNITY_DEPTH_IMBALANCE_MULTIPLIER: float = 2000.0

    # score_signal_activity (0-20): tiered base by signal_count, + HIGH-severity bonus
    OPPORTUNITY_SIGNAL_ACTIVITY_CAP: float = 20.0
    OPPORTUNITY_SIGNAL_TIER1_COUNT: int = 1      # signal_count == 1
    OPPORTUNITY_SIGNAL_TIER1_SCORE: float = 10.0
    OPPORTUNITY_SIGNAL_TIER2_COUNT: int = 3      # signal_count <= 3
    OPPORTUNITY_SIGNAL_TIER2_SCORE: float = 15.0
    OPPORTUNITY_SIGNAL_TIER3_SCORE: float = 20.0  # signal_count > 3
    OPPORTUNITY_SIGNAL_HIGH_SEVERITY_BONUS: float = 3.0
    OPPORTUNITY_SIGNAL_HIGH_SEVERITY_BONUS_CAP: float = 5.0

    # score_discovery (0-10): tiered by minutes_to_expiry
    OPPORTUNITY_DISCOVERY_TIER_15M: float = 10.0
    OPPORTUNITY_DISCOVERY_TIER_30M: float = 8.0
    OPPORTUNITY_DISCOVERY_TIER_60M: float = 6.0
    OPPORTUNITY_DISCOVERY_TIER_120M: float = 4.0
    OPPORTUNITY_DISCOVERY_TIER_360M: float = 2.0
    OPPORTUNITY_DISCOVERY_TIER_DEFAULT: float = 1.0

    # Strategy engine (Layer 6)
    STRATEGY_ENGINE_ENABLED: bool = True
    STRATEGY_ENGINE_INTERVAL_SECONDS: int = 60
    STRATEGY_ENGINE_RUN_ON_STARTUP: bool = True
    STRATEGY_PERSIST_SKIPS: bool = False

    # Strategy engine entry gate thresholds — moved here from strategy_engine.py
    # for transparency.  These values are intentionally calibrated for the
    # Polymarket AMM-init phase, where market mid-prices sit near 0.50 and
    # CLOB depth/spread variance is minimal (no human trades yet).
    #
    # This is NOT a risk bypass.  The Risk Engine (Layer 9) remains the
    # primary hard gate on every open-long decision.  These thresholds only
    # determine whether an opportunity score and signal are worth sending to
    # the Risk Engine at all.
    #
    # SCORE_OPEN:            lowered 40.0 → 30.0  (max achievable in AMM-init ≈ 34)
    # MIN_SIGNAL_CONFIDENCE: lowered 25.0 → 20.0  (AMM-init signals average ~23.5)
    #
    # REVIEW REQUIRED when live CLOB data shows spread/depth/signal variance
    # consistent with human-traded markets.
    STRATEGY_SCORE_OPEN: float = 30.0
    STRATEGY_SCORE_WATCH: float = 20.0
    STRATEGY_SPREAD_THRESHOLD: float = 0.02
    STRATEGY_MIN_SIGNAL_CONFIDENCE: float = 20.0
    STRATEGY_MIN_SIGNAL_CONFIDENCE_MTF: float = 15.0
    # Documentation flags — do not alter production behaviour.
    # True = thresholds currently reflect AMM-init calibration, not mature-market targets.
    STRATEGY_AMM_INIT_MODE_ACTIVE: bool = True
    # True = entry gate values should be re-reviewed once CLOB data is more
    # variated (wider spreads, deeper books, human-driven signal divergence).
    STRATEGY_ENTRY_GATE_REVIEW_REQUIRED: bool = True

    # Execution engine (Layer 7)
    EXECUTION_ENGINE_ENABLED: bool = True
    EXECUTION_ENGINE_INTERVAL_SECONDS: int = 30
    EXECUTION_ENGINE_RUN_ON_STARTUP: bool = True
    EXECUTION_PAPER_MODE: bool = True

    # Position tracking (Layer 8)
    POSITION_TRACKING_INTERVAL_SECONDS: int = 30

    # Risk engine (Layer 9)
    RISK_ENGINE_ENABLED: bool = True
    RISK_ENGINE_INTERVAL_SECONDS: int = 15
    RISK_ENGINE_RUN_ON_STARTUP: bool = True
    MAX_POSITION_SIZE: float = 1.0
    MAX_DAILY_LOSS: float = -50.0
    # Position count is UNLIMITED — entries are gated only by USDC exposure and
    # available capital.  A high daily-trades ceiling prevents rate limiting while
    # still offering an emergency brake during runaway conditions.
    MAX_DAILY_TRADES: int = 500

    # Portfolio risk management (Layer 14)
    # Count-based position limits removed (Phase 12L: unlimited position count).
    # Entry is governed exclusively by USDC exposure caps and capital availability.
    PORTFOLIO_MAX_EXPOSURE_USDC: float = 200.0
    PORTFOLIO_MAX_PER_ASSET_USDC: float = 100.0

    # ── Multi-entry per market (RESUME CARD PNL spec) ──────────────────────────
    # Count caps (MAX_ENTRIES_PER_MARKET, MAX_OPEN_LOTS_PER_MARKET,
    # MAX_SAME_SIDE_ENTRIES) removed — position count is unlimited.
    # The following USDC-based and spam-protection guards remain mandatory.
    MAX_EXPOSURE_PER_MARKET_USDC: float = 50.0
    MIN_SECONDS_BETWEEN_ENTRIES: float = 30.0
    ALLOW_OPPOSITE_SIDE_HEDGE: bool = False  # LONG_YES + LONG_NO together blocked by default

    # ── Scale-in delta gate (Phase 12J) ────────────────────────────────────────
    # A scale-in entry (second+ lot on the same condition_id) is only allowed
    # when at least ONE of the following improvement criteria is satisfied vs.
    # the most recent RISK_APPROVED / EXECUTED entry decision for that market:
    #
    #   • opportunity_score_new >= opportunity_score_prev + SCALE_IN_MIN_OPPORTUNITY_DELTA
    #   • yes_mid moves ≥ SCALE_IN_ENTRY_PRICE_IMPROVEMENT in the favourable
    #     direction (lower for LONG_YES; higher for LONG_NO)
    #
    # First entries (no prior RISK_APPROVED / EXECUTED decision) are always
    # admitted — this gate only fires on second+ attempts.
    # Block reason: SCALE_IN_NO_IMPROVEMENT
    SCALE_IN_MIN_OPPORTUNITY_DELTA: float = 3.0    # opportunity_score improvement threshold
    SCALE_IN_ENTRY_PRICE_IMPROVEMENT: float = 0.005  # 0.5% favourable move in yes_mid

    # Position sizing (Layer 13) — continuous exponential sizing (Phase 12L)
    # Replaces fixed quality-range tiers with a smooth curve from MIN to MAX.
    # Entry is skipped when score < POSITION_SCORE_MEDIUM.
    # For qualifying scores: size grows exponentially from MIN_USDC at the
    # minimum threshold up to MAX_USDC at POSITION_SCORE_MAX (capped above).
    #
    # Formula: size = MIN_USDC × (MAX_USDC / MIN_USDC) ^ fraction
    #   fraction = clamp((score - POSITION_SCORE_MEDIUM) /
    #                    (POSITION_SCORE_MAX - POSITION_SCORE_MEDIUM), 0, 1)
    #
    # Example outputs (MIN=1, MAX=50, thresholds 30-50):
    #   score=30  → $1.00   score=35  → $2.66   score=40  → $7.07
    #   score=45  → $18.80  score≥50  → $50.00
    MIN_ENTRY_NOTIONAL_USDC: float = 1.0         # minimum any order may be placed
    POSITION_SIZE_MIN_USDC: float = 1.0          # size at POSITION_SCORE_MEDIUM
    POSITION_SIZE_MAX_USDC: float = 50.0         # size at POSITION_SCORE_MAX and above
    POSITION_SCORE_MEDIUM: float = 30.0          # skip threshold — below = no trade
    POSITION_SCORE_MAX: float = 50.0             # score at which MAX size is reached

    # Watchdog — monitors engine heartbeats and restarts the process if stalled
    WATCHDOG_ENABLED: bool = True
    WATCHDOG_GRACE_SECONDS: int = 120    # startup grace period before first check
    WATCHDOG_CHECK_SECONDS: int = 60     # how often the watchdog polls
    WATCHDOG_STALL_SECONDS: int = 300    # warn if engine hasn't cycled in 5 min
    WATCHDOG_RESTART_SECONDS: int = 600  # force sys.exit(1) if stalled > 10 min

    # Capital management (Layer 16)
    CAPITAL_DAILY_LOSS_LIMIT_USDC: float = 30.0
    CAPITAL_WEEKLY_LOSS_LIMIT_USDC: float = 75.0
    CAPITAL_MAX_CONSECUTIVE_LOSSES: int = 5
    CAPITAL_MAX_DRAWDOWN_PERCENT: float = 20.0
    CAPITAL_ENABLE_KILL_SWITCH: bool = True
    CAPITAL_COOLDOWN_MINUTES: float = 60.0
    CAPITAL_INITIAL_USDC: float = 400.0  # starting capital for drawdown % calculation
    # Minimum unallocated capital that must remain after any new entry.
    # Blocks INSUFFICIENT_CAPITAL when:
    #   available_capital - proposed_notional < MIN_AVAILABLE_CAPITAL_RESERVE_USDC
    # where: available_capital = CAPITAL_INITIAL_USDC + realized_pnl - open_exposure
    MIN_AVAILABLE_CAPITAL_RESERVE_USDC: float = 10.0

    # Exit engine (Layer 11)
    EXIT_ENGINE_ENABLED: bool = True
    # EXIT_ENGINE_INTERVAL_SECONDS kept for legacy compatibility; the exit worker
    # uses EXIT_CHECK_INTERVAL_SECONDS as its actual poll frequency.
    EXIT_ENGINE_INTERVAL_SECONDS: int = 30
    EXIT_CHECK_INTERVAL_SECONDS: int = 2     # actual exit engine poll frequency (seconds)
    # Fast profit exit — fires before PROFIT_TARGET when net PnL clears the bar
    # and the position has been held at least MIN_POSITION_HOLD_SECONDS.
    MIN_POSITION_HOLD_SECONDS: int = 2
    FAST_PROFIT_EXIT_ENABLED: bool = True
    FAST_PROFIT_TARGET_USDC: float = 0.05        # gross PnL threshold
    FAST_PROFIT_TARGET_PERCENT: float = 0.5      # OR gross % of position_size_usdc
    MIN_NET_PROFIT_AFTER_COST_USDC: float = 0.03 # net PnL must exceed this after costs
    ESTIMATED_EXIT_COST_USDC: float = 0.01       # spread impact + slippage estimate
    MAX_ACCEPTABLE_EXIT_SPREAD: float = 0.05     # skip fast exit if spread too wide
    FAST_EXIT_MODE: str = "FULL"                 # FULL | PARTIAL | DYNAMIC
    FAST_EXIT_PARTIAL_PERCENT: float = 50.0      # % to close in PARTIAL mode
    EXIT_PROFIT_TARGET_USDC: float = 0.10
    # Dynamic stop loss (Phase 4 Part A):
    #   StopLoss = PositionSize × CurrentSpread × EXIT_STOP_LOSS_MULTIPLIER
    #   Falls back to EXIT_STOP_LOSS_USDC when spread data is unavailable.
    EXIT_STOP_LOSS_MULTIPLIER: float = 2.5
    EXIT_STOP_LOSS_USDC: float = -1.50     # static fallback
    EXIT_SIGNAL_TIMEOUT_MINUTES: int = 30
    EXIT_MAX_HOLD_MINUTES: int = 120          # absolute hold limit — fires for any status/market
    EXIT_EXPIRY_BUFFER_MINUTES: float = 15.0
    EXIT_FORCE_EXPIRY_MINUTES: float = 5.0

    # Trailing stop (Phase 4 Part E) — architecture ready, activates when markets mature
    # Triggers when: current_exit_pnl < (peak_pnl - position_value × TRAILING_STOP_DISTANCE)
    # Only fires after a profit peak has been recorded (peak_pnl > 0).
    TRAILING_STOP_ENABLED: bool = False
    TRAILING_STOP_DISTANCE: float = 0.02  # fraction of position value (2%)

    # Fee simulation (Phase 4 Part D) — Polymarket charges on notional value
    # Set to actual rate when live trading; 0.0 = paper mode (no fees deducted).
    POLYMARKET_FEE_RATE: float = 0.0      # applied to both entry and exit orders

    # ── Decision Engine pipeline (Phase Next) ─────────────────────────────────
    # Signal → Momentum → Trend → Volatility → Opportunity → Risk → Decision.
    # Rule-based (no ML). Read-only — never mutates market/trading data.
    MOMENTUM_ENGINE_ENABLED: bool = True
    MOMENTUM_ENGINE_INTERVAL_SECONDS: int = 60
    MOMENTUM_ENGINE_RUN_ON_STARTUP: bool = True

    TREND_ENGINE_ENABLED: bool = True
    TREND_ENGINE_INTERVAL_SECONDS: int = 60
    TREND_ENGINE_RUN_ON_STARTUP: bool = True

    VOLATILITY_ENGINE_ENABLED: bool = True
    VOLATILITY_ENGINE_INTERVAL_SECONDS: int = 60
    VOLATILITY_ENGINE_RUN_ON_STARTUP: bool = True

    DECISION_ENGINE_ENABLED: bool = True
    DECISION_ENGINE_INTERVAL_SECONDS: int = 60
    DECISION_ENGINE_RUN_ON_STARTUP: bool = True

    # ── Phase Next: Decision Engine Evolution — Polymarket-first engines ─────
    # Market Quality is the PRIMARY gate and must run before Decision Engine.
    MARKET_QUALITY_ENGINE_ENABLED: bool = True
    MARKET_QUALITY_ENGINE_INTERVAL_SECONDS: int = 30
    MARKET_QUALITY_ENGINE_RUN_ON_STARTUP: bool = True

    MARKET_CONTEXT_ENGINE_ENABLED: bool = True
    MARKET_CONTEXT_ENGINE_INTERVAL_SECONDS: int = 60
    MARKET_CONTEXT_ENGINE_RUN_ON_STARTUP: bool = True

    ORDERBOOK_ENGINE_ENABLED: bool = True
    ORDERBOOK_ENGINE_INTERVAL_SECONDS: int = 30
    ORDERBOOK_ENGINE_RUN_ON_STARTUP: bool = True

    FUNDING_ENGINE_ENABLED: bool = True
    FUNDING_ENGINE_INTERVAL_SECONDS: int = 60
    FUNDING_ENGINE_RUN_ON_STARTUP: bool = True

    NEWS_ENGINE_ENABLED: bool = True
    NEWS_ENGINE_INTERVAL_SECONDS: int = 120
    NEWS_ENGINE_RUN_ON_STARTUP: bool = True

    # ── Outcome Learning (Priority 1 + Priority 5) ────────────────────────────
    # Runs after markets expire to evaluate AI prediction accuracy.
    OUTCOME_LEARNING_ENABLED: bool = True
    OUTCOME_LEARNING_INTERVAL_SECONDS: int = 300   # 5 minutes
    OUTCOME_LEARNING_RUN_ON_STARTUP: bool = True

    # ── Dynamic Engine Weight (Priority 3) ────────────────────────────────────
    # Adjusts engine weights based on historical accuracy.
    # Only adjusts engines with >= DYNAMIC_WEIGHT_MIN_OUTCOMES outcomes.
    DYNAMIC_WEIGHT_ENABLED: bool = True
    DYNAMIC_WEIGHT_INTERVAL_SECONDS: int = 1800    # 30 minutes
    DYNAMIC_WEIGHT_RUN_ON_STARTUP: bool = False    # no outcomes on first startup
    DYNAMIC_WEIGHT_MIN_OUTCOMES: int = 10          # minimum before adjusting

    # ── Execution Safety (Layer 7 lifecycle gate) ──────────────────────────────
    # Maximum age (minutes) of a RISK_APPROVED decision before execution refuses it.
    # Prevents stale decisions from being acted on after market state has changed.
    EXECUTION_MAX_DECISION_AGE_MINUTES: int = 30

    # ── Chainlink RTDS (Polymarket Real-Time Data Service) ────────────────────
    # WebSocket connection to wss://ws-live-data.polymarket.com for live
    # Chainlink oracle prices (BTC, ETH, SOL, XRP).  This is the ONLY
    # permitted source for asset reference prices used in predictions.
    CHAINLINK_ENABLED: bool = True
    CHAINLINK_WS_URL: str = "wss://ws-live-data.polymarket.com"
    CHAINLINK_TOPIC: str = "crypto_prices_chainlink"
    CHAINLINK_STALE_SECONDS: int = 60        # price is stale after 60 s without update
    CHAINLINK_RECONNECT_SECONDS: int = 5     # delay between reconnect attempts
    CHAINLINK_TICK_HISTORY_SIZE: int = 2000  # per-symbol ring buffer for OHLC candles

    # Integrity gate — OPEN_LONG_* is blocked unless:
    #   target_verified=True AND target_price is not None AND Chainlink fresh
    # Production default: True. Only disable for isolated unit testing.
    # This setting MUST remain True in production — changing it is forbidden
    # without an explicit spec change.
    CHAINLINK_INTEGRITY_GATE_ENABLED: bool = True

    # Target worker — fetches official Price to Beat from Gamma API for each
    # active market.  Runs every N seconds; skips already-verified markets.
    TARGET_WORKER_ENABLED: bool = True
    TARGET_WORKER_INTERVAL_SECONDS: int = 30

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalise_db_url(cls, v: str) -> str:
        if not isinstance(v, str):
            return v
        v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        v = v.replace("postgres://", "postgresql+asyncpg://", 1)
        parsed = urlparse(v)
        params = parse_qs(parsed.query, keep_blank_values=True)
        params.pop("sslmode", None)
        params.pop("sslrootcert", None)
        params.pop("sslcert", None)
        params.pop("sslkey", None)
        clean_query = urlencode({k: vv[0] for k, vv in params.items()})
        clean = parsed._replace(query=clean_query)
        return urlunparse(clean)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
