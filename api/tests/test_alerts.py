"""Tests for AlertRule CRUD and Alert acknowledge/resolve."""
import uuid
import pytest
from conftest import create_user, delete_user, login, auth_headers


def _make_customer(app):
    from extensions import db
    from models.customer import Customer
    c = Customer(name=f"AlertCo-{uuid.uuid4().hex[:6]}", slug=f"ac-{uuid.uuid4().hex[:6]}", is_active=True)
    db.session.add(c)
    db.session.commit()
    return c


def _make_device(app, customer_id):
    from extensions import db
    from models.device import Device
    d = Device(hostname=f"host-{uuid.uuid4().hex[:6]}", customer_id=customer_id, platform="windows")
    db.session.add(d)
    db.session.commit()
    return d


def _make_alert(app, device_id, status="open"):
    from extensions import db
    from models.alert import Alert
    a = Alert(device_id=device_id, message="CPU high", severity="warning", status=status)
    db.session.add(a)
    db.session.commit()
    return a


class TestAlertRuleCRUD:
    def test_list_rules_requires_auth(self, client):
        r = client.get("/api/alert_rules")
        assert r.status_code == 401

    def test_create_rule(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.post(
                "/api/alert_rules",
                json={"name": "CPU High", "metric": "cpu", "operator": "gt", "threshold": 90},
                headers=auth_headers(tok),
                content_type="application/json",
            )
            assert r.status_code == 201, r.get_json()
            body = r.get_json()
            assert body["name"] == "CPU High"
            assert body["metric"] == "cpu"
            assert body["is_active"] is True
        finally:
            delete_user(app, uid)

    def test_create_rule_missing_fields(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.post(
                "/api/alert_rules",
                json={"name": "Incomplete"},
                headers=auth_headers(tok),
                content_type="application/json",
            )
            assert r.status_code == 400
        finally:
            delete_user(app, uid)

    def test_viewer_cannot_create_rule(self, app, client):
        uid, email, pw = create_user(app, role="viewer")
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.post(
                "/api/alert_rules",
                json={"name": "X", "metric": "cpu", "operator": "gt"},
                headers=auth_headers(tok),
                content_type="application/json",
            )
            assert r.status_code == 403
        finally:
            delete_user(app, uid)

    def test_get_rule(self, app, client):
        uid, email, pw = create_user(app, role="technician")
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.post(
                "/api/alert_rules",
                json={"name": "RAM Rule", "metric": "ram", "operator": "gt", "threshold": 85},
                headers=auth_headers(tok),
                content_type="application/json",
            )
            rid = r.get_json()["id"]
            r2 = client.get(f"/api/alert_rules/{rid}", headers=auth_headers(tok))
            assert r2.status_code == 200
            assert r2.get_json()["id"] == rid
        finally:
            delete_user(app, uid)

    def test_update_rule(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.post(
                "/api/alert_rules",
                json={"name": "Disk Rule", "metric": "disk", "operator": "gt", "threshold": 80},
                headers=auth_headers(tok),
                content_type="application/json",
            )
            rid = r.get_json()["id"]
            r2 = client.put(
                f"/api/alert_rules/{rid}",
                json={"threshold": 95, "is_active": False},
                headers=auth_headers(tok),
                content_type="application/json",
            )
            assert r2.status_code == 200
            body = r2.get_json()
            assert body["threshold"] == 95
            assert body["is_active"] is False
        finally:
            delete_user(app, uid)

    def test_delete_rule(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.post(
                "/api/alert_rules",
                json={"name": "Delete me", "metric": "cpu", "operator": "gt"},
                headers=auth_headers(tok),
                content_type="application/json",
            )
            rid = r.get_json()["id"]
            r2 = client.delete(f"/api/alert_rules/{rid}", headers=auth_headers(tok))
            assert r2.status_code == 200
            r3 = client.get(f"/api/alert_rules/{rid}", headers=auth_headers(tok))
            assert r3.status_code == 404
        finally:
            delete_user(app, uid)

    def test_list_rules_paginated(self, app, client):
        uid, email, pw = create_user(app, role="technician")
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.get("/api/alert_rules", headers=auth_headers(tok))
            assert r.status_code == 200
            body = r.get_json()
            assert "items" in body
            assert "total" in body
        finally:
            delete_user(app, uid)


class TestAlertActions:
    def test_list_alerts_requires_auth(self, client):
        r = client.get("/api/alerts")
        assert r.status_code == 401

    def test_list_alerts(self, app, client):
        uid, email, pw = create_user(app, role="technician")
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        _make_alert(app, dev.id)
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.get("/api/alerts", headers=auth_headers(tok))
            assert r.status_code == 200
            assert "items" in r.get_json()
        finally:
            from extensions import db
            from models.alert import Alert
            from models.device import Device
            from models.customer import Customer
            Alert.query.filter_by(device_id=dev.id).delete()
            db.session.delete(dev)
            db.session.delete(cust)
            db.session.commit()
            delete_user(app, uid)

    def test_acknowledge_alert(self, app, client):
        uid, email, pw = create_user(app, role="technician")
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        alert = _make_alert(app, dev.id)
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.post(f"/api/alerts/{alert.id}/acknowledge", headers=auth_headers(tok))
            assert r.status_code == 200
            assert r.get_json()["status"] == "acknowledged"
        finally:
            from extensions import db
            from models.alert import Alert
            from models.device import Device
            from models.customer import Customer
            Alert.query.filter_by(device_id=dev.id).delete()
            db.session.delete(dev)
            db.session.delete(cust)
            db.session.commit()
            delete_user(app, uid)

    def test_resolve_alert(self, app, client):
        uid, email, pw = create_user(app, role="technician")
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        alert = _make_alert(app, dev.id)
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.post(f"/api/alerts/{alert.id}/resolve", headers=auth_headers(tok))
            assert r.status_code == 200
            body = r.get_json()
            assert body["status"] == "resolved"
            assert body["resolved_at"] is not None
        finally:
            from extensions import db
            from models.alert import Alert
            from models.device import Device
            from models.customer import Customer
            Alert.query.filter_by(device_id=dev.id).delete()
            db.session.delete(dev)
            db.session.delete(cust)
            db.session.commit()
            delete_user(app, uid)

    def test_ack_nonexistent_alert(self, app, client):
        uid, email, pw = create_user(app, role="technician")
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.post(f"/api/alerts/{uuid.uuid4()}/acknowledge", headers=auth_headers(tok))
            assert r.status_code == 404
        finally:
            delete_user(app, uid)
