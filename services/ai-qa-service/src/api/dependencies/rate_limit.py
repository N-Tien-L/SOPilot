from fastapi import Request, HTTPException, status
import time
import structlog
from typing import Optional

from ...config.settings import settings
from ...config.redis import redis_client

logger = structlog.get_logger()


class InMemoryRateLimiter:
    """In-memory fallback rate limiter when Redis is unavailable."""

    def __init__(self):
        self._requests: dict[str, list[float]] = {}
        self._lock = None

    def _cleanup(self, key: str, window: float) -> None:
        """Remove expired entries for a key."""
        if key in self._requests:
            now = time.time()
            self._requests[key] = [t for t in self._requests[key] if t > now - window]
            if not self._requests[key]:
                del self._requests[key]

    def check(self, key: str, limit: int, window: float) -> bool:
        """Check if request is allowed. Returns True if allowed, False if rate limited."""
        now = time.time()
        self._cleanup(key, window)

        if key not in self._requests:
            self._requests[key] = []

        if len(self._requests[key]) >= limit:
            return False

        self._requests[key].append(now)
        return True


_memory_limiter = InMemoryRateLimiter()


async def rate_limit(request: Request):
    """
    Rate limiting dependency for chat endpoints.
    Limits requests based on user_id from headers.
    Falls back to in-memory limiter if Redis is unavailable.
    """
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        user_id = "anonymous"

    role = request.headers.get("X-Role")
    if role in ["ADMIN", "MANAGER"]:
        return

    now = time.time()
    key = f"rate_limit:chat:{user_id}"
    window = settings.rate_limit_window_seconds
    limit = settings.rate_limit_requests

    try:
        client = redis_client.get_client()
        await client.zremrangebyscore(key, 0, now - window)
        request_count = await client.zcard(key)

        if request_count >= limit:
            logger.warning("rate_limit_exceeded", user_id=user_id, count=request_count)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Maximum {limit} requests per {window} seconds."
            )

        await client.zadd(key, {str(now): now})
        await client.expire(key, window)

    except HTTPException:
        raise
    except Exception as e:
        logger.warning("rate_limit_redis_failed", error=str(e), fallback="in_memory")
        if not _memory_limiter.check(key, limit, window):
            logger.warning("rate_limit_exceeded_in_memory", user_id=user_id)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Maximum {limit} requests per {window} seconds."
            )
