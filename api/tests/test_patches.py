"""Tests for routes/patches.py — patch record listing/approval, compliance
summary, and patch policy CRUD (audits/testing_audit.md Finding C2)."""
import uuid
from conftest import create_user, delete_user, login, auth_headers


def _make_customer(app):
    from extensions import db
    from models.customer import Customer
    c = Customer(name=f"PatchCo-{uuid.uuid4().hex[:6]}", slug=f"pc-{uuid.uuid4().hex[:6]}", is_active=True)
    db.session.add(c)
    db.session.commit()
    return c


def _make_device(app, customer_id):
    from extensions import db
    from models.device import Device
    d = Device(hostname=f"host-{uuid.uuid4().hex[:6]}", customer_id=customer_id,
               platform="windows", os_name="Windows 11", ip_address="10.0.0.1", is_online=True)
    db.session.add(d)
    db.session.commit()
    return d


def _make_patch(app, device_id, **kwargs):
    from extensions import db
    from models.patch import PatchRecord
    defaults = dict(device_id=device_id, patch_name=f"KB-{uuid.uuid4().hex[:6]}", status="pending")
    defaults.update(kwargs)
    p = PatchRecord(**defaults)
    db.session.add(p)
    db.session.commit()
    return p


def _cleanup(app, *, user_id=None, customer_id=None, device_ids=(), patch_ids=(), policy_ids=()):
    from extensions import db
    from models.customer import Customer
    from models.device import Device
    from models.patch import PatchRecord, PatchPolicy
    for pid in patch_ids:
        PatchRecord.query.filter_by(id=pid).delete()
    for pid in policy_ids:
        PatchPolicy.query.filter_by(id=pid).delete()
    for did in device_ids:
        Device.query.filter_by(id=did).delete()
    if customer_id:
        Customer.query.filter_by(id=customer_id).delete()
    db.session.commit()
    if user_id:
        delete_user(app, user_id)


class TestListPatches:
    def test_requires_auth(self, client):
        r = client.get("/api/patches/")
        assert r.status_code == 401

    def test_filters_by_device_and_returns_paginated_shape(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        patch = _make_patch(app, dev.id, status="pending")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.get(f"/api/patches/?device_id={dev.id}", headers=auth_headers(token))
            assert r.status_code == 200
            body = r.get_json()
            assert "items" in body and "pages" in body
            assert any(p["id"] == patch.id for p in body["items"])
        finally:
            _cleanup(app, user_id=uid, customer_id=cust.id, device_ids=[dev.id], patch_ids=[patch.id])


class TestPendingPatches:
    def test_only_returns_pending(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        pending = _make_patch(app, dev.id, status="pending")
        deployed = _make_patch(app, dev.id, status="deployed")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.get("/api/patches/pending", headers=auth_headers(token))
            assert r.status_code == 200
            ids = [p["id"] for p in r.get_json()]
            assert pending.id in ids
            assert deployed.id not in ids
        finally:
            _cleanup(app, user_id=uid, customer_id=cust.id, device_ids=[dev.id],
                     patch_ids=[pending.id, deployed.id])


class TestApprovePatches:
    def test_requires_technician_or_admin(self, app, client):
        uid, email, pw = create_user(app, role="viewer")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.post("/api/patches/approve", headers=auth_headers(token), json={"patch_ids": ["x"]})
            assert r.status_code == 403
        finally:
            delete_user(app, uid)

    def test_requires_patch_ids(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.post("/api/patches/approve", headers=auth_headers(token), json={"patch_ids": []})
            assert r.status_code == 400
        finally:
            delete_user(app, uid)

    def test_approves_pending_patches_only(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        pending = _make_patch(app, dev.id, status="pending")
        already_deployed = _make_patch(app, dev.id, status="deployed")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.post("/api/patches/approve", headers=auth_headers(token),
                             json={"patch_ids": [pending.id, already_deployed.id]})
            assert r.status_code == 200
            assert r.get_json()["approved"] == 1  # only the pending one counts

            from extensions import db
            db.session.refresh(pending)
            assert pending.status == "approved"
            assert pending.deployed_by == uid
        finally:
            _cleanup(app, user_id=uid, customer_id=cust.id, device_ids=[dev.id],
                     patch_ids=[pending.id, already_deployed.id])


class TestPatchSummary:
    def test_computes_compliance_percentage(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        p1 = _make_patch(app, dev.id, status="deployed")
        p2 = _make_patch(app, dev.id, status="pending")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.get("/api/patches/summary", headers=auth_headers(token))
            assert r.status_code == 200
            body = r.get_json()
            assert body["total"] >= 2
            assert body["deployed"] >= 1
            assert 0 <= body["compliance_pct"] <= 100
        finally:
            _cleanup(app, user_id=uid, customer_id=cust.id, device_ids=[dev.id], patch_ids=[p1.id, p2.id])


class TestPatchPolicies:
    def test_create_requires_technician_or_admin(self, app, client):
        uid, email, pw = create_user(app, role="viewer")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.post("/api/patches/policies", headers=auth_headers(token), json={"name": "x"})
            assert r.status_code == 403
        finally:
            delete_user(app, uid)

    def test_create_requires_name(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.post("/api/patches/policies", headers=auth_headers(token), json={})
            assert r.status_code == 400
        finally:
            delete_user(app, uid)

    def test_create_update_delete_lifecycle(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        policy_id = None
        try:
            token = login(client, email, pw).get_json()["access_token"]
            name = f"Policy-{uuid.uuid4().hex[:6]}"
            r = client.post("/api/patches/policies", headers=auth_headers(token),
                             json={"name": name, "auto_approve_critical": True})
            assert r.status_code == 201
            policy_id = r.get_json()["id"]
            assert r.get_json()["name"] == name

            r = client.get("/api/patches/policies", headers=auth_headers(token))
            assert any(p["id"] == policy_id for p in r.get_json())

            r = client.put(f"/api/patches/policies/{policy_id}", headers=auth_headers(token),
                            json={"reboot_behavior": "auto"})
            assert r.status_code == 200
            assert r.get_json()["reboot_behavior"] == "auto"

            r = client.delete(f"/api/patches/policies/{policy_id}", headers=auth_headers(token))
            assert r.status_code == 200
            policy_id = None  # already deleted
        finally:
            _cleanup(app, user_id=uid, policy_ids=[policy_id] if policy_id else [])

    def test_delete_requires_admin_not_just_technician(self, app, client):
        admin_uid, admin_email, admin_pw = create_user(app, role="admin")
        tech_uid, tech_email, tech_pw = create_user(app, role="technician")
        policy_id = None
        try:
            admin_token = login(client, admin_email, admin_pw).get_json()["access_token"]
            r = client.post("/api/patches/policies", headers=auth_headers(admin_token),
                             json={"name": f"Policy-{uuid.uuid4().hex[:6]}"})
            policy_id = r.get_json()["id"]

            tech_token = login(client, tech_email, tech_pw).get_json()["access_token"]
            r = client.delete(f"/api/patches/policies/{policy_id}", headers=auth_headers(tech_token))
            assert r.status_code == 403
        finally:
            _cleanup(app, policy_ids=[policy_id] if policy_id else [])
            delete_user(app, admin_uid)
            delete_user(app, tech_uid)
