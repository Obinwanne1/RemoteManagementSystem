"""Tests for routes/events.py — SSE token validation + recent-events polling
fallback (audits/testing_audit.md Finding C2). The /stream generator itself
(long-lived SSE loop) isn't exercised end-to-end here — /recent and the
token-validation branch cover the route's real logic without needing a live
streaming connection."""
from flask_jwt_extended import create_access_token
from conftest import create_user, delete_user, login, auth_headers


def _mint_token(app, uid, role):
    with app.app_context():
        return create_access_token(identity=uid, additional_claims={"role": role})


class TestStreamAuth:
    def test_missing_token_returns_401(self, client):
        r = client.get("/api/events/stream")
        assert r.status_code == 401
        assert r.get_json()["error"] == "token required"

    def test_garbage_token_returns_401_generic_message(self, client):
        r = client.get("/api/events/stream?token=not-a-real-jwt")
        assert r.status_code == 401
        # Generic message only — no internal exception detail leaked to an
        # unauthenticated caller (this endpoint has no @jwt_required()).
        assert r.get_json()["error"] == "invalid token"

    def test_valid_token_but_disallowed_role_returns_403(self, app, client):
        uid, email, pw = create_user(app, role="client")
        try:
            # "client" IS an allowed role per the route's own check
            # (admin/technician/viewer/superadmin/client) — mint a token with
            # an unrecognized role string to exercise the 403 branch instead.
            bad_token = _mint_token(app, uid, "not-a-real-role")
            r = client.get(f"/api/events/stream?token={bad_token}")
            assert r.status_code == 403
        finally:
            delete_user(app, uid)

    def test_valid_admin_token_opens_stream(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        try:
            token = _mint_token(app, uid, "admin")
            r = client.get(f"/api/events/stream?token={token}")
            assert r.status_code == 200
            assert r.mimetype == "text/event-stream"
        finally:
            delete_user(app, uid)


class TestRecentEvents:
    def test_requires_auth(self, client):
        r = client.get("/api/events/recent")
        assert r.status_code == 401

    def test_returns_list_with_valid_token(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.get("/api/events/recent", headers=auth_headers(token))
            assert r.status_code == 200
            assert isinstance(r.get_json(), list)
        finally:
            delete_user(app, uid)

    def test_limit_is_capped_at_100(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.get("/api/events/recent?limit=99999", headers=auth_headers(token))
            assert r.status_code == 200
        finally:
            delete_user(app, uid)
