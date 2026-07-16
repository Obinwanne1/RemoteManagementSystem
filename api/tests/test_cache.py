"""
Unit tests for utils/cache.py.
Tests both happy-path (mocked Redis) and graceful degradation (Redis down).
No real Redis connection needed — all calls are mocked.
"""
import json
import pytest
from unittest.mock import MagicMock, patch


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_redis(get_return=None, raise_on_get=False, raise_on_set=False, raise_on_delete=False):
    r = MagicMock()
    if raise_on_get:
        r.get.side_effect = Exception("Redis down")
    else:
        r.get.return_value = get_return
    if raise_on_set:
        r.setex.side_effect = Exception("Redis down")
    if raise_on_delete:
        r.delete.side_effect = Exception("Redis down")
    return r


# ── cache_get ─────────────────────────────────────────────────────────────────

class TestCacheGet:
    def test_returns_deserialized_value(self):
        from utils.cache import cache_get
        mock_redis = _make_redis(get_return=json.dumps({"key": "val"}))
        with patch("utils.cache._get_client", return_value=mock_redis):
            result = cache_get("test-key")
        assert result == {"key": "val"}

    def test_returns_none_on_miss(self):
        from utils.cache import cache_get
        mock_redis = _make_redis(get_return=None)
        with patch("utils.cache._get_client", return_value=mock_redis):
            result = cache_get("missing-key")
        assert result is None

    def test_returns_none_when_redis_down(self):
        from utils.cache import cache_get
        mock_redis = _make_redis(raise_on_get=True)
        with patch("utils.cache._get_client", return_value=mock_redis):
            result = cache_get("any-key")
        assert result is None  # graceful degradation, no exception raised

    def test_handles_integer_value(self):
        from utils.cache import cache_get
        mock_redis = _make_redis(get_return=json.dumps(42))
        with patch("utils.cache._get_client", return_value=mock_redis):
            assert cache_get("int-key") == 42

    def test_handles_list_value(self):
        from utils.cache import cache_get
        mock_redis = _make_redis(get_return=json.dumps([1, 2, 3]))
        with patch("utils.cache._get_client", return_value=mock_redis):
            assert cache_get("list-key") == [1, 2, 3]


# ── cache_set ─────────────────────────────────────────────────────────────────

class TestCacheSet:
    def test_calls_setex_with_ttl(self):
        from utils.cache import cache_set
        mock_redis = MagicMock()
        with patch("utils.cache._get_client", return_value=mock_redis):
            cache_set("my-key", {"a": 1}, ttl=30)
        mock_redis.setex.assert_called_once()
        args = mock_redis.setex.call_args[0]
        assert args[0] == "my-key"
        assert args[1] == 30
        assert json.loads(args[2]) == {"a": 1}

    def test_silently_ignores_redis_error(self):
        from utils.cache import cache_set
        mock_redis = _make_redis(raise_on_set=True)
        with patch("utils.cache._get_client", return_value=mock_redis):
            cache_set("key", "value", ttl=60)  # must not raise

    def test_serializes_non_string_types(self):
        from utils.cache import cache_set
        mock_redis = MagicMock()
        with patch("utils.cache._get_client", return_value=mock_redis):
            cache_set("nums", [1, 2, 3], ttl=10)
        serialized = mock_redis.setex.call_args[0][2]
        assert json.loads(serialized) == [1, 2, 3]


# ── cache_delete ──────────────────────────────────────────────────────────────

class TestCacheDelete:
    def test_calls_delete(self):
        from utils.cache import cache_delete
        mock_redis = MagicMock()
        with patch("utils.cache._get_client", return_value=mock_redis):
            cache_delete("del-key")
        mock_redis.delete.assert_called_once_with("del-key")

    def test_silently_ignores_redis_error(self):
        from utils.cache import cache_delete
        mock_redis = _make_redis(raise_on_delete=True)
        with patch("utils.cache._get_client", return_value=mock_redis):
            cache_delete("key")  # must not raise


# ── cache_delete_pattern ──────────────────────────────────────────────────────

class TestCacheDeletePattern:
    def test_deletes_matched_keys(self):
        from utils.cache import cache_delete_pattern
        mock_redis = MagicMock()
        mock_redis.scan_iter.return_value = iter(["key:1", "key:2"])
        with patch("utils.cache._get_client", return_value=mock_redis):
            cache_delete_pattern("key:*")
        mock_redis.delete.assert_called_once_with("key:1", "key:2")

    def test_skips_delete_when_no_keys_matched(self):
        from utils.cache import cache_delete_pattern
        mock_redis = MagicMock()
        mock_redis.scan_iter.return_value = iter([])
        with patch("utils.cache._get_client", return_value=mock_redis):
            cache_delete_pattern("nomatch:*")
        mock_redis.delete.assert_not_called()

    def test_silently_ignores_redis_error(self):
        from utils.cache import cache_delete_pattern
        mock_redis = MagicMock()
        mock_redis.scan_iter.side_effect = Exception("Redis down")
        with patch("utils.cache._get_client", return_value=mock_redis):
            cache_delete_pattern("key:*")  # must not raise
