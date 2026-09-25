"""Auth flow tests — login, lockout, MFA, refresh, password management."""
import pyotp
import pytest
from conftest import create_user, delete_user, login, auth_headers


# ── Login ──────────────────────────────────────────────────────────────────────

class TestLogin:
    def test_success(self, app, client):
        uid, email, pw = create_user(app)
        try:
            r = login(client, email, pw)
            assert r.status_code == 200
            body = r.get_json()
            assert "access_token" in body
            assert "refresh_token" in body
            assert body["user"]["email"] == email
        finally:
            delete_user(app, uid)

    def test_wrong_password(self, app, client):
        uid, email, _ = create_user(app)
        try:
            r = login(client, email, "WrongPass@99!")
            assert r.status_code == 401
            assert "Invalid credentials" in r.get_json()["error"]
        finally:
            delete_user(app, uid)

    def test_unknown_email(self, client):
        r = login(client, "nobody@nowhere.com", "AnyPass@1!")
        assert r.status_code == 401

    def test_missing_fields(self, client):
        r = client.post("/api/auth/login", json={}, content_type="application/json")
        assert r.status_code == 400

    def test_inactive_user(self, app, client):
        uid, email, pw = create_user(app, is_active=False)
        try:
            r = login(client, email, pw)
            assert r.status_code == 401
        finally:
            delete_user(app, uid)

    def test_lockout_after_three_failures(self, app, client):
        uid, email, _ = create_user(app)
        try:
            for _ in range(2):
                r = login(client, email, "BadPass@99!")
                assert r.status_code == 401
            # 3rd attempt triggers lockout
            r = login(client, email, "BadPass@99!")
            assert r.status_code == 423
            body = r.get_json()
            assert body["error"] == "account_locked"
            assert "locked_until" in body
        finally:
            delete_user(app, uid)

    def test_locked_account_rejected_immediately(self, app, client):
        uid, email, pw = create_user(app, is_locked=True)
        try:
            r = login(client, email, pw)
            assert r.status_code == 423
            assert r.get_json()["error"] == "account_locked"
        finally:
            delete_user(app, uid)

    def test_auto_unlock_after_lockout_expiry(self, app, client):
        from datetime import datetime, timezone, timedelta
        from extensions import db
        from models.user import User

        uid, email, pw = create_user(app)
        try:
            # Simulate a lockout that already expired 1 second ago
            u = db.session.get(User, uid)
            u.is_locked = True
            u.failed_login_attempts = 3
            u.locked_until = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.session.commit()

            r = login(client, email, pw)
            assert r.status_code == 200, f"Expected 200 after auto-unlock, got {r.status_code}"
            assert "access_token" in r.get_json()
        finally:
            delete_user(app, uid)

    def test_correct_password_resets_failed_attempts(self, app, client):
        from extensions import db
        from models.user import User

        uid, email, pw = create_user(app)
        try:
            login(client, email, "BadPass@99!")  # 1 failure
            login(client, email, pw)             # success — should reset counter
            u = db.session.get(User, uid)
            assert u.failed_login_attempts == 0
            assert not u.is_locked
        finally:
            delete_user(app, uid)


# ── MFA ────────────────────────────────────────────────────────────────────────

