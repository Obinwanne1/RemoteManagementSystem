"""Tests for device list, get, update, delete, metrics, and task queuing."""
import uuid
import pytest
from conftest import create_user, delete_user, login, auth_headers


def _make_customer(app):
    from extensions import db
    from models.customer import Customer
    c = Customer(name=f"DevCo-{uuid.uuid4().hex[:6]}", slug=f"dc-{uuid.uuid4().hex[:6]}", is_active=True)
    db.session.add(c)
    db.session.commit()
    return c


def _make_device(app, customer_id, hostname=None):
    from extensions import db
    from models.device import Device
    d = Device(
        hostname=hostname or f"host-{uuid.uuid4().hex[:6]}",
        customer_id=customer_id,
        platform="windows",
        os_name="Windows 11",
        ip_address="10.0.0.1",
        is_online=True,
    )
    db.session.add(d)
    db.session.commit()
    return d


def _cleanup(app, device_ids=None, customer_id=None, user_id=None):
    from extensions import db
    from models.device import Device, DeviceMetrics
    from models.customer import Customer
    if device_ids:
        for did in device_ids:
            DeviceMetrics.query.filter_by(device_id=did).delete()
            Device.query.filter_by(id=did).delete()
    if customer_id:
        Customer.query.filter_by(id=customer_id).delete()
    db.session.commit()
    if user_id:
        delete_user(app, user_id)


class TestDeviceList:
    def test_list_requires_auth(self, client):
        r = client.get("/api/devices/")
        assert r.status_code == 401

    def test_list_returns_paginated(self, app, client):
        uid, email, pw = create_user(app, role="technician")
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.get("/api/devices/", headers=auth_headers(tok))
            assert r.status_code == 200
            body = r.get_json()
            assert "items" in body
            assert "total" in body
            assert body["total"] >= 1
        finally:
            _cleanup(app, [dev.id], cust.id, uid)

    def test_list_filter_by_customer(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.get(f"/api/devices/?customer_id={cust.id}", headers=auth_headers(tok))
            assert r.status_code == 200
            ids = [d["id"] for d in r.get_json()["items"]]
            assert dev.id in ids
        finally:
            _cleanup(app, [dev.id], cust.id, uid)

    def test_list_search_by_hostname(self, app, client):
        uid, email, pw = create_user(app, role="technician")
        cust = _make_customer(app)
        unique = f"unique-{uuid.uuid4().hex[:8]}"
        dev = _make_device(app, cust.id, hostname=unique)
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.get(f"/api/devices/?q={unique}", headers=auth_headers(tok))
            assert r.status_code == 200
            items = r.get_json()["items"]
            assert any(d["hostname"] == unique for d in items)
        finally:
            _cleanup(app, [dev.id], cust.id, uid)


class TestDeviceGetUpdate:
    def test_get_device(self, app, client):
        uid, email, pw = create_user(app, role="technician")
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.get(f"/api/devices/{dev.id}", headers=auth_headers(tok))
            assert r.status_code == 200
            assert r.get_json()["id"] == dev.id
        finally:
            _cleanup(app, [dev.id], cust.id, uid)

    def test_get_nonexistent_device(self, app, client):
        uid, email, pw = create_user(app, role="technician")
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.get(f"/api/devices/{uuid.uuid4()}", headers=auth_headers(tok))
            assert r.status_code == 404
        finally:
            delete_user(app, uid)

    def test_update_device(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.put(
                f"/api/devices/{dev.id}",
                json={"display_name": "Updated Name"},
                headers=auth_headers(tok),
                content_type="application/json",
            )
            assert r.status_code == 200
            assert r.get_json()["display_name"] == "Updated Name"
        finally:
            _cleanup(app, [dev.id], cust.id, uid)

    def test_delete_device(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.delete(f"/api/devices/{dev.id}", headers=auth_headers(tok))
            assert r.status_code == 200
            r2 = client.get(f"/api/devices/{dev.id}", headers=auth_headers(tok))
            assert r2.status_code == 404
        finally:
            _cleanup(app, [], cust.id, uid)


class TestDeviceMetrics:
    def test_metrics_empty_for_new_device(self, app, client):
        uid, email, pw = create_user(app, role="technician")
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.get(f"/api/devices/{dev.id}/metrics", headers=auth_headers(tok))
            assert r.status_code == 200
            assert r.get_json() == []  # plain list, no pagination wrapper
        finally:
            _cleanup(app, [dev.id], cust.id, uid)

    def test_metrics_returned_after_insert(self, app, client):
        from extensions import db
        from models.device import DeviceMetrics
        from datetime import datetime, timezone
        uid, email, pw = create_user(app, role="technician")
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        with app.app_context():
            m = DeviceMetrics(
                device_id=dev.id, cpu_pct=45.0, ram_pct=60.0, disk_pct=30.0,
                collected_at=datetime.now(timezone.utc),
            )
            db.session.add(m)
            db.session.commit()
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.get(f"/api/devices/{dev.id}/metrics", headers=auth_headers(tok))
            assert r.status_code == 200
            items = r.get_json()
            assert isinstance(items, list)
            assert len(items) >= 1
            assert items[0]["cpu_pct"] == 45.0
        finally:
            _cleanup(app, [dev.id], cust.id, uid)


class TestQueueTask:
    def test_queue_task_invalid_type(self, app, client):
        uid, email, pw = create_user(app, role="technician")
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.post(
                f"/api/devices/{dev.id}/queue_task",
                json={"task_type": "hack_the_world"},
                headers=auth_headers(tok),
                content_type="application/json",
            )
            assert r.status_code == 400
        finally:
            _cleanup(app, [dev.id], cust.id, uid)

    def test_queue_task_clean_temp(self, app, client):
        uid, email, pw = create_user(app, role="technician")
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        with app.app_context():
            from utils.builtin_scripts import ensure_builtin_scripts
            ensure_builtin_scripts()
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.post(
                f"/api/devices/{dev.id}/queue_task",
                json={"task_type": "clean_temp"},
                headers=auth_headers(tok),
                content_type="application/json",
            )
            assert r.status_code == 202, r.get_json()
        finally:
            _cleanup(app, [dev.id], cust.id, uid)

    def test_queue_task_requires_auth(self, client):
        r = client.post(f"/api/devices/{uuid.uuid4()}/queue_task", json={"task_type": "reboot"})
        assert r.status_code == 401
