"""
Redis-backed event bus for real-time SSE streaming.
All publish calls no-op silently if Redis is unavailable.
"""
import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_CHANNEL = "rmm:events"
_RECENT_KEY = "rmm:recent_events"
_RECENT_MAX = 100

_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        import redis as _redis
        url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        r = _redis.Redis.from_url(url, decode_responses=True, socket_connect_timeout=3)
        r.ping()
        _redis_client = r
    except Exception as exc:
        logger.debug("Event bus Redis unavailable: %s", exc)
        _redis_client = None
    return _redis_client


def publish_event(event_type: str, data: dict) -> None:
    """Publish a structured event. No-op if Redis down."""
    r = _get_redis()
    if r is None:
        return
    try:
        payload = json.dumps({
            "type": event_type,
            "data": data,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        r.publish(_CHANNEL, payload)
        r.lpush(_RECENT_KEY, payload)
        r.ltrim(_RECENT_KEY, 0, _RECENT_MAX - 1)
        r.expire(_RECENT_KEY, 3600)  # auto-expire after 1h idle
    except Exception as exc:
        logger.warning("publish_event failed: %s", exc)


def get_recent_events(limit: int = 20) -> list:
    """Return up to `limit` recent events (newest first) from Redis list."""
    r = _get_redis()
    if r is None:
        return []
    try:
        raw = r.lrange(_RECENT_KEY, 0, limit - 1)
        return [json.loads(x) for x in raw]
    except Exception:
        return []


def new_pubsub():
    """Return a fresh Redis PubSub subscribed to the event channel.
    Caller is responsible for calling ps.unsubscribe() + ps.close()."""
    import redis as _redis
    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    r = _redis.Redis.from_url(url, decode_responses=True, socket_connect_timeout=3)
    ps = r.pubsub(ignore_subscribe_messages=True)
    ps.subscribe(_CHANNEL)
    return ps
