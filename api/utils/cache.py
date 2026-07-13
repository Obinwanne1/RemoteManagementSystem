"""Simple Redis-backed cache helpers for hot endpoints."""
import json
import logging
import os

logger = logging.getLogger(__name__)


def _r():
    import redis
    return redis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        socket_timeout=1,
        socket_connect_timeout=1,
        decode_responses=True,
    )


def cache_get(key: str):
    """Return deserialized cached value or None on miss/error."""
    try:
        raw = _r().get(key)
        return json.loads(raw) if raw is not None else None
    except Exception as exc:
        logger.debug("cache_get miss [%s]: %s", key, exc)
        return None


def cache_set(key: str, value, ttl: int) -> None:
    """Serialize value and store with TTL seconds. Silently ignores Redis errors."""
    try:
        _r().setex(key, ttl, json.dumps(value, default=str))
    except Exception as exc:
        logger.debug("cache_set failed [%s]: %s", key, exc)


def cache_delete(key: str) -> None:
    """Delete a cache key. Silently ignores Redis errors."""
    try:
        _r().delete(key)
    except Exception as exc:
        logger.debug("cache_delete failed [%s]: %s", key, exc)
