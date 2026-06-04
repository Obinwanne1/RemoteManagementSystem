"""
Ensure the built-in superadmin account exists.
Called at every app startup. The superadmin cannot be deleted or demoted
through the API — it is the emergency backdoor for locked-out scenarios.

Credentials (defaults, override via .env):
  SUPERADMIN_EMAIL    default: superadmin@rmm.local
  SUPERADMIN_PASSWORD default: SuperAdmin@RMM1 (CHANGE THIS after first login)
"""
import os


SUPERADMIN_EMAIL = os.getenv("SUPERADMIN_EMAIL", "superadmin@rmm.local")
SUPERADMIN_PASSWORD = os.getenv("SUPERADMIN_PASSWORD", "SuperAdmin@RMM1")
SUPERADMIN_NAME = "Super Administrator"


def ensure_superadmin():
    """Create or restore the superadmin account if missing."""
    from extensions import db
    from models.user import User

    existing = User.query.filter_by(email=SUPERADMIN_EMAIL).first()
    if existing:
        # Ensure role hasn't been downgraded somehow
        if existing.role != "superadmin":
            existing.role = "superadmin"
            db.session.commit()
        return

    superadmin = User(
        email=SUPERADMIN_EMAIL,
        full_name=SUPERADMIN_NAME,
        role="superadmin",
        is_active=True,
        must_change_password=False,
    )
    superadmin.set_password(SUPERADMIN_PASSWORD)
    db.session.add(superadmin)
    db.session.commit()
