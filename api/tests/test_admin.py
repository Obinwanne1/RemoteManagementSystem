"""Admin route tests — user CRUD, role gating, org-token exposure, and GDPR
Art. 17/20 export/delete (audits/testing_audit.md Finding C2 — this file had
zero test coverage before, measured at 21%)."""
from conftest import create_user, delete_user, login, auth_headers


def _cleanup(app, user_ids):
    for uid in user_ids:
        try:
            delete_user(app, uid)
        except Exception:
            pass


class TestListUsers:
    def test_requires_auth(self, client):
        r = client.get("/api/admin/users")
        assert r.status_code == 401

    def test_non_admin_gets_403(self, app, client):
        uid, email, pw = create_user(app, role="technician")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.get("/api/admin/users", headers=auth_headers(token))
            assert r.status_code == 403
        finally:
            _cleanup(app, [uid])

    def test_admin_sees_paginated_items(self, app, client):
        admin_uid, admin_email, admin_pw = create_user(app, role="admin")
        try:
            token = login(client, admin_email, admin_pw).get_json()["access_token"]
            r = client.get("/api/admin/users", headers=auth_headers(token))
            assert r.status_code == 200
            body = r.get_json()
            # "items" not "users" — see audits/code_duplication_audit.md Finding N2,
            # which fixed a real bug where frontend/src/pages/AdminPage.tsx read
            # data.items from a response that only ever had "users".
            assert "items" in body
            assert "pages" in body
            assert any(u["email"] == admin_email for u in body["items"])
        finally:
            _cleanup(app, [admin_uid])


class TestCreateUser:
    def test_requires_admin_role(self, app, client):
        uid, email, pw = create_user(app, role="viewer")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.post(
                "/api/admin/users", headers=auth_headers(token),
                json={"email": "new@test.local", "full_name": "New Guy", "password": "GoodPass@1!"},
            )
            assert r.status_code == 403
        finally:
            _cleanup(app, [uid])

    def test_admin_creates_user_successfully(self, app, client):
        admin_uid, admin_email, admin_pw = create_user(app, role="admin")
        new_email = f"created_{admin_uid[:8]}@test.local"
        try:
            token = login(client, admin_email, admin_pw).get_json()["access_token"]
            r = client.post(
                "/api/admin/users", headers=auth_headers(token),
                json={"email": new_email, "full_name": "Created User", "password": "GoodPass@1!", "role": "technician"},
            )
            assert r.status_code == 201
            body = r.get_json()
            assert body["email"] == new_email
            assert "password_hash" not in body  # see test_serialization.py's sibling assertions
        finally:
            from models.user import User
            created = User.query.filter_by(email=new_email).first()
            _cleanup(app, [admin_uid] + ([created.id] if created else []))

    def test_rejects_duplicate_email(self, app, client):
        admin_uid, admin_email, admin_pw = create_user(app, role="admin")
        try:
            token = login(client, admin_email, admin_pw).get_json()["access_token"]
            r = client.post(
                "/api/admin/users", headers=auth_headers(token),
                json={"email": admin_email, "full_name": "Dup", "password": "GoodPass@1!"},
            )
            assert r.status_code == 409
        finally:
            _cleanup(app, [admin_uid])

    def test_client_role_requires_customer_id(self, app, client):
        admin_uid, admin_email, admin_pw = create_user(app, role="admin")
        try:
            token = login(client, admin_email, admin_pw).get_json()["access_token"]
            r = client.post(
                "/api/admin/users", headers=auth_headers(token),
                json={"email": "client@test.local", "full_name": "Client", "password": "GoodPass@1!", "role": "client"},
            )
            assert r.status_code == 400
        finally:
            _cleanup(app, [admin_uid])


class TestUpdateUser:
    def test_superadmin_cannot_be_modified(self, app, client):
        # ensure_superadmin() normally seeds one at real API startup, but the test
        # app's create_app() runs before conftest.py's db.create_all() (see the
        # "Could not ensure superadmin (DB may not be ready yet)" warning at suite
        # startup) — so the test DB never gets one for free; create it directly.
        admin_uid, admin_email, admin_pw = create_user(app, role="admin")
        sa_uid, _, _ = create_user(app, role="superadmin")
        try:
            token = login(client, admin_email, admin_pw).get_json()["access_token"]
            r = client.put(
                f"/api/admin/users/{sa_uid}", headers=auth_headers(token),
                json={"full_name": "Hijacked"},
            )
            assert r.status_code == 403
        finally:
            _cleanup(app, [admin_uid, sa_uid])

    def test_admin_can_change_role(self, app, client):
        admin_uid, admin_email, admin_pw = create_user(app, role="admin")
        target_uid, _, _ = create_user(app, role="viewer")
        try:
            token = login(client, admin_email, admin_pw).get_json()["access_token"]
            r = client.put(
                f"/api/admin/users/{target_uid}", headers=auth_headers(token),
                json={"role": "technician"},
            )
            assert r.status_code == 200
            assert r.get_json()["role"] == "technician"
        finally:
            _cleanup(app, [admin_uid, target_uid])

    def test_rejects_invalid_role(self, app, client):
        admin_uid, admin_email, admin_pw = create_user(app, role="admin")
        target_uid, _, _ = create_user(app, role="viewer")
        try:
            token = login(client, admin_email, admin_pw).get_json()["access_token"]
            r = client.put(
                f"/api/admin/users/{target_uid}", headers=auth_headers(token),
                json={"role": "not-a-real-role"},
            )
            assert r.status_code == 400
        finally:
            _cleanup(app, [admin_uid, target_uid])


