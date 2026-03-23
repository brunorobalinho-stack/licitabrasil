import json
from functools import wraps
from typing import Any

import redis

from app.core.config import get_settings

settings = get_settings()

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)


def cache_result(prefix: str, ttl: int | None = None):
    """Decorator to cache function results in Redis."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_ttl = ttl or settings.CACHE_TTL
            key = f"backoffice:{prefix}:{hash(str(args) + str(kwargs))}"
            cached = redis_client.get(key)
            if cached:
                return json.loads(cached)
            result = func(*args, **kwargs)
            redis_client.setex(key, cache_ttl, json.dumps(result, default=str))
            return result
        return wrapper
    return decorator


def invalidate_cache(prefix: str):
    """Invalidate all cache keys matching a prefix."""
    for key in redis_client.scan_iter(f"backoffice:{prefix}:*"):
        redis_client.delete(key)
