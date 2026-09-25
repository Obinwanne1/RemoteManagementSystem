"""Tests for routes/org_settings.py — org branding/contact settings CRUD,
logo upload, and the public unauthenticated branding endpoint
(audits/testing_audit.md Finding C2)."""
import io
import uuid
from conftest import create_user, delete_user, login, auth_headers


def _reset_settings(app):
    """org_settings is a singleton row (id=1) shared across the whole test
    session — restore it to a known-empty state after tests that mutate it,
    so other tests (and re-runs of this file) aren't order-dependent."""
    from extensions import db
    from models.org_settings import OrgSettings
    settings = db.session.get(OrgSettings, 1)
    if settings:
        for field in ["company_name", "company_address", "company_email", "company_phone",
                      "payment_terms", "bank_details", "footer_notes", "app_name",
                      "tagline", "primary_color", "currency", "timezone", "logo_data"]:
            setattr(settings, field, None)
        db.session.commit()


class TestGetOrgSettings:
    def test_requires_auth(self, client):
        r = client.get("/api/admin/org-settings")
        assert r.status_code == 401

    def test_any_authenticated_role_can_read(self, app, client):
        uid, email, pw = create_user(app, role="viewer")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.get("/api/admin/org-settings", headers=auth_headers(token))
            assert r.status_code == 200
            assert "id" in r.get_json()
        finally:
            delete_user(app, uid)


class TestUpdateOrgSettings:
    def test_requires_admin_role(self, app, client):
        uid, email, pw = create_user(app, role="technician")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.put("/api/admin/org-settings", headers=auth_headers(token),
                            json={"company_name": "Should Not Save"})
            assert r.status_code == 403
        finally:
            delete_user(app, uid)

    def test_admin_updates_fields(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            unique_name = f"Acme-{uuid.uuid4().hex[:6]}"
            r = client.put(
                "/api/admin/org-settings", headers=auth_headers(token),
                json={"company_name": unique_name, "currency": "EUR", "primary_color": "#123ABC"},
            )
            assert r.status_code == 200
            body = r.get_json()
            assert body["company_name"] == unique_name
            assert body["currency"] == "EUR"
            assert body["primary_color"] == "#123ABC"
        finally:
            _reset_settings(app)
            delete_user(app, uid)

    def test_rejects_invalid_color_format(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.put("/api/admin/org-settings", headers=auth_headers(token),
                            json={"primary_color": "not-a-hex-color"})
            assert r.status_code == 400
        finally:
            delete_user(app, uid)

    def test_rejects_invalid_email(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.put("/api/admin/org-settings", headers=auth_headers(token),
                            json={"company_email": "not-an-email"})
            assert r.status_code == 400
        finally:
            delete_user(app, uid)


class TestUploadLogo:
    def test_requires_admin_role(self, app, client):
        uid, email, pw = create_user(app, role="technician")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.put(
                "/api/admin/org-settings/logo", headers=auth_headers(token),
                data={"file": (io.BytesIO(b"fake"), "logo.png")},
                content_type="multipart/form-data",
            )
            assert r.status_code == 403
        finally:
            delete_user(app, uid)

    def test_requires_file(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.put("/api/admin/org-settings/logo", headers=auth_headers(token), data={})
            assert r.status_code == 400
        finally:
            delete_user(app, uid)

    def test_rejects_non_image_file(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.put(
                "/api/admin/org-settings/logo", headers=auth_headers(token),
                data={"file": (io.BytesIO(b"not an image"), "notes.txt", "text/plain")},
                content_type="multipart/form-data",
            )
            assert r.status_code == 400
        finally:
            delete_user(app, uid)

    def test_uploads_and_resizes_real_png(self, app, client):
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (800, 400), color=(255, 0, 0)).save(buf, format="PNG")
        buf.seek(0)

        uid, email, pw = create_user(app, role="admin")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.put(
                "/api/admin/org-settings/logo", headers=auth_headers(token),
                data={"file": (buf, "logo.png", "image/png")},
                content_type="multipart/form-data",
            )
            assert r.status_code == 200
            body = r.get_json()
            assert body["logo_data"].startswith("data:image/png;base64,")
        finally:
            _reset_settings(app)
            delete_user(app, uid)


class TestDeleteLogo:
    def test_requires_admin_role(self, app, client):
        uid, email, pw = create_user(app, role="technician")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.delete("/api/admin/org-settings/logo", headers=auth_headers(token))
            assert r.status_code == 403
        finally:
            delete_user(app, uid)

    def test_admin_removes_logo(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.delete("/api/admin/org-settings/logo", headers=auth_headers(token))
            assert r.status_code == 200
        finally:
            delete_user(app, uid)


class TestPublicBranding:
    def test_no_auth_required(self, client):
        r = client.get("/api/admin/public/branding")
        assert r.status_code == 200
        body = r.get_json()
        assert "app_name" in body
        assert "primary_color" in body

    def test_never_leaks_non_branding_fields(self, app, client):
        """The endpoint is unauthenticated by design — must only ever expose
        the 4 whitelisted branding fields, never company_email/bank_details/etc."""
        uid, email, pw = create_user(app, role="admin")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            client.put("/api/admin/org-settings", headers=auth_headers(token),
                       json={"company_email": "secret@internal.local", "bank_details": "IBAN12345"})
            r = client.get("/api/admin/public/branding")
            body = r.get_json()
            assert set(body.keys()) == {"app_name", "tagline", "primary_color", "logo_data"}
        finally:
            _reset_settings(app)
            delete_user(app, uid)
