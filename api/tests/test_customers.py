"""Customer + device group route tests (audits/testing_audit.md Finding C2
— customers.py had zero test coverage before this file)."""
import uuid
from conftest import create_user, delete_user, login, auth_headers


def _cleanup(app, *, user_ids=(), customer_ids=(), group_ids=(), device_ids=()):
    from extensions import db
    from models.customer import Customer, DeviceGroup
    from models.device import Device
    for gid in group_ids:
        DeviceGroup.query.filter_by(id=gid).delete()
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


def _make_customer(app, **kwargs):
    from extensions import db
    from models.customer import Customer
    defaults = dict(name=f"Co-{uuid.uuid4().hex[:6]}", slug=f"co-{uuid.uuid4().hex[:6]}", is_active=True)
    defaults.update(kwargs)
    c = Customer(**defaults)
    db.session.add(c)
    db.session.commit()
    return c


class TestListCustomers:
    def test_requires_auth(self, client):
        r = client.get("/api/customers/")
        assert r.status_code == 401

    def test_lists_active_customers(self, app, client):
        uid, email, pw = create_user(app, role="viewer")
        cust = _make_customer(app)
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.get("/api/customers/", headers=auth_headers(token))
            assert r.status_code == 200
            body = r.get_json()
            assert "items" in body and "pages" in body
            assert any(c["id"] == cust.id for c in body["items"])
        finally:
            _cleanup(app, user_ids=[uid], customer_ids=[cust.id])

    def test_inactive_customers_excluded(self, app, client):
        uid, email, pw = create_user(app, role="viewer")
        cust = _make_customer(app, is_active=False)
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.get("/api/customers/", headers=auth_headers(token))
            ids = [c["id"] for c in r.get_json()["items"]]
            assert cust.id not in ids
        finally:
            _cleanup(app, user_ids=[uid], customer_ids=[cust.id])

    def test_search_by_name(self, app, client):
        uid, email, pw = create_user(app, role="viewer")
        cust = _make_customer(app, name=f"Zephyr-{uuid.uuid4().hex[:6]}")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.get("/api/customers/?q=Zephyr", headers=auth_headers(token))
            ids = [c["id"] for c in r.get_json()["items"]]
            assert cust.id in ids
            r2 = client.get("/api/customers/?q=DoesNotExist", headers=auth_headers(token))
            assert cust.id not in [c["id"] for c in r2.get_json()["items"]]
        finally:
            _cleanup(app, user_ids=[uid], customer_ids=[cust.id])


