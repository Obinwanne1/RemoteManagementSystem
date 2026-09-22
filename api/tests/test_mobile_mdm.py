"""Tests for MDM integration CRUD, enrollment consent gating, and device-command
scoping/permissions. Mirrors test_devices.py's fixture/cleanup conventions."""
import uuid
import pytest
from conftest import create_user, delete_user, login, auth_headers


def _make_customer(app):
    from extensions import db
    from models.customer import Customer
    c = Customer(name=f"MdmCo-{uuid.uuid4().hex[:6]}", slug=f"mc-{uuid.uuid4().hex[:6]}", is_active=True)
    db.session.add(c)
    db.session.commit()
    return c


def _make_integration(app, customer_id=None, bound=False):
    from extensions import db
    from models.mdm_integration import MdmIntegration
    integ = MdmIntegration(
        name=f"integ-{uuid.uuid4().hex[:6]}",
        type="android",
        customer_id=customer_id,
        project_id="test-project",
        enterprise_id="enterprises/fake123" if bound else None,
        default_policy_name="default",
    )
    db.session.add(integ)
    db.session.commit()
    return integ


def _make_device(app, customer_id):
    from extensions import db
    from models.device import Device
    d = Device(hostname=f"phone-{uuid.uuid4().hex[:6]}", customer_id=customer_id,
              platform="android", device_type="mobile", is_agentless=True, is_online=True)
    db.session.add(d)
    db.session.commit()
    return d


def _make_client_user(app, customer_id):
    from extensions import db
    from models.user import User
    uid, email, pw = create_user(app, role="client")
    u = db.session.get(User, uid)
    u.customer_id = customer_id
    db.session.commit()
    return uid, email, pw


def _cleanup(app, integration_ids=None, device_ids=None, customer_ids=None, user_ids=None):
    from extensions import db
    from models.mdm_integration import MdmIntegration, MobileEnrollment
    from models.device import Device
    from models.customer import Customer
    for did in (device_ids or []):
        MobileEnrollment.query.filter_by(device_id=did).delete()
        Device.query.filter_by(id=did).delete()
    for iid in (integration_ids or []):
        MobileEnrollment.query.filter_by(mdm_integration_id=iid).delete()
        MdmIntegration.query.filter_by(id=iid).delete()
    for cid in (customer_ids or []):
        Customer.query.filter_by(id=cid).delete()
    db.session.commit()
    for uid in (user_ids or []):
        delete_user(app, uid)


class TestIntegrationCrud:
    def test_create_requires_admin(self, app, client):
        uid, email, pw = create_user(app, role="technician")
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.post("/api/mdm/integrations", json={"name": "x", "project_id": "p"},
                           headers=auth_headers(tok))
            assert r.status_code == 403
        finally:
            _cleanup(app, user_ids=[uid])

    def test_admin_can_create_integration(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        integ_id = None
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.post("/api/mdm/integrations", json={"name": "acme android", "project_id": "acme-proj"},
                           headers=auth_headers(tok))
            assert r.status_code == 201
            body = r.get_json()
            assert body["type"] == "android"
            assert body["bound"] is False
            integ_id = body["id"]
        finally:
            _cleanup(app, integration_ids=[integ_id] if integ_id else [], user_ids=[uid])

    def test_upload_credentials_rejects_invalid_json(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        integ = _make_integration(app)
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.post(
                f"/api/mdm/integrations/{integ.id}/credentials",
                data={"file": (__import__("io").BytesIO(b"not json"), "sa.json")},
                headers=auth_headers(tok), content_type="multipart/form-data",
            )
            assert r.status_code == 400
        finally:
            _cleanup(app, integration_ids=[integ.id], user_ids=[uid])


class TestEnrollmentConsent:
    def test_requires_bound_integration(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        integ = _make_integration(app, bound=False)
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.post("/api/mdm/enrollments", json={"mdm_integration_id": integ.id},
                           headers=auth_headers(tok))
            assert r.status_code == 400
            assert "not bound" in r.get_json()["error"].lower()
        finally:
            _cleanup(app, integration_ids=[integ.id], user_ids=[uid])

    def test_client_cannot_enroll_without_consent(self, app, client):
        cust = _make_customer(app)
        integ = _make_integration(app, customer_id=cust.id, bound=True)
        uid, email, pw = _make_client_user(app, cust.id)
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.post("/api/mdm/enrollments",
                           json={"mdm_integration_id": integ.id, "ownership_type": "corporate"},
                           headers=auth_headers(tok))
            assert r.status_code == 400
            assert "consent" in r.get_json()["error"].lower()
        finally:
            _cleanup(app, integration_ids=[integ.id], customer_ids=[cust.id], user_ids=[uid])

    def test_client_cannot_enroll_into_foreign_customer_integration(self, app, client):
        cust_a = _make_customer(app)
        cust_b = _make_customer(app)
        integ = _make_integration(app, customer_id=cust_b.id, bound=True)
        uid, email, pw = _make_client_user(app, cust_a.id)
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.post("/api/mdm/enrollments",
                           json={"mdm_integration_id": integ.id, "consent_acknowledged": True},
                           headers=auth_headers(tok))
            assert r.status_code == 404
        finally:
            _cleanup(app, integration_ids=[integ.id], customer_ids=[cust_a.id, cust_b.id], user_ids=[uid])

    def test_client_enrollment_forced_to_byod(self, app, client, monkeypatch):
        from utils.android_mgmt import AndroidManagementClient
        monkeypatch.setattr(
            AndroidManagementClient, "create_enrollment_token",
            lambda self, **kw: {"value": "tok123", "qrCode": "{}"},
        )
        cust = _make_customer(app)
        integ = _make_integration(app, customer_id=cust.id, bound=True)
        uid, email, pw = _make_client_user(app, cust.id)
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.post(
                "/api/mdm/enrollments",
                json={"mdm_integration_id": integ.id, "ownership_type": "corporate",
                     "consent_acknowledged": True},
                headers=auth_headers(tok),
            )
            assert r.status_code == 201
            from extensions import db
            from models.mdm_integration import MobileEnrollment
            enrollment = MobileEnrollment.query.filter_by(id=r.get_json()["enrollment_id"]).first()
            # Server forces byod for client role even though body asked for corporate
            assert enrollment.ownership_type == "byod"
        finally:
            _cleanup(app, integration_ids=[integ.id], customer_ids=[cust.id], user_ids=[uid])


class TestDeviceCommands:
    def test_wipe_requires_admin(self, app, client):
        uid, email, pw = create_user(app, role="technician")
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.post("/api/mdm/devices/nonexistent-id/wipe", headers=auth_headers(tok))
            assert r.status_code == 403
        finally:
            _cleanup(app, user_ids=[uid])

    def test_lock_cross_tenant_blocked(self, app, client):
        cust_a = _make_customer(app)
        cust_b = _make_customer(app)
        dev = _make_device(app, cust_b.id)
        uid, email, pw = _make_client_user(app, cust_a.id)
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.post(f"/api/mdm/devices/{dev.id}/lock", headers=auth_headers(tok))
            assert r.status_code == 404
        finally:
            _cleanup(app, device_ids=[dev.id], customer_ids=[cust_a.id, cust_b.id], user_ids=[uid])

    def test_lock_rejects_unenrolled_device(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)  # no MobileEnrollment attached
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.post(f"/api/mdm/devices/{dev.id}/lock", headers=auth_headers(tok))
            assert r.status_code == 400
        finally:
            _cleanup(app, device_ids=[dev.id], customer_ids=[cust.id], user_ids=[uid])
