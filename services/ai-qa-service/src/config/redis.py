import redis.asyncio as redis
from typing import Optional
import structlog

from ..config.settings import settings

logger = structlog.get_logger()


class RedisClient:
    def __init__(self):
        self._client: Optional[redis.Redis] = None

    def get_client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            logger.info("redis_connected", url=settings.redis_url)
        return self._client

    async def close(self):
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("redis_disconnected")


redis_client = RedisClient()
