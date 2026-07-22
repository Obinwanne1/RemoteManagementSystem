"""Redis-backed cache helpers. Module-level singleton — one connection pool, not one connection per call."""
import json
import logging
import os

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        import redis
        _client = redis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            socket_timeout=1,
            socket_connect_timeout=1,
            decode_responses=True,
            max_connections=20,
        )
    return _client


def cache_get(key: str):
    try:
        raw = _get_client().get(key)
        return json.loads(raw) if raw is not None else None
    except Exception as exc:
        logger.debug("cache_get miss [%s]: %s", key, exc)
        return None


def cache_get_raw(key: str):
    """Return the raw JSON string from Redis (no deserialize). None on miss."""
    try:
        return _get_client().get(key)
    except Exception as exc:
        logger.debug("cache_get_raw miss [%s]: %s", key, exc)
        return None


def cache_set(key: str, value, ttl: int) -> None:
    try:
        _get_client().setex(key, ttl, json.dumps(value, default=str))
    except Exception as exc:
        logger.debug("cache_set failed [%s]: %s", key, exc)


def cache_set_raw(key: str, raw_json: str, ttl: int) -> None:
    """Store a pre-serialized JSON string — skips double serialize on cache hit."""
    try:
        _get_client().setex(key, ttl, raw_json)
    except Exception as exc:
        logger.debug("cache_set_raw failed [%s]: %s", key, exc)


def cache_delete(key: str) -> None:
    try:
        _get_client().delete(key)
    except Exception as exc:
        logger.debug("cache_delete failed [%s]: %s", key, exc)


def cache_delete_pattern(pattern: str) -> None:
    """Delete all keys matching a glob pattern. Use sparingly — SCAN-based."""
    try:
        r = _get_client()
        keys = list(r.scan_iter(pattern, count=100))
        if keys:
            r.delete(*keys)
    except Exception as exc:
        logger.debug("cache_delete_pattern failed [%s]: %s", pattern, exc)
