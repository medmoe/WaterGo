from functools import lru_cache

import redis

from app.core.config import settings


@lru_cache
def get_redis() -> redis.Redis:
    """Shared Redis client (OTP store, Celery broker lives on the same server).

    Cached so the connection pool is reused; tests patch this to a fakeredis
    instance.
    """
    return redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
