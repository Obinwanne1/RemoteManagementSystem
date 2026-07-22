"""
Process-local JWT decode cache.

Monkey-patches flask_jwt_extended's internal _decode_jwt_from_request so
repeated requests with the same bearer token skip HMAC verification.
Cache is per-process (no Redis), TTL=60s, max 512 tokens.

Import this module once at app startup to activate the patch.
"""
import hashlib
import threading

from cachetools import TTLCache

_cache: TTLCache = TTLCache(maxsize=512, ttl=60)
_lock = threading.RLock()


def _token_key(token: str) -> str:
    return hashlib.md5(token.encode(), usedforsecurity=False).hexdigest()


def install():
    import flask_jwt_extended.view_decorators as _vd

    _orig = _vd._decode_jwt_from_request

    def _cached_decode(locations, fresh, refresh=False, verify_type=True, skip_revocation_check=False):
        from flask import request
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            key = _token_key(auth[7:])
            with _lock:
                hit = _cache.get(key)
            if hit is not None:
                return hit

        result = _orig(locations, fresh, refresh=refresh,
                       verify_type=verify_type,
                       skip_revocation_check=skip_revocation_check)

        if auth.startswith("Bearer ") and result:
            key = _token_key(auth[7:])
            with _lock:
                _cache[key] = result

        return result

    _vd._decode_jwt_from_request = _cached_decode