class TestMFA:
    def _setup_mfa_user(self, app, client):
        """Create user, enable MFA, return (uid, email, pw, secret)."""
        uid, email, pw = create_user(app)
        r = login(client, email, pw)
        tok = r.get_json()["access_token"]

        # Setup MFA — get secret
        r = client.post("/api/auth/mfa/setup", headers=auth_headers(tok))
        assert r.status_code == 200
        secret = r.get_json()["secret"]

        # Enable MFA with valid code
        code = pyotp.TOTP(secret).now()
        r = client.post("/api/auth/mfa/enable",
                        json={"code": code}, headers=auth_headers(tok),
                        content_type="application/json")
        assert r.status_code == 200
        return uid, email, pw, secret

    def test_mfa_secret_stored_encrypted_not_plaintext(self, app, client):
        """Regression test for audits/security_audit.md Finding S2 — mfa_secret
        was previously stored as plaintext in the DB."""
        uid, email, pw, secret = self._setup_mfa_user(app, client)
        try:
            with app.app_context():
                from models.user import User
                from extensions import db
                stored = db.session.get(User, uid).mfa_secret
                assert stored != secret
                assert secret not in stored
                # But get_mfa_secret() still returns the real plaintext for TOTP verification
                assert db.session.get(User, uid).get_mfa_secret() == secret
        finally:
            delete_user(app, uid)

    def test_mfa_login_gate(self, app, client):
        uid, email, pw, secret = self._setup_mfa_user(app, client)
        try:
            r = login(client, email, pw)
            assert r.status_code == 200
            body = r.get_json()
            assert body.get("status") == "mfa_required"
            assert "mfa_token" in body
        finally:
            delete_user(app, uid)

    def test_mfa_login_valid_code(self, app, client):
        uid, email, pw, secret = self._setup_mfa_user(app, client)
        try:
            r = login(client, email, pw)
            mfa_token = r.get_json()["mfa_token"]
            code = pyotp.TOTP(secret).now()
            r2 = client.post("/api/auth/mfa/login",
                             json={"mfa_token": mfa_token, "code": code},
                             content_type="application/json")
            assert r2.status_code == 200
            body = r2.get_json()
            assert "access_token" in body
            assert "refresh_token" in body
        finally:
            delete_user(app, uid)

    def test_mfa_login_invalid_code(self, app, client):
        uid, email, pw, secret = self._setup_mfa_user(app, client)
        try:
            r = login(client, email, pw)
            mfa_token = r.get_json()["mfa_token"]
            r2 = client.post("/api/auth/mfa/login",
                             json={"mfa_token": mfa_token, "code": "000000"},
                             content_type="application/json")
            assert r2.status_code == 401
        finally:
            delete_user(app, uid)

    def test_mfa_login_missing_fields(self, client):
        r = client.post("/api/auth/mfa/login", json={}, content_type="application/json")
        assert r.status_code == 400

    def test_mfa_disable(self, app, client):
        uid, email, pw, secret = self._setup_mfa_user(app, client)
        try:
            r = login(client, email, pw)
            mfa_token = r.get_json()["mfa_token"]
            code = pyotp.TOTP(secret).now()
            r_full = client.post("/api/auth/mfa/login",
                                 json={"mfa_token": mfa_token, "code": code},
                                 content_type="application/json")
            tok = r_full.get_json()["access_token"]

            r_dis = client.post("/api/auth/mfa/disable",
                                json={"password": pw}, headers=auth_headers(tok),
                                content_type="application/json")
            assert r_dis.status_code == 200

            # Now login should return tokens directly, no MFA gate
            r_login = login(client, email, pw)
            assert r_login.status_code == 200
            assert "access_token" in r_login.get_json()
        finally:
            delete_user(app, uid)


# ── Token refresh ──────────────────────────────────────────────────────────────

