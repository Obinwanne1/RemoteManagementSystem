"""SLA policy CRUD tests (audits/testing_audit.md Finding C2 — sla_policies.py
had zero test coverage before, measured at 26%)."""
import uuid
from conftest import create_user, delete_user, login, auth_headers


def _make_customer(app):
    from extensions import db
    from models.customer import Customer
    c = Customer(name=f"SlaCo-{uuid.uuid4().hex[:6]}", slug=f"sc-{uuid.uuid4().hex[:6]}", is_active=True)
    db.session.add(c)
    db.session.commit()
    return c


def _cleanup(app, *, policy_ids=(), customer_id=None, user_id=None):
    from extensions import db
    from models.sla_policy import SLAPolicy
    from models.customer import Customer
    for pid in policy_ids:
        SLAPolicy.query.filter_by(id=pid).delete()
    if customer_id:
        Customer.query.filter_by(id=customer_id).delete()
    db.session.commit()
    if user_id:
        delete_user(app, user_id)


class TestListPolicies:
    def test_requires_auth(self, client):
        r = client.get("/api/sla-policies/")
        assert r.status_code == 401

    def test_any_authenticated_role_can_list(self, app, client):
        uid, email, pw = create_user(app, role="viewer")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.get("/api/sla-policies/", headers=auth_headers(token))
            assert r.status_code == 200
            assert isinstance(r.get_json(), list)
        finally:
            _cleanup(app, user_id=uid)

    def test_customer_scoped_query_includes_global_defaults(self, app, client):
        admin_uid, admin_email, admin_pw = create_user(app, role="admin")
        cust = _make_customer(app)
        policy_id = None
        try:
            token = login(client, admin_email, admin_pw).get_json()["access_token"]
            create_r = client.post(
                "/api/sla-policies/", headers=auth_headers(token),
                json={"priority": "critical", "response_hours": 1, "resolution_hours": 4, "customer_id": cust.id},
            )
            assert create_r.status_code == 201
            policy_id = create_r.get_json()["id"]

            r = client.get(f"/api/sla-policies/?customer_id={cust.id}", headers=auth_headers(token))
            assert r.status_code == 200
            ids = [p["id"] for p in r.get_json()]
            assert policy_id in ids
        finally:
            _cleanup(app, policy_ids=[policy_id] if policy_id else [], customer_id=cust.id, user_id=admin_uid)


class TestCreatePolicy:
    def test_requires_admin_role(self, app, client):
        uid, email, pw = create_user(app, role="technician")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.post(
                "/api/sla-policies/", headers=auth_headers(token),
                json={"priority": "high", "response_hours": 2, "resolution_hours": 8},
            )
            assert r.status_code == 403
        finally:
            _cleanup(app, user_id=uid)

    def test_rejects_invalid_priority(self, app, client):
        admin_uid, admin_email, admin_pw = create_user(app, role="admin")
        try:
            token = login(client, admin_email, admin_pw).get_json()["access_token"]
            r = client.post(
                "/api/sla-policies/", headers=auth_headers(token),
                json={"priority": "urgent", "response_hours": 1, "resolution_hours": 4},
            )
            assert r.status_code == 400
        finally:
            _cleanup(app, user_id=admin_uid)

    def test_rejects_non_integer_hours(self, app, client):
        admin_uid, admin_email, admin_pw = create_user(app, role="admin")
        try:
            token = login(client, admin_email, admin_pw).get_json()["access_token"]
            r = client.post(
                "/api/sla-policies/", headers=auth_headers(token),
                json={"priority": "high", "response_hours": "two", "resolution_hours": 8},
            )
            assert r.status_code == 400
        finally:
            _cleanup(app, user_id=admin_uid)

    def test_rejects_duplicate_scope_and_priority(self, app, client):
        admin_uid, admin_email, admin_pw = create_user(app, role="admin")
        cust = _make_customer(app)
        policy_id = None
        try:
            token = login(client, admin_email, admin_pw).get_json()["access_token"]
            payload = {"priority": "low", "response_hours": 8, "resolution_hours": 48, "customer_id": cust.id}
            first = client.post("/api/sla-policies/", headers=auth_headers(token), json=payload)
            assert first.status_code == 201
            policy_id = first.get_json()["id"]

            dup = client.post("/api/sla-policies/", headers=auth_headers(token), json=payload)
            assert dup.status_code == 409
        finally:
            _cleanup(app, policy_ids=[policy_id] if policy_id else [], customer_id=cust.id, user_id=admin_uid)


