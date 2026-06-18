from typing import Optional

import redis.asyncio as aioredis
from redis.asyncio import Redis
from redis.asyncio.connection import ConnectionPool

from app.config.settings import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_redis_pool: Optional[ConnectionPool] = None
_redis_client: Optional[Redis] = None


def create_redis_pool() -> ConnectionPool:
    return aioredis.ConnectionPool.from_url(
        settings.REDIS_URL,
        max_connections=settings.REDIS_POOL_SIZE,
        decode_responses=settings.REDIS_DECODE_RESPONSES,
    )


async def get_redis_client() -> Redis:
    global _redis_pool, _redis_client
    if _redis_client is None:
        _redis_pool = create_redis_pool()
        _redis_client = aioredis.Redis(connection_pool=_redis_pool)
    return _redis_client


async def check_redis_health() -> bool:
    try:
        client = await get_redis_client()
        await client.ping()
        return True
    except Exception as exc:
        logger.error("Redis health check failed", error=str(exc))
        return False


async def close_redis() -> None:
    global _redis_pool, _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
    if _redis_pool is not None:
        await _redis_pool.aclose()
        _redis_pool = None
    logger.info("Redis connection closed")