class TestCreateCustomer:
    def test_requires_admin_or_technician(self, app, client):
        uid, email, pw = create_user(app, role="viewer")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.post("/api/customers/", headers=auth_headers(token), json={"name": "New Co"})
            assert r.status_code == 403
        finally:
            _cleanup(app, user_ids=[uid])

    def test_creates_with_generated_slug(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        name = f"Acme Corp {uuid.uuid4().hex[:6]}"
        created_id = None
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.post("/api/customers/", headers=auth_headers(token), json={"name": name})
            assert r.status_code == 201
            body = r.get_json()
            created_id = body["id"]
            assert body["name"] == name
            assert body["slug"]
        finally:
            _cleanup(app, user_ids=[uid], customer_ids=[created_id] if created_id else [])

    def test_rejects_missing_name(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.post("/api/customers/", headers=auth_headers(token), json={})
            assert r.status_code == 400
        finally:
            _cleanup(app, user_ids=[uid])

    def test_deduplicates_slug_on_name_collision(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        name = f"Dup Co {uuid.uuid4().hex[:6]}"
        ids = []
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r1 = client.post("/api/customers/", headers=auth_headers(token), json={"name": name})
            r2 = client.post("/api/customers/", headers=auth_headers(token), json={"name": name})
            ids = [r1.get_json()["id"], r2.get_json()["id"]]
            assert r1.get_json()["slug"] != r2.get_json()["slug"]
        finally:
            _cleanup(app, user_ids=[uid], customer_ids=ids)


class TestGetUpdateDeleteCustomer:
    def test_get_missing_customer_404s(self, app, client):
        uid, email, pw = create_user(app, role="viewer")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.get("/api/customers/does-not-exist", headers=auth_headers(token))
            assert r.status_code == 404
        finally:
            _cleanup(app, user_ids=[uid])

    def test_get_includes_counts(self, app, client):
        uid, email, pw = create_user(app, role="viewer")
        cust = _make_customer(app)
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.get(f"/api/customers/{cust.id}", headers=auth_headers(token))
            assert r.status_code == 200
            assert "device_count" in r.get_json()
        finally:
            _cleanup(app, user_ids=[uid], customer_ids=[cust.id])

    def test_update_requires_admin_or_technician(self, app, client):
        uid, email, pw = create_user(app, role="viewer")
        cust = _make_customer(app)
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.put(f"/api/customers/{cust.id}", headers=auth_headers(token), json={"name": "Hacked"})
            assert r.status_code == 403
        finally:
            _cleanup(app, user_ids=[uid], customer_ids=[cust.id])

    def test_admin_updates_customer(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        cust = _make_customer(app)
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.put(f"/api/customers/{cust.id}", headers=auth_headers(token), json={"tier": "enterprise"})
            assert r.status_code == 200
            assert r.get_json()["tier"] == "enterprise"
        finally:
            _cleanup(app, user_ids=[uid], customer_ids=[cust.id])

    def test_delete_requires_admin(self, app, client):
        uid, email, pw = create_user(app, role="technician")
        cust = _make_customer(app)
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.delete(f"/api/customers/{cust.id}", headers=auth_headers(token))
            assert r.status_code == 403
        finally:
            _cleanup(app, user_ids=[uid], customer_ids=[cust.id])

    def test_admin_delete_is_soft(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        cust = _make_customer(app)
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.delete(f"/api/customers/{cust.id}", headers=auth_headers(token))
            assert r.status_code == 200
            from extensions import db
            from models.customer import Customer
            db.session.refresh(cust)
            assert cust.is_active is False
        finally:
            _cleanup(app, user_ids=[uid], customer_ids=[cust.id])


class TestCustomerDevices:
    def test_returns_devices_with_latest_metrics(self, app, client):
        from extensions import db
        from models.device import Device, DeviceMetrics
        uid, email, pw = create_user(app, role="viewer")
        cust = _make_customer(app)
        dev = Device(hostname=f"h-{uuid.uuid4().hex[:6]}", customer_id=cust.id, platform="windows")
        db.session.add(dev)
        db.session.commit()
        metrics = DeviceMetrics(device_id=dev.id, cpu_pct=42.0)
        db.session.add(metrics)
        db.session.commit()
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.get(f"/api/customers/{cust.id}/devices", headers=auth_headers(token))
            assert r.status_code == 200
            body = r.get_json()
            assert len(body) == 1
            assert body[0]["id"] == dev.id
        finally:
            DeviceMetrics.query.filter_by(device_id=dev.id).delete()
            _cleanup(app, user_ids=[uid], customer_ids=[cust.id], device_ids=[dev.id])

    def test_missing_customer_404s(self, app, client):
        uid, email, pw = create_user(app, role="viewer")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.get("/api/customers/does-not-exist/devices", headers=auth_headers(token))
            assert r.status_code == 404
        finally:
            _cleanup(app, user_ids=[uid])


class TestDeviceGroups:
    def test_list_requires_role(self, app, client):
        uid, email, pw = create_user(app, role="client")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.get("/api/customers/groups", headers=auth_headers(token))
            assert r.status_code == 403
        finally:
            _cleanup(app, user_ids=[uid])

    def test_create_requires_name_and_customer_id(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.post("/api/customers/groups", headers=auth_headers(token), json={"name": "Group A"})
            assert r.status_code == 400
        finally:
            _cleanup(app, user_ids=[uid])

    def test_create_and_list_group(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        cust = _make_customer(app)
        group_id = None
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.post(
                "/api/customers/groups", headers=auth_headers(token),
                json={"name": "Servers", "customer_id": cust.id},
            )
            assert r.status_code == 201
            group_id = r.get_json()["id"]

            r2 = client.get(f"/api/customers/groups?customer_id={cust.id}", headers=auth_headers(token))
            assert any(g["id"] == group_id for g in r2.get_json()["items"])
        finally:
            _cleanup(app, user_ids=[uid], customer_ids=[cust.id], group_ids=[group_id] if group_id else [])
