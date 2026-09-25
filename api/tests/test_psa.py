"""Tests for routes/psa.py — PSA integration CRUD, connection test, manual
sync trigger, and company-map CRUD (audits/testing_audit.md Finding C2).

All outbound PSA network calls are mocked via PsaIntegration.get_client() —
never let a test try to reach a real ConnectWise/Autotask endpoint."""
import uuid
from unittest.mock import MagicMock, patch

from conftest import create_user, delete_user, login, auth_headers


def _make_customer(app):
    from extensions import db
    from models.customer import Customer
    c = Customer(name=f"PsaCo-{uuid.uuid4().hex[:6]}", slug=f"psac-{uuid.uuid4().hex[:6]}", is_active=True)
    db.session.add(c)
    db.session.commit()
    return c


def _cleanup(app, *, user_id=None, customer_id=None, integration_ids=(), map_ids=()):
    from extensions import db
    from models.customer import Customer
    from models.psa_integration import PsaIntegration, PsaCompanyMap
    for mid in map_ids:
        PsaCompanyMap.query.filter_by(id=mid).delete()
    for iid in integration_ids:
        PsaIntegration.query.filter_by(id=iid).delete()
    if customer_id:
        Customer.query.filter_by(id=customer_id).delete()
    db.session.commit()
    if user_id:
        delete_user(app, user_id)


def _create_integration(client, token, **overrides):
    payload = dict(
        name=f"Integration-{uuid.uuid4().hex[:6]}", type="connectwise",
        api_url="https://cw.example.invalid", company_id="cw-co-1",
        client_id="pub-key", client_secret="super-secret-value",
    )
    payload.update(overrides)
    return client.post("/api/psa/integrations", headers=auth_headers(token), json=payload)


class TestListIntegrations:
    def test_requires_auth(self, client):
        r = client.get("/api/psa/integrations")
        assert r.status_code == 401

    def test_viewer_forbidden(self, app, client):
        uid, email, pw = create_user(app, role="viewer")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.get("/api/psa/integrations", headers=auth_headers(token))
            assert r.status_code == 403
        finally:
            delete_user(app, uid)


