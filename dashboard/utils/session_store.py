"""Server-side session store for dashboard auth tokens.

Streamlit wipes st.session_state on every full browser reload (F5) — there's
no built-in way to survive it. Previously this app put the raw JWT access +
refresh tokens directly in the URL (?tok=&rtok=) so they could be restored
after reload. That meant the actual bearer tokens sat in the browser's
address bar continuously — landing in browser history and any server/proxy
access log that records query strings.

Instead: the real tokens live server-side in Redis, keyed by a random opaque
session id, and only that id goes in the URL (?sid=). A leaked/logged URL is
then useless on its own — it doesn't carry a usable bearer token.

Every function degrades to a no-op / None if Redis is unreachable, so a
Redis outage falls back to the old (less safe) URL scheme rather than
locking users out entirely — see utils/auth.py's fallback paths.
"""
import json
import logging
import os
import secrets

logger = logging.getLogger(__name__)

# Matches JWT_REFRESH_TOKEN_EXPIRES' default (api/config.py) — no point
# outliving the refresh token itself.
_TTL_SECONDS = int(os.getenv("DASHBOARD_SESSION_TTL", 604800))
_KEY_PREFIX = "dash:session:"

_client = None
_unavailable = False


def _redis():
    global _client, _unavailable
    if _unavailable:
        return None
    if _client is None:
        try:
            import redis
            _client = redis.from_url(
                os.getenv("REDIS_URL", "redis://localhost:6379/0"),
                decode_responses=True, socket_connect_timeout=2, socket_timeout=2,
            )
            _client.ping()
        except Exception as e:
            logger.warning("Dashboard session store unavailable (Redis unreachable): %s", e)
            _unavailable = True
            _client = None
    return _client


def create_session(access_token: str, refresh_token: str = "") -> str:
    """Store tokens server-side, return an opaque session id — or "" if Redis is down."""
    r = _redis()
    if not r:
        return ""
    sid = secrets.token_urlsafe(32)
    try:
        r.setex(_KEY_PREFIX + sid, _TTL_SECONDS, json.dumps({
            "access_token": access_token, "refresh_token": refresh_token,
        }))
        return sid
    except Exception as e:
        logger.warning("Failed to create dashboard session: %s", e)
        return ""


def get_session(session_id: str):
    """Look up (access_token, refresh_token) for a session id. Refreshes TTL
    on hit (sliding expiry). Returns ("", "") if not found or Redis is down."""
    if not session_id:
        return "", ""
    r = _redis()
    if not r:
        return "", ""
    key = _KEY_PREFIX + session_id
    try:
        raw = r.get(key)
        if not raw:
            return "", ""
        r.expire(key, _TTL_SECONDS)
        data = json.loads(raw)
        return data.get("access_token", ""), data.get("refresh_token", "")
    except Exception as e:
        logger.warning("Failed to read dashboard session: %s", e)
        return "", ""


def update_session(session_id: str, access_token: str, refresh_token: str = "") -> None:
    """Overwrite stored tokens — used after an access-token refresh mid-session."""
    if not session_id:
        return
    r = _redis()
    if not r:
        return
    try:
        r.setex(_KEY_PREFIX + session_id, _TTL_SECONDS, json.dumps({
            "access_token": access_token, "refresh_token": refresh_token,
        }))
    except Exception as e:
        logger.warning("Failed to update dashboard session: %s", e)


def delete_session(session_id: str) -> None:
    if not session_id:
        return
    r = _redis()
    if not r:
        return
    try:
        r.delete(_KEY_PREFIX + session_id)
    except Exception as e:
        logger.warning("Failed to delete dashboard session: %s", e)
