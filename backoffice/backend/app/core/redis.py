import hashlib
import json
import logging
from functools import wraps

import redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

try:
    redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    redis_client.ping()
except Exception:
    logger.warning("Redis unavailable - caching disabled")
    redis_client = None


def cache_result(prefix: str, ttl: int | None = None):
    """Decorator to cache function results in Redis."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if redis_client is None:
                return func(*args, **kwargs)
            cache_ttl = ttl or settings.CACHE_TTL
            key_data = f"{prefix}:{func.__name__}:{str(args)}:{str(kwargs)}"
            key_hash = hashlib.sha256(key_data.encode()).hexdigest()
            key = f"backoffice:{prefix}:{key_hash}"
            try:
                cached = redis_client.get(key)
                if cached:
                    return json.loads(cached)
            except Exception:
                logger.warning("Redis read error, falling through to function")
            result = func(*args, **kwargs)
            try:
                redis_client.setex(key, cache_ttl, json.dumps(result, default=str))
            except Exception:
                logger.warning("Redis write error, result not cached")
            return result
        return wrapper
    return decorator


def invalidate_cache(prefix: str):
    """Invalidate all cache keys matching a prefix."""
    if redis_client is None:
        return
    try:
        keys = list(redis_client.scan_iter(f"backoffice:{prefix}:*"))
        if keys:
            redis_client.delete(*keys)
    except Exception:
        logger.warning("Redis invalidation error")
