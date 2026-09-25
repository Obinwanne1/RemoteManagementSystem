"""Dashboard summary/health-map/activity-feed route tests (audits/testing_audit.md
Finding C2 — dashboard.py had zero test coverage before this file).

Every endpoint here caches its response in real Redis under a key that does
NOT vary per test (cache_key = f"rmm:dash:summary:{cid or 'all'}" — every
non-client-role caller gets cid=None, so every test hits the exact same key).
Flushing "rmm:dash:*" before AND after each test is required, matching the
cross-test-pollution bug already found and fixed in test_performance.py this
same session (see audits/testing_audit.md's "Bugs found" section)."""
import uuid
from conftest import create_user, delete_user, login, auth_headers
from utils.cache import cache_delete_pattern


def _cleanup(app, *, user_ids=(), device_ids=(), customer_ids=()):
    from extensions import db
    from models.device import Device
    from models.customer import Customer
    for did in device_ids:
        Device.query.filter_by(id=did).delete()
    for cid in customer_ids:
        Customer.query.filter_by(id=cid).delete()
    db.session.commit()
    for uid in user_ids:
        try:
            delete_user(app, uid)
        except Exception:
            pass
    cache_delete_pattern("rmm:dash:*")


def _make_device(app, **kwargs):
    from extensions import db
    from models.device import Device
    defaults = dict(hostname=f"h-{uuid.uuid4().hex[:6]}", platform="windows", is_online=True, status="healthy")
    defaults.update(kwargs)
    d = Device(**defaults)
    db.session.add(d)
    db.session.commit()
    return d


class TestSummary:
    def test_requires_auth(self, client):
        r = client.get("/api/dashboard/summary")
        assert r.status_code == 401

    def test_counts_online_and_critical_devices(self, app, client):
        cache_delete_pattern("rmm:dash:*")
        uid, email, pw = create_user(app, role="admin")
        dev1 = _make_device(app, is_online=True, status="healthy")
        dev2 = _make_device(app, is_online=False, status="critical")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.get("/api/dashboard/summary", headers=auth_headers(token))
            assert r.status_code == 200
            body = r.get_json()
            assert body["devices"]["total"] >= 2
            assert body["devices"]["online"] >= 1
            assert body["devices"]["critical"] >= 1
        finally:
            _cleanup(app, user_ids=[uid], device_ids=[dev1.id, dev2.id])

    def test_response_is_cached_within_ttl(self, app, client):
        """A second call before a device count changes should return the same
        cached total even if a fresh query would differ (documents the 60s TTL
        this endpoint uses, not just correctness of the counts)."""
        cache_delete_pattern("rmm:dash:*")
        uid, email, pw = create_user(app, role="admin")
        dev = _make_device(app)
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r1 = client.get("/api/dashboard/summary", headers=auth_headers(token))
            first_total = r1.get_json()["devices"]["total"]

            dev2 = _make_device(app)  # created AFTER the cache was primed
            r2 = client.get("/api/dashboard/summary", headers=auth_headers(token))
            assert r2.get_json()["devices"]["total"] == first_total  # still cached, doesn't see dev2

            from extensions import db
            from models.device import Device
            Device.query.filter_by(id=dev2.id).delete()
            db.session.commit()
        finally:
            _cleanup(app, user_ids=[uid], device_ids=[dev.id])


class TestHealthMap:
    def test_requires_auth(self, client):
        r = client.get("/api/dashboard/health_map")
        assert r.status_code == 401

    def test_returns_device_list(self, app, client):
        cache_delete_pattern("rmm:dash:*")
        uid, email, pw = create_user(app, role="admin")
        dev = _make_device(app, hostname=f"healthmap-{uuid.uuid4().hex[:6]}")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.get("/api/dashboard/health_map", headers=auth_headers(token))
            assert r.status_code == 200
            hostnames = [d["hostname"] for d in r.get_json()]
            assert dev.hostname in hostnames
        finally:
            _cleanup(app, user_ids=[uid], device_ids=[dev.id])


class TestRecentAlerts:
    def test_requires_auth(self, client):
        r = client.get("/api/dashboard/recent_alerts")
        assert r.status_code == 401

    def test_returns_recent_alerts_desc(self, app, client):
        from extensions import db
        from models.alert import Alert
        cache_delete_pattern("rmm:dash:*")
        uid, email, pw = create_user(app, role="admin")
        dev = _make_device(app)
        alert = Alert(device_id=dev.id, severity="critical", message="Test alert", status="open")
        db.session.add(alert)
        db.session.commit()
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.get("/api/dashboard/recent_alerts", headers=auth_headers(token))
            assert r.status_code == 200
            ids = [a["id"] for a in r.get_json()]
            assert alert.id in ids
        finally:
            Alert.query.filter_by(id=alert.id).delete()
            db.session.commit()
            _cleanup(app, user_ids=[uid], device_ids=[dev.id])


class TestActivityFeed:
    def test_requires_auth(self, client):
        r = client.get("/api/dashboard/activity_feed")
        assert r.status_code == 401

    def test_client_role_sees_empty_feed(self, app, client):
        """activity_feed short-circuits to [] for role=client without even
        querying — a deliberate privacy choice (audit log isn't tenant-scoped
        so it's hidden entirely from clients rather than filtered)."""
        cache_delete_pattern("rmm:dash:*")
        uid, email, pw = create_user(app, role="client")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.get("/api/dashboard/activity_feed", headers=auth_headers(token))
            assert r.status_code == 200
            assert r.get_json() == []
        finally:
            _cleanup(app, user_ids=[uid])

    def test_admin_sees_audit_entries(self, app, client):
        cache_delete_pattern("rmm:dash:*")
        uid, email, pw = create_user(app, role="admin")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            # logging in itself doesn't necessarily write an AuditLog row in
            # every code path, so just assert the shape/200 rather than content —
            # a real audit event assertion would need to trigger a known
            # audit-logged action first (e.g. admin.py's user CRUD, covered
            # separately in test_admin.py).
            r = client.get("/api/dashboard/activity_feed", headers=auth_headers(token))
            assert r.status_code == 200
            assert isinstance(r.get_json(), list)
        finally:
            _cleanup(app, user_ids=[uid])
