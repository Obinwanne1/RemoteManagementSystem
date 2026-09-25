"""IoT sensor ingestion/query tests (audits/testing_audit.md Finding C2 —
sensors.py had zero test coverage before, measured at 21%). Covers both the
JWT-authenticated dashboard endpoints and the agent-Bearer-token push endpoint."""
import hashlib
import uuid
from conftest import create_user, delete_user, login, auth_headers


def _make_customer(app):
    from extensions import db
    from models.customer import Customer
    c = Customer(name=f"SensorCo-{uuid.uuid4().hex[:6]}", slug=f"sn-{uuid.uuid4().hex[:6]}", is_active=True)
    db.session.add(c)
    db.session.commit()
    return c


def _make_device(app, customer_id):
    from extensions import db
    from models.device import Device
    d = Device(
        hostname=f"host-{uuid.uuid4().hex[:6]}", customer_id=customer_id,
        platform="linux", os_name="Raspbian", ip_address="10.0.0.5", is_online=True,
    )
    db.session.add(d)
    db.session.commit()
    return d


def _make_agent_token(app, device_id, raw_token="raw-agent-token-for-tests"):
    from extensions import db
    from models.audit import AgentToken
    at = AgentToken(device_id=device_id, token_hash=hashlib.sha256(raw_token.encode()).hexdigest())
    db.session.add(at)
    db.session.commit()
    return raw_token


def _cleanup(app, *, device_ids=(), customer_id=None, user_id=None):
    from extensions import db
    from models.device import Device, DeviceSensorReading
    from models.audit import AgentToken
    from models.customer import Customer
    for did in device_ids:
        AgentToken.query.filter_by(device_id=did).delete()
        DeviceSensorReading.query.filter_by(device_id=did).delete()
        Device.query.filter_by(id=did).delete()
    if customer_id:
        Customer.query.filter_by(id=customer_id).delete()
    db.session.commit()
    if user_id:
        delete_user(app, user_id)


class TestPushSensorData:
    def test_rejects_missing_token(self, app, client):
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        try:
            r = client.post(f"/api/sensors/{dev.id}/data", json=[{"sensor_type": "temperature", "value": 21.5}])
            assert r.status_code == 401
        finally:
            _cleanup(app, device_ids=[dev.id], customer_id=cust.id)

    def test_rejects_invalid_token(self, app, client):
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        try:
            r = client.post(
                f"/api/sensors/{dev.id}/data",
                headers={"Authorization": "Bearer not-a-real-token"},
                json=[{"sensor_type": "temperature", "value": 21.5}],
            )
            assert r.status_code == 401
        finally:
            _cleanup(app, device_ids=[dev.id], customer_id=cust.id)

    def test_inserts_valid_readings(self, app, client):
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        try:
            raw_token = _make_agent_token(app, dev.id)
            r = client.post(
                f"/api/sensors/{dev.id}/data",
                headers={"Authorization": f"Bearer {raw_token}"},
                json=[
                    {"sensor_type": "temperature", "value": 21.5, "unit": "C"},
                    {"sensor_type": "humidity", "value": 45.0, "unit": "%"},
                ],
            )
            assert r.status_code == 200
            body = r.get_json()
            assert body["inserted"] == 2
            assert "errors" not in body
        finally:
            _cleanup(app, device_ids=[dev.id], customer_id=cust.id)

    def test_rejects_unknown_sensor_type(self, app, client):
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        try:
            raw_token = _make_agent_token(app, dev.id)
            r = client.post(
                f"/api/sensors/{dev.id}/data",
                headers={"Authorization": f"Bearer {raw_token}"},
                json=[{"sensor_type": "not_a_real_sensor", "value": 1.0}],
            )
            assert r.status_code == 400
            body = r.get_json()
            assert body["inserted"] == 0
            assert len(body["errors"]) == 1
        finally:
            _cleanup(app, device_ids=[dev.id], customer_id=cust.id)

    def test_partial_success_returns_200_with_errors_list(self, app, client):
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        try:
            raw_token = _make_agent_token(app, dev.id)
            r = client.post(
                f"/api/sensors/{dev.id}/data",
                headers={"Authorization": f"Bearer {raw_token}"},
                json=[
                    {"sensor_type": "temperature", "value": 21.5},
                    {"sensor_type": "co2", "value": "not-a-number"},
                ],
            )
            assert r.status_code == 200
            body = r.get_json()
            assert body["inserted"] == 1
            assert len(body["errors"]) == 1
        finally:
            _cleanup(app, device_ids=[dev.id], customer_id=cust.id)

    def test_rejects_non_array_body(self, app, client):
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        try:
            raw_token = _make_agent_token(app, dev.id)
            r = client.post(
                f"/api/sensors/{dev.id}/data",
                headers={"Authorization": f"Bearer {raw_token}"},
                json={"sensor_type": "temperature", "value": 21.5},  # object, not array
            )
            assert r.status_code == 400
        finally:
            _cleanup(app, device_ids=[dev.id], customer_id=cust.id)

    def test_rejects_batch_over_max_size(self, app, client):
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        try:
            raw_token = _make_agent_token(app, dev.id)
            oversized = [{"sensor_type": "temperature", "value": 1.0} for _ in range(101)]
            r = client.post(
                f"/api/sensors/{dev.id}/data",
                headers={"Authorization": f"Bearer {raw_token}"},
                json=oversized,
            )
            assert r.status_code == 400
        finally:
            _cleanup(app, device_ids=[dev.id], customer_id=cust.id)

    def test_revoked_token_is_rejected(self, app, client):
        from extensions import db
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        try:
            raw_token = _make_agent_token(app, dev.id)
            from models.audit import AgentToken
            AgentToken.query.filter_by(device_id=dev.id).update({"is_revoked": True})
            db.session.commit()

            r = client.post(
                f"/api/sensors/{dev.id}/data",
                headers={"Authorization": f"Bearer {raw_token}"},
                json=[{"sensor_type": "temperature", "value": 21.5}],
            )
            assert r.status_code == 401
        finally:
            _cleanup(app, device_ids=[dev.id], customer_id=cust.id)


