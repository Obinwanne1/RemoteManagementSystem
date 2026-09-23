"""Lightweight Redis INCR/EXPIRE rate limiter for code paths that don't go through a
Flask route decorator (e.g. AI assistant tool execution, which calls service functions
directly and so bypasses @limiter.limit on the underlying human-facing routes)."""
import logging

from utils.cache import _get_client

logger = logging.getLogger(__name__)


def check_and_increment(key: str, limit: int, window_seconds: int) -> bool:
    """Returns True if under the limit (and increments the counter), False if the
    limit is already reached. Fails OPEN (returns True) if Redis is unavailable —
    matches this codebase's existing cache-layer pattern of degrading gracefully
    rather than blocking functionality on a Redis outage."""
    try:
        client = _get_client()
        count = client.incr(key)
        if count == 1:
            client.expire(key, window_seconds)
        return count <= limit
    except Exception as exc:
        logger.debug("rate_limit check failed [%s]: %s", key, exc)
        return True