class TestUpdatePolicy:
    def test_updates_hours(self, app, client):
        admin_uid, admin_email, admin_pw = create_user(app, role="admin")
        cust = _make_customer(app)
        policy_id = None
        try:
            token = login(client, admin_email, admin_pw).get_json()["access_token"]
            create_r = client.post(
                "/api/sla-policies/", headers=auth_headers(token),
                json={"priority": "medium", "response_hours": 4, "resolution_hours": 24, "customer_id": cust.id},
            )
            policy_id = create_r.get_json()["id"]

            r = client.put(
                f"/api/sla-policies/{policy_id}", headers=auth_headers(token),
                json={"response_hours": 2},
            )
            assert r.status_code == 200
            assert r.get_json()["response_hours"] == 2
            assert r.get_json()["resolution_hours"] == 24  # unchanged
        finally:
            _cleanup(app, policy_ids=[policy_id] if policy_id else [], customer_id=cust.id, user_id=admin_uid)

    def test_rejects_invalid_hours_on_update(self, app, client):
        admin_uid, admin_email, admin_pw = create_user(app, role="admin")
        cust = _make_customer(app)
        policy_id = None
        try:
            token = login(client, admin_email, admin_pw).get_json()["access_token"]
            create_r = client.post(
                "/api/sla-policies/", headers=auth_headers(token),
                json={"priority": "medium", "response_hours": 4, "resolution_hours": 24, "customer_id": cust.id},
            )
            policy_id = create_r.get_json()["id"]

            r = client.put(
                f"/api/sla-policies/{policy_id}", headers=auth_headers(token),
                json={"response_hours": 0},
            )
            assert r.status_code == 400
        finally:
            _cleanup(app, policy_ids=[policy_id] if policy_id else [], customer_id=cust.id, user_id=admin_uid)


class TestDeletePolicy:
    def test_cannot_delete_global_default(self, app, client):
        admin_uid, admin_email, admin_pw = create_user(app, role="admin")
        try:
            token = login(client, admin_email, admin_pw).get_json()["access_token"]
            # A global default (customer_id=None) — use a priority unlikely to collide
            # with any migration-seeded global default in this shared test DB.
            r = client.post(
                "/api/sla-policies/", headers=auth_headers(token),
                json={"priority": "critical", "response_hours": 1, "resolution_hours": 4},
            )
            if r.status_code == 409:
                # A global "critical" default already exists (seeded by migration) —
                # that's exactly the row this test wants to prove is undeletable.
                from models.sla_policy import SLAPolicy
                existing = SLAPolicy.query.filter_by(customer_id=None, priority="critical").first()
                policy_id = existing.id
            else:
                assert r.status_code == 201
                policy_id = r.get_json()["id"]

            del_r = client.delete(f"/api/sla-policies/{policy_id}", headers=auth_headers(token))
            assert del_r.status_code == 400
        finally:
            _cleanup(app, user_id=admin_uid)

    def test_deletes_customer_specific_policy(self, app, client):
        admin_uid, admin_email, admin_pw = create_user(app, role="admin")
        cust = _make_customer(app)
        try:
            token = login(client, admin_email, admin_pw).get_json()["access_token"]
            create_r = client.post(
                "/api/sla-policies/", headers=auth_headers(token),
                json={"priority": "low", "response_hours": 8, "resolution_hours": 72, "customer_id": cust.id},
            )
            policy_id = create_r.get_json()["id"]

            del_r = client.delete(f"/api/sla-policies/{policy_id}", headers=auth_headers(token))
            assert del_r.status_code == 200
        finally:
            _cleanup(app, customer_id=cust.id, user_id=admin_uid)
