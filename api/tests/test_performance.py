"""Response-time budget tests (audits/testing_audit.md Finding M4). Not a load
test — a cheap tripwire that fails loudly if a route regresses to an obviously
pathological response time (e.g. an accidental N+1 query) under the test suite's
own SQLite in-memory DB, which has no network latency to hide behind."""
import time
from conftest import create_user, delete_user, login, auth_headers


class TestResponseTimeBudgets:
    def test_device_list_responds_within_budget(self, app, client):
        # devices.py::list_devices caches its raw JSON response for 30s, keyed by
        # page/per_page/filters (utils/cache.py, Redis-backed) — this endpoint's
        # cache key is shared with every other test that queries the same filters,
        # so populating it here can serve a stale (e.g. total=0) response to a
        # later, unrelated test within that window. Must clear it afterward.
        from utils.cache import cache_delete_pattern
        uid, email, pw = create_user(app, role="admin")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            start = time.monotonic()
            r = client.get("/api/devices/?per_page=50", headers=auth_headers(token))
            elapsed = time.monotonic() - start
            assert r.status_code == 200
            assert elapsed < 1.0, f"devices list took {elapsed:.2f}s, budget is 1.0s"
        finally:
            delete_user(app, uid)
            cache_delete_pattern("rmm:devices:list:*")

    def test_customers_list_responds_within_budget(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            start = time.monotonic()
            r = client.get("/api/customers/?per_page=50", headers=auth_headers(token))
            elapsed = time.monotonic() - start
            assert r.status_code == 200
            assert elapsed < 1.0, f"customers list took {elapsed:.2f}s, budget is 1.0s"
        finally:
            delete_user(app, uid)
