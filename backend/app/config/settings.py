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
    APP_VERSION: str = "0.3.0"
    APP_ENV: str = "development"
    DEBUG: bool = False

    # API
    API_V1_PREFIX: str = "/api/v1"

    # Database — Replit injects DATABASE_URL as postgresql://...?sslmode=require
    # We normalise to asyncpg scheme and strip incompatible query params.
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

    # Scanner (market universe discovery — Sprint 3)
    SCANNER_INTERVAL_SECONDS: int = 300   # 5 minutes; discovery paginates ~20k markets
    SCANNER_ENABLED: bool = True
    SCANNER_RUN_ON_STARTUP: bool = True   # run once immediately at boot

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalise_db_url(cls, v: str) -> str:
        """
        Convert plain postgresql:// / postgres:// URLs to postgresql+asyncpg://.
        Also strips query params that asyncpg doesn't understand (e.g. sslmode).
        asyncpg SSL is handled via engine connect_args, not query params.
        """
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