class TestGetSensorData:
    def test_requires_auth(self, app, client):
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        try:
            r = client.get(f"/api/sensors/{dev.id}/data")
            assert r.status_code == 401
        finally:
            _cleanup(app, device_ids=[dev.id], customer_id=cust.id)

    def test_returns_readings_for_device(self, app, client):
        admin_uid, admin_email, admin_pw = create_user(app, role="admin")
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        try:
            raw_token = _make_agent_token(app, dev.id)
            client.post(
                f"/api/sensors/{dev.id}/data",
                headers={"Authorization": f"Bearer {raw_token}"},
                json=[{"sensor_type": "temperature", "value": 21.5}],
            )
            token = login(client, admin_email, admin_pw).get_json()["access_token"]
            r = client.get(f"/api/sensors/{dev.id}/data", headers=auth_headers(token))
            assert r.status_code == 200
            body = r.get_json()
            assert len(body) == 1
            assert body[0]["sensor_type"] == "temperature"
        finally:
            _cleanup(app, device_ids=[dev.id], customer_id=cust.id, user_id=admin_uid)

    def test_client_role_blocked_from_other_customers_device(self, app, client):
        from extensions import db
        from models.user import User
        client_uid, client_email, client_pw = create_user(app, role="client")
        own_cust = _make_customer(app)
        other_cust = _make_customer(app)
        other_dev = _make_device(app, other_cust.id)
        try:
            u = db.session.get(User, client_uid)
            u.customer_id = own_cust.id
            db.session.commit()

            token = login(client, client_email, client_pw).get_json()["access_token"]
            r = client.get(f"/api/sensors/{other_dev.id}/data", headers=auth_headers(token))
            assert r.status_code == 403
        finally:
            _cleanup(app, device_ids=[other_dev.id], customer_id=own_cust.id, user_id=client_uid)
            from models.customer import Customer
            Customer.query.filter_by(id=other_cust.id).delete()
            db.session.commit()


class TestSensorSummary:
    def test_requires_admin_or_technician_role(self, app, client):
        uid, email, pw = create_user(app, role="viewer")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.get("/api/sensors/summary", headers=auth_headers(token))
            assert r.status_code == 403
        finally:
            _cleanup(app, user_id=uid)

    def test_admin_gets_summary_list(self, app, client):
        admin_uid, admin_email, admin_pw = create_user(app, role="admin")
        try:
            token = login(client, admin_email, admin_pw).get_json()["access_token"]
            r = client.get("/api/sensors/summary", headers=auth_headers(token))
            assert r.status_code == 200
            assert isinstance(r.get_json(), list)
        finally:
            _cleanup(app, user_id=admin_uid)