class TestRefresh:
    def test_refresh_returns_new_access_token(self, app, client):
        uid, email, pw = create_user(app)
        try:
            r = login(client, email, pw)
            refresh_token = r.get_json()["refresh_token"]
            r2 = client.post(
                "/api/auth/refresh",
                headers={"Authorization": f"Bearer {refresh_token}"},
            )
            assert r2.status_code == 200
            assert "access_token" in r2.get_json()
        finally:
            delete_user(app, uid)

    def test_refresh_rejected_without_token(self, client):
        r = client.post("/api/auth/refresh")
        assert r.status_code == 401

    def test_refresh_rejected_with_access_token(self, app, client):
        """Access token must not be accepted as a refresh token."""
        uid, email, pw = create_user(app)
        try:
            r = login(client, email, pw)
            access_token = r.get_json()["access_token"]
            r2 = client.post(
                "/api/auth/refresh",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            assert r2.status_code == 422  # JWT extended returns 422 for wrong token type
        finally:
            delete_user(app, uid)


# ── /me endpoint ───────────────────────────────────────────────────────────────

class TestMe:
    def test_me_requires_auth(self, client):
        r = client.get("/api/auth/me")
        assert r.status_code == 401

    def test_me_returns_current_user(self, app, client):
        uid, email, pw = create_user(app)
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.get("/api/auth/me", headers=auth_headers(tok))
            assert r.status_code == 200
            body = r.get_json()
            assert body["email"] == email
            assert "password_hash" not in body
        finally:
            delete_user(app, uid)


# ── Password management ────────────────────────────────────────────────────────

class TestPasswordChange:
    def test_change_password_success(self, app, client):
        uid, email, pw = create_user(app)
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.put(
                "/api/auth/me/password",
                json={"current_password": pw, "new_password": "NewPassword@99!"},
                headers=auth_headers(tok),
                content_type="application/json",
            )
            assert r.status_code == 200
            # Verify new password works
            r2 = login(client, email, "NewPassword@99!")
            assert r2.status_code == 200
        finally:
            delete_user(app, uid)

    def test_change_password_wrong_current(self, app, client):
        uid, email, pw = create_user(app)
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.put(
                "/api/auth/me/password",
                json={"current_password": "WrongOld@1!", "new_password": "NewPassword@99!"},
                headers=auth_headers(tok),
                content_type="application/json",
            )
            assert r.status_code == 400
        finally:
            delete_user(app, uid)

    def test_change_password_weak_new(self, app, client):
        uid, email, pw = create_user(app)
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.put(
                "/api/auth/me/password",
                json={"current_password": pw, "new_password": "weak"},
                headers=auth_headers(tok),
                content_type="application/json",
            )
            assert r.status_code == 400
        finally:
            delete_user(app, uid)

    def test_force_change_password(self, app, client):
        from extensions import db
        from models.user import User
        uid, email, pw = create_user(app)
        # Endpoint requires must_change_password=True
        with app.app_context():
            u = db.session.get(User, uid)
            u.must_change_password = True
            db.session.commit()
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.post(
                "/api/auth/me/force-change-password",
                json={"new_password": "ForceNew@99!"},
                headers=auth_headers(tok),
                content_type="application/json",
            )
            assert r.status_code == 200
        finally:
            delete_user(app, uid)

    def test_force_change_password_weak(self, app, client):
        from extensions import db
        from models.user import User
        uid, email, pw = create_user(app)
        with app.app_context():
            u = db.session.get(User, uid)
            u.must_change_password = True
            db.session.commit()
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.post(
                "/api/auth/me/force-change-password",
                json={"new_password": "short"},
                headers=auth_headers(tok),
                content_type="application/json",
            )
            assert r.status_code == 400
        finally:
            delete_user(app, uid)


# ── Logout ─────────────────────────────────────────────────────────────────────

class TestLogout:
    def test_logout_success(self, app, client):
        uid, email, pw = create_user(app)
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.post("/api/auth/logout", headers=auth_headers(tok))
            assert r.status_code == 200
        finally:
            delete_user(app, uid)

    def test_logout_requires_auth(self, client):
        r = client.post("/api/auth/logout")
        assert r.status_code == 401


# ── Password reset ─────────────────────────────────────────────────────────────

class TestPasswordReset:
    def test_reset_request_always_200(self, client):
        """Must return 200 even for unknown email (prevent enumeration)."""
        r = client.post(
            "/api/auth/password-reset/request",
            json={"email": "unknown@nowhere.com"},
            content_type="application/json",
        )
        assert r.status_code == 200

    def test_reset_confirm_invalid_token(self, client):
        r = client.post(
            "/api/auth/password-reset/confirm",
            json={"token": "not-a-real-token", "new_password": "NewPass@99!"},
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_reset_confirm_missing_fields(self, client):
        r = client.post(
            "/api/auth/password-reset/confirm",
            json={},
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_reset_token_is_single_use(self, app, client):
        """Regression test for audits/security_audit.md Finding A1 — a reset
        token previously remained valid for its full 1-hour window even after
        already being used once."""
        from flask_jwt_extended import create_access_token
        uid, email, pw = create_user(app)
        try:
            with app.app_context():
                reset_token = create_access_token(
                    identity=uid, additional_claims={"purpose": "password_reset"},
                )
            r1 = client.post(
                "/api/auth/password-reset/confirm",
                json={"token": reset_token, "new_password": "FirstNewPass@1!"},
                content_type="application/json",
            )
            assert r1.status_code == 200

            # Same token, second attempt — must now be rejected
            r2 = client.post(
                "/api/auth/password-reset/confirm",
                json={"token": reset_token, "new_password": "SecondNewPass@2!"},
                content_type="application/json",
            )
            assert r2.status_code == 400
        finally:
            delete_user(app, uid)


# ── Rate limiting (audits/testing_audit.md Finding M1) ─────────────────────────
# TestConfig.RATELIMIT_ENABLED = False globally, so Flask-Limiter is a no-op for
# every other test in this suite. This is NOT a simple runtime toggle: Flask-
# Limiter's init_app() reads RATELIMIT_ENABLED once and, if disabled, returns
# immediately WITHOUT constructing its storage backend or limiter strategy object
# at all (see flask_limiter/_extension.py:331-333) — so flipping app.config or
# even the extension's own `.enabled` attribute afterward has no effect, because
# the machinery that would enforce it was never built. Testing real enforcement
# needs a second Flask app created with the flag on from the start.
#
# A second, sneakier trap found while writing this test: extensions.py's
# Limiter(storage_uri="redis://...") sets storage_uri as a CONSTRUCTOR argument,
# which flask_limiter's init_app() prefers over TestConfig.RATELIMIT_STORAGE_URL
# ("memory://") — `self._storage_uri or storage_uri_from_config`, and the
# constructor value is always truthy. So enabling the real limiter, even in
# "testing" config, connects to whatever Redis is actually reachable at
# 127.0.0.1:6379 — on a dev machine with Redis running (as this one was, for
# unrelated live-service testing earlier this session), the fixed-window
# counter for 127.0.0.1 (the Flask test client's fixed remote_addr) persists
# in that real Redis across separate pytest invocations within the same
# 60-second window, making the test flaky/order-dependent. Forcing
# limiter._storage_uri to "memory://" for the duration of this test only
# (restored after) gives a real, isolated, repeatable in-process counter
# instead — TestConfig.RATELIMIT_STORAGE_URL was already trying to say this;
# it just couldn't win against the constructor kwarg on its own.

class TestLoginRateLimit:
    def test_sixth_attempt_in_a_minute_is_429(self):
        from config import TestConfig, config_map
        from app import create_app
        from extensions import db, limiter

        # extensions.limiter is ONE shared object — init_app() stores .enabled/
        # ._storage/._limiter/._storage_uri as plain instance attributes, not
        # per-app state (unlike db/jwt, which Flask-SQLAlchemy/Flask-JWT-Extended
        # correctly scope per-app). Re-running create_app() below WILL mutate
        # this shared object, so everything touched must be explicitly restored
        # afterward or every other test in the suite is affected.
        original_enabled = limiter.enabled
        original_storage_uri = limiter._storage_uri

        class _RateLimitedTestConfig(TestConfig):
            RATELIMIT_ENABLED = True

        config_map["_ratelimit_test"] = _RateLimitedTestConfig
        try:
            limiter._storage_uri = "memory://"  # isolated, in-process — see note above
            rl_app = create_app("_ratelimit_test")
            with rl_app.app_context():
                db.create_all()
                try:
                    rl_client = rl_app.test_client()
                    for _ in range(5):
                        r = rl_client.post(
                            "/api/auth/login",
                            json={"email": "nobody@ratelimit-test.local", "password": "wrong"},
                            content_type="application/json",
                        )
                        assert r.status_code == 401  # unknown user, not yet limited
                    r = rl_client.post(
                        "/api/auth/login",
                        json={"email": "nobody@ratelimit-test.local", "password": "wrong"},
                        content_type="application/json",
                    )
                    assert r.status_code == 429
                finally:
                    db.drop_all()
        finally:
            del config_map["_ratelimit_test"]
            limiter.enabled = original_enabled
            limiter._storage_uri = original_storage_uri

    def test_disabled_in_test_config_by_default(self, client):
        """Documents the invariant every other test in this file relies on."""
        for _ in range(10):
            r = client.post(
                "/api/auth/login",
                json={"email": "nobody@ratelimit-test.local", "password": "wrong"},
                content_type="application/json",
            )
            assert r.status_code == 401  # never 429 — rate limiting is off by default


# ── JWT error response shape (audits/testing_audit.md Finding M2) ──────────────

class TestJwtErrorShape:
    def test_missing_token_returns_error_key_not_msg(self, client):
        r = client.get("/api/admin/users")  # @jwt_required() route, no Authorization header
        assert r.status_code == 401
        body = r.get_json()
        assert "error" in body
        assert "msg" not in body

    def test_malformed_token_returns_error_key_not_msg(self, client):
        r = client.get("/api/admin/users", headers=auth_headers("not-a-real-jwt"))
        assert r.status_code == 422
        body = r.get_json()
        assert "error" in body
        assert "msg" not in body


# ── JWT tampering (audits/testing_audit.md Finding M3) ─────────────────────────

class TestJwtTampering:
    def test_tampered_signature_is_rejected(self, app, client):
        uid, email, pw = create_user(app)
        try:
            token = login(client, email, pw).get_json()["access_token"]
            tampered = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
            r = client.get("/api/auth/me", headers=auth_headers(tampered))
            assert r.status_code == 422
        finally:
            delete_user(app, uid)

    def test_truncated_token_is_rejected(self, app, client):
        uid, email, pw = create_user(app)
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.get("/api/auth/me", headers=auth_headers(token[: len(token) // 2]))
            assert r.status_code == 422
        finally:
            delete_user(app, uid)
