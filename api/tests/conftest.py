import os
import sys
import uuid
import pytest

# Ensure api/ is on sys.path so 'from app import create_app' etc. resolve.
_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _api_dir not in sys.path:
    sys.path.insert(0, _api_dir)

# Must be set before any app import — config.py reads these at class-body time.
# setdefault preserves existing values if a real .env is loaded first by load_dotenv.
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-chars-longx")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-at-least-32-charsx")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SUPERADMIN_PASSWORD", "TestSuperAdmin@1")
# Force-set values that CI env vars would otherwise override via setdefault
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["ORG_REGISTRATION_TOKEN"] = "test-org-token-unique-secret-value"


@pytest.fixture(scope="session")
def app():
    """Create one Flask app + SQLite in-memory DB for the entire test session."""
    from app import create_app
    flask_app = create_app("testing")

    from extensions import db
    with flask_app.app_context():
        db.create_all()
        yield flask_app
        db.drop_all()


@pytest.fixture
def client(app):
    """Fresh test client per test (no cookie/state bleed between tests)."""
    return app.test_client()


@pytest.fixture(scope="session")
def customer(app):
    """One shared Customer row for all agent tests."""
    from extensions import db
    from models.customer import Customer
    cust = Customer(
        name="Test Corp",
        slug=f"test-corp-{uuid.uuid4().hex[:6]}",
        is_active=True,
    )
    db.session.add(cust)
    db.session.commit()
    yield cust


# ── Helpers ───────────────────────────────────────────────────────────────────

def create_user(app, *, email=None, password="TestPassword@1!", role="technician",
                is_active=True, is_locked=False):
    """Insert a User into the DB and return its id + plaintext password."""
    from extensions import db
    from models.user import User
    if email is None:
        email = f"u_{uuid.uuid4().hex[:8]}@test.local"
    u = User(email=email, full_name="Test User", role=role, is_active=is_active,
             is_locked=is_locked)
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    return u.id, email, password


def delete_user(app, user_id):
    """Remove a test user and all related rows."""
    from extensions import db
    from models.user import User
    from models.audit import AuditLog
    from models.user_session import UserSession
    AuditLog.query.filter_by(user_id=user_id).delete()
    UserSession.query.filter_by(user_id=user_id).delete()
    User.query.filter_by(id=user_id).delete()
    db.session.commit()


def login(client, email, password):
    """POST /api/auth/login and return the response."""
    return client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
        content_type="application/json",
    )


def auth_headers(access_token):
    return {"Authorization": f"Bearer {access_token}"}
