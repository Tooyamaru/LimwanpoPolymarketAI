from app.core.logging import get_logger

logger = get_logger(__name__)

_redis_client = None
_redis_pool = None


async def get_redis_client():
    global _redis_pool, _redis_client
    if _redis_client is None:
        try:
            import redis.asyncio as aioredis
            from app.config.settings import settings
            _redis_pool = aioredis.ConnectionPool.from_url(
                settings.REDIS_URL,
                max_connections=settings.REDIS_POOL_SIZE,
                decode_responses=settings.REDIS_DECODE_RESPONSES,
            )
            _redis_client = aioredis.Redis(connection_pool=_redis_pool)
        except Exception as exc:
            logger.warning("Redis not available", error=str(exc))
            return None
    return _redis_client


async def check_redis_health() -> bool:
    try:
        client = await get_redis_client()
        if client is None:
            return False
        await client.ping()
        return True
    except Exception as exc:
        logger.warning("Redis health check failed", error=str(exc))
        return False


async def close_redis() -> None:
    global _redis_pool, _redis_client
    if _redis_client is not None:
        try:
            await _redis_client.aclose()
        except Exception:
            pass
        _redis_client = None
    if _redis_pool is not None:
        try:
            await _redis_pool.aclose()
        except Exception:
            pass
        _redis_pool = None
    logger.info("Redis connection closed")