class TestCreateIntegration:
    def test_requires_admin_not_just_technician(self, app, client):
        uid, email, pw = create_user(app, role="technician")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = _create_integration(client, token)
            assert r.status_code == 403
        finally:
            delete_user(app, uid)

    def test_rejects_unknown_type(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = _create_integration(client, token, type="not-a-real-psa")
            assert r.status_code == 400
        finally:
            delete_user(app, uid)

    def test_connectwise_requires_company_id(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = _create_integration(client, token, company_id=None)
            assert r.status_code == 400
        finally:
            delete_user(app, uid)

    def test_creates_and_never_leaks_secret(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        integration_id = None
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = _create_integration(client, token)
            assert r.status_code == 201
            body = r.get_json()
            integration_id = body["id"]
            assert "client_secret" not in body
            assert "client_secret_enc" not in body
            assert "super-secret-value" not in str(body)
        finally:
            _cleanup(app, user_id=uid, integration_ids=[integration_id] if integration_id else [])


class TestUpdateDeleteIntegration:
    def test_update_requires_admin(self, app, client):
        admin_uid, admin_email, admin_pw = create_user(app, role="admin")
        tech_uid, tech_email, tech_pw = create_user(app, role="technician")
        integration_id = None
        try:
            admin_token = login(client, admin_email, admin_pw).get_json()["access_token"]
            integration_id = _create_integration(client, admin_token).get_json()["id"]

            tech_token = login(client, tech_email, tech_pw).get_json()["access_token"]
            r = client.put(f"/api/psa/integrations/{integration_id}", headers=auth_headers(tech_token),
                            json={"name": "Hijacked"})
            assert r.status_code == 403
        finally:
            _cleanup(app, integration_ids=[integration_id] if integration_id else [])
            delete_user(app, admin_uid)
            delete_user(app, tech_uid)

    def test_update_changes_name(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        integration_id = None
        try:
            token = login(client, email, pw).get_json()["access_token"]
            integration_id = _create_integration(client, token).get_json()["id"]
            r = client.put(f"/api/psa/integrations/{integration_id}", headers=auth_headers(token),
                            json={"name": "Renamed Integration"})
            assert r.status_code == 200
            assert r.get_json()["name"] == "Renamed Integration"
        finally:
            _cleanup(app, user_id=uid, integration_ids=[integration_id] if integration_id else [])

    def test_delete_removes_integration(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            integration_id = _create_integration(client, token).get_json()["id"]
            r = client.delete(f"/api/psa/integrations/{integration_id}", headers=auth_headers(token))
            assert r.status_code == 200

            from models.psa_integration import PsaIntegration
            from extensions import db
            assert db.session.get(PsaIntegration, integration_id) is None
        finally:
            delete_user(app, uid)


class TestConnectionTest:
    def test_success_path_does_not_touch_real_network(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        integration_id = None
        try:
            token = login(client, email, pw).get_json()["access_token"]
            integration_id = _create_integration(client, token).get_json()["id"]

            fake_client = MagicMock()
            fake_client.test_connection.return_value = (True, "Connected OK")
            with patch("models.psa_integration.PsaIntegration.get_client", return_value=fake_client):
                r = client.post(f"/api/psa/integrations/{integration_id}/test", headers=auth_headers(token))
            assert r.status_code == 200
            assert r.get_json()["success"] is True
        finally:
            _cleanup(app, user_id=uid, integration_ids=[integration_id] if integration_id else [])

    def test_failure_path_records_sync_error_and_returns_502(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        integration_id = None
        try:
            token = login(client, email, pw).get_json()["access_token"]
            integration_id = _create_integration(client, token).get_json()["id"]

            fake_client = MagicMock()
            fake_client.test_connection.return_value = (False, "401 Unauthorized")
            with patch("models.psa_integration.PsaIntegration.get_client", return_value=fake_client):
                r = client.post(f"/api/psa/integrations/{integration_id}/test", headers=auth_headers(token))
            assert r.status_code == 502
            assert r.get_json()["success"] is False

            from models.psa_integration import PsaIntegration
            from extensions import db
            integ = db.session.get(PsaIntegration, integration_id)
            assert "401 Unauthorized" in integ.sync_error
        finally:
            _cleanup(app, user_id=uid, integration_ids=[integration_id] if integration_id else [])


class TestTriggerSync:
    def test_disabled_integration_rejected(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        integration_id = None
        try:
            token = login(client, email, pw).get_json()["access_token"]
            integration_id = _create_integration(client, token, is_active=False).get_json()["id"]
            r = client.post(f"/api/psa/integrations/{integration_id}/sync", headers=auth_headers(token))
            assert r.status_code == 400
        finally:
            _cleanup(app, user_id=uid, integration_ids=[integration_id] if integration_id else [])

    def test_active_integration_queues_celery_task(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        integration_id = None
        try:
            token = login(client, email, pw).get_json()["access_token"]
            integration_id = _create_integration(client, token).get_json()["id"]
            with patch("tasks.psa_tasks.sync_psa_integration.delay") as mock_delay:
                r = client.post(f"/api/psa/integrations/{integration_id}/sync", headers=auth_headers(token))
            assert r.status_code == 202
            mock_delay.assert_called_once_with(integration_id)
        finally:
            _cleanup(app, user_id=uid, integration_ids=[integration_id] if integration_id else [])


class TestCompanyMaps:
    def test_create_requires_customer_id_and_psa_company_id(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        integration_id = None
        try:
            token = login(client, email, pw).get_json()["access_token"]
            integration_id = _create_integration(client, token).get_json()["id"]
            r = client.post(f"/api/psa/integrations/{integration_id}/company-maps",
                             headers=auth_headers(token), json={})
            assert r.status_code == 400
        finally:
            _cleanup(app, user_id=uid, integration_ids=[integration_id] if integration_id else [])

    def test_create_then_upsert_on_second_call(self, app, client):
        """Same (integration, customer) pair posted twice must update, not
        duplicate — the route's own upsert logic via the unique constraint."""
        uid, email, pw = create_user(app, role="admin")
        cust = _make_customer(app)
        integration_id = None
        map_id = None
        try:
            token = login(client, email, pw).get_json()["access_token"]
            integration_id = _create_integration(client, token).get_json()["id"]

            r1 = client.post(f"/api/psa/integrations/{integration_id}/company-maps",
                              headers=auth_headers(token),
                              json={"customer_id": cust.id, "psa_company_id": "cw-100"})
            assert r1.status_code == 201
            map_id = r1.get_json()["id"]

            r2 = client.post(f"/api/psa/integrations/{integration_id}/company-maps",
                              headers=auth_headers(token),
                              json={"customer_id": cust.id, "psa_company_id": "cw-200"})
            assert r2.status_code == 200
            assert r2.get_json()["id"] == map_id
            assert r2.get_json()["psa_company_id"] == "cw-200"

            from models.psa_integration import PsaCompanyMap
            assert PsaCompanyMap.query.filter_by(psa_integration_id=integration_id, customer_id=cust.id).count() == 1
        finally:
            _cleanup(app, user_id=uid, customer_id=cust.id,
                     integration_ids=[integration_id] if integration_id else [],
                     map_ids=[map_id] if map_id else [])

    def test_delete_company_map(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        cust = _make_customer(app)
        integration_id = None
        try:
            token = login(client, email, pw).get_json()["access_token"]
            integration_id = _create_integration(client, token).get_json()["id"]
            r = client.post(f"/api/psa/integrations/{integration_id}/company-maps",
                             headers=auth_headers(token),
                             json={"customer_id": cust.id, "psa_company_id": "cw-1"})
            map_id = r.get_json()["id"]

            r = client.delete(f"/api/psa/integrations/{integration_id}/company-maps/{map_id}",
                               headers=auth_headers(token))
            assert r.status_code == 200
        finally:
            _cleanup(app, user_id=uid, customer_id=cust.id, integration_ids=[integration_id] if integration_id else [])


class TestFetchPsaCompanies:
    def test_returns_client_companies_without_real_network_call(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        integration_id = None
        try:
            token = login(client, email, pw).get_json()["access_token"]
            integration_id = _create_integration(client, token).get_json()["id"]

            fake_client = MagicMock()
            fake_client.get_companies.return_value = [{"id": "1", "name": "Acme", "identifier": "ACME"}]
            with patch("models.psa_integration.PsaIntegration.get_client", return_value=fake_client):
                r = client.get(f"/api/psa/integrations/{integration_id}/psa-companies", headers=auth_headers(token))
            assert r.status_code == 200
            assert r.get_json() == [{"id": "1", "name": "Acme", "identifier": "ACME"}]
        finally:
            _cleanup(app, user_id=uid, integration_ids=[integration_id] if integration_id else [])

    def test_client_exception_returns_502_not_500(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        integration_id = None
        try:
            token = login(client, email, pw).get_json()["access_token"]
            integration_id = _create_integration(client, token).get_json()["id"]

            fake_client = MagicMock()
            fake_client.get_companies.side_effect = ConnectionError("PSA unreachable")
            with patch("models.psa_integration.PsaIntegration.get_client", return_value=fake_client):
                r = client.get(f"/api/psa/integrations/{integration_id}/psa-companies", headers=auth_headers(token))
            assert r.status_code == 502
        finally:
            _cleanup(app, user_id=uid, integration_ids=[integration_id] if integration_id else [])
