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
    APP_VERSION: str = "0.6.0"
    APP_ENV: str = "development"
    DEBUG: bool = False

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

    # Collector (price ticks — Sprint 2)
    COLLECTOR_INTERVAL_SECONDS: int = 5
    COLLECTOR_ENABLED: bool = True

    # Scanner (market universe discovery — Sprint 3/4)
    SCANNER_INTERVAL_SECONDS: int = 300
    SCANNER_ENABLED: bool = True
    SCANNER_RUN_ON_STARTUP: bool = True

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

    # Strategy engine (Layer 6)
    STRATEGY_ENGINE_ENABLED: bool = True
    STRATEGY_ENGINE_INTERVAL_SECONDS: int = 60
    STRATEGY_ENGINE_RUN_ON_STARTUP: bool = True
    STRATEGY_PERSIST_SKIPS: bool = False

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
    MAX_OPEN_POSITIONS: int = 10
    MAX_POSITION_SIZE: float = 1.0
    MAX_EXPOSURE_PER_ASSET: int = 3
    MAX_DAILY_LOSS: float = -50.0
    MAX_DAILY_TRADES: int = 20

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
