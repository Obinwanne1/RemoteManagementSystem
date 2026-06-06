import uuid
from datetime import datetime, timezone
from extensions import db


class UserSession(db.Model):
    """Tracks one active refresh token per user per device fingerprint.

    Device fingerprint = SHA256(User-Agent + Accept-Language).
    When a user logs in from the same device again, the old entry is replaced,
    invalidating the previous refresh token for that device only.
    Different devices each have their own independent entry.
    """
    __tablename__ = "user_sessions"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    device_fp = db.Column(db.String(64), nullable=False)   # first 32 hex chars of SHA256
    refresh_jti = db.Column(db.String(36), nullable=False)  # JTI of active refresh token
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint("user_id", "device_fp", name="uq_user_device"),
    )