class TestDeleteUser:
    def test_cannot_delete_own_account(self, app, client):
        admin_uid, admin_email, admin_pw = create_user(app, role="admin")
        try:
            token = login(client, admin_email, admin_pw).get_json()["access_token"]
            r = client.delete(f"/api/admin/users/{admin_uid}", headers=auth_headers(token))
            assert r.status_code == 400
        finally:
            _cleanup(app, [admin_uid])

    def test_soft_deletes_and_scrambles_email(self, app, client):
        admin_uid, admin_email, admin_pw = create_user(app, role="admin")
        target_uid, target_email, _ = create_user(app, role="viewer")
        try:
            token = login(client, admin_email, admin_pw).get_json()["access_token"]
            r = client.delete(f"/api/admin/users/{target_uid}", headers=auth_headers(token))
            assert r.status_code == 200
            from models.user import User
            target = db_get(User, target_uid)
            assert target.is_active is False
            assert target.email != target_email
            assert target.email.startswith("__deleted__")
        finally:
            _cleanup(app, [admin_uid, target_uid])


class TestOrgToken:
    def test_requires_admin_role(self, app, client):
        uid, email, pw = create_user(app, role="technician")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.get("/api/admin/org-token", headers=auth_headers(token))
            assert r.status_code == 403
        finally:
            _cleanup(app, [uid])

    def test_admin_receives_token(self, app, client):
        admin_uid, admin_email, admin_pw = create_user(app, role="admin")
        try:
            token = login(client, admin_email, admin_pw).get_json()["access_token"]
            r = client.get("/api/admin/org-token", headers=auth_headers(token))
            assert r.status_code == 200
            assert "org_token" in r.get_json()
        finally:
            _cleanup(app, [admin_uid])


class TestGdprExport:
    def test_requires_admin_role(self, app, client):
        uid, email, pw = create_user(app, role="viewer")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.get(f"/api/admin/users/{uid}/gdpr-export", headers=auth_headers(token))
            assert r.status_code == 403
        finally:
            _cleanup(app, [uid])

    def test_export_contains_expected_sections(self, app, client):
        admin_uid, admin_email, admin_pw = create_user(app, role="admin")
        target_uid, target_email, _ = create_user(app, role="viewer")
        try:
            token = login(client, admin_email, admin_pw).get_json()["access_token"]
            r = client.get(f"/api/admin/users/{target_uid}/gdpr-export", headers=auth_headers(token))
            assert r.status_code == 200
            body = r.get_json()
            assert body["user"]["email"] == target_email
            assert "audit_log" in body
            assert "ticket_comments" in body
        finally:
            _cleanup(app, [admin_uid, target_uid])


class TestGdprDelete:
    def test_cannot_anonymize_own_account(self, app, client):
        admin_uid, admin_email, admin_pw = create_user(app, role="admin")
        try:
            token = login(client, admin_email, admin_pw).get_json()["access_token"]
            r = client.delete(f"/api/admin/users/{admin_uid}/gdpr-delete", headers=auth_headers(token))
            assert r.status_code == 400
        finally:
            _cleanup(app, [admin_uid])

    def test_anonymizes_pii(self, app, client):
        """Regression test for Art. 17 — irreversible, so this is the only real
        proof the anonymization logic actually scrubs what it claims to."""
        admin_uid, admin_email, admin_pw = create_user(app, role="admin")
        target_uid, target_email, _ = create_user(app, role="viewer")
        try:
            token = login(client, admin_email, admin_pw).get_json()["access_token"]
            r = client.delete(f"/api/admin/users/{target_uid}/gdpr-delete", headers=auth_headers(token))
            assert r.status_code == 200
            from models.user import User
            target = db_get(User, target_uid)
            assert target.email != target_email
            assert target.email.startswith("__anon__")
            assert target.password_hash == ""
            assert target.is_active is False
        finally:
            _cleanup(app, [admin_uid, target_uid])


def db_get(model, id_):
    from extensions import db
    return db.session.get(model, id_)
