"""Tests for routes/network.py — network scan trigger, agentless device
upsert, scan listing (audits/testing_audit.md Finding C2)."""
import time
import uuid
from unittest.mock import patch

from conftest import create_user, delete_user, login, auth_headers


def _make_customer(app):
    from extensions import db
    from models.customer import Customer
    c = Customer(name=f"NetCo-{uuid.uuid4().hex[:6]}", slug=f"nc-{uuid.uuid4().hex[:6]}", is_active=True)
    db.session.add(c)
    db.session.commit()
    return c


def _cleanup(app, *, user_id=None, customer_id=None, scan_ids=(), device_ids=()):
    from extensions import db
    from models.customer import Customer
    from models.audit import NetworkScan
    from models.device import Device
    for did in device_ids:
        Device.query.filter_by(id=did).delete()
    for sid in scan_ids:
        NetworkScan.query.filter_by(id=sid).delete()
    if customer_id:
        Customer.query.filter_by(id=customer_id).delete()
    db.session.commit()
    if user_id:
        delete_user(app, user_id)


class TestTriggerScan:
    def test_requires_auth(self, client):
        r = client.post("/api/network/scan", json={"scan_range": "10.0.0.0/24"})
        assert r.status_code == 401

    def test_viewer_forbidden(self, app, client):
        uid, email, pw = create_user(app, role="viewer")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.post("/api/network/scan", headers=auth_headers(token),
                             json={"scan_range": "10.0.0.0/24"})
            assert r.status_code == 403
        finally:
            _cleanup(app, user_id=uid)

    def test_missing_scan_range_rejected_by_schema(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.post("/api/network/scan", headers=auth_headers(token), json={})
            assert r.status_code == 400
        finally:
            _cleanup(app, user_id=uid)

    def test_admin_starts_scan(self, app, client):
        # The route spawns a real background thread running tasks.network_tasks._run_scan —
        # patch it out so no actual ICMP sweep happens during the test.
        uid, email, pw = create_user(app, role="admin")
        scan_id = None
        try:
            token = login(client, email, pw).get_json()["access_token"]
            with patch("tasks.network_tasks._run_scan") as mock_run:
                r = client.post("/api/network/scan", headers=auth_headers(token),
                                 json={"scan_range": "10.0.0.0/24"})
                assert r.status_code == 202
                body = r.get_json()
                assert "scan_id" in body
                scan_id = body["scan_id"]
                time.sleep(0.2)  # let the daemon thread reach the mocked call
                assert mock_run.called
        finally:
            _cleanup(app, user_id=uid, scan_ids=[scan_id] if scan_id else [])


class TestUpsertAgentlessDevices:
    def test_requires_hosts(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.post("/api/network/agentless_devices", headers=auth_headers(token),
                             json={"hosts": []})
            assert r.status_code == 400
        finally:
            _cleanup(app, user_id=uid)

    def test_creates_new_agentless_device(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        cust = _make_customer(app)
        created_device_id = None
        try:
            token = login(client, email, pw).get_json()["access_token"]
            unique_ip = f"10.99.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"
            r = client.post(
                "/api/network/agentless_devices", headers=auth_headers(token),
                json={"customer_id": cust.id, "hosts": [
                    {"ip": unique_ip, "mac": f"AA:BB:CC:{uuid.uuid4().hex[:2]}:{uuid.uuid4().hex[:2]}:{uuid.uuid4().hex[:2]}",
                     "vendor": "TestVendor", "platform": "android", "device_type": "phone"},
                ]},
            )
            assert r.status_code == 200
            body = r.get_json()
            assert body["created"] == 1
            assert body["updated"] == 0

            from models.device import Device
            dev = Device.query.filter_by(ip_address=unique_ip).first()
            assert dev is not None
            created_device_id = dev.id
        finally:
            _cleanup(app, user_id=uid, customer_id=cust.id,
                     device_ids=[created_device_id] if created_device_id else [])


class TestListScans:
    def test_requires_auth(self, client):
        r = client.get("/api/network/scans")
        assert r.status_code == 401

    def test_lists_scans_for_customer(self, app, client):
        from extensions import db
        from models.audit import NetworkScan
        uid, email, pw = create_user(app, role="admin")
        cust = _make_customer(app)
        scan = NetworkScan(customer_id=cust.id, initiated_by=uid, scan_range="10.0.0.0/24", status="completed")
        db.session.add(scan)
        db.session.commit()
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.get(f"/api/network/scans?customer_id={cust.id}", headers=auth_headers(token))
            assert r.status_code == 200
            body = r.get_json()
            assert any(s["id"] == scan.id for s in body)
        finally:
            _cleanup(app, user_id=uid, customer_id=cust.id, scan_ids=[scan.id])


class TestGetScan:
    def test_404_for_unknown_scan(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.get("/api/network/scans/not-a-real-id", headers=auth_headers(token))
            assert r.status_code == 404
        finally:
            _cleanup(app, user_id=uid)

    def test_returns_discovered_hosts(self, app, client):
        from extensions import db
        from models.audit import NetworkScan
        uid, email, pw = create_user(app, role="admin")
        cust = _make_customer(app)
        scan = NetworkScan(customer_id=cust.id, initiated_by=uid, scan_range="10.0.0.0/24",
                            status="completed", discovered_hosts=[{"ip": "10.0.0.5"}])
        db.session.add(scan)
        db.session.commit()
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.get(f"/api/network/scans/{scan.id}", headers=auth_headers(token))
            assert r.status_code == 200
            body = r.get_json()
            assert body["discovered_hosts"] == [{"ip": "10.0.0.5"}]
        finally:
            _cleanup(app, user_id=uid, customer_id=cust.id, scan_ids=[scan.id])
