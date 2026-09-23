"""API and token usage monitoring — superadmin-only. See utils/usage_tracker.py."""
from datetime import datetime, timezone
from extensions import db


class ApiUsageEvent(db.Model):
    """One row per instrumented call: AI Assistant + outbound third-party integrations."""
    __tablename__ = "api_usage_events"

    id = db.Column(
        db.BigInteger().with_variant(db.Integer(), "sqlite"),
        primary_key=True, autoincrement=True,
    )
    service = db.Column(db.String(50), nullable=False, index=True)
    feature = db.Column(db.String(100), nullable=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)
    input_tokens = db.Column(db.Integer, nullable=True)
    output_tokens = db.Column(db.Integer, nullable=True)
    estimated_cost_usd = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="success")
    status_code = db.Column(db.Integer, nullable=True)
    latency_ms = db.Column(db.Integer, nullable=True)
    error_message = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    __table_args__ = (
        db.Index("ix_usage_event_service_created", "service", "created_at"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "service": self.service,
            "feature": self.feature,
            "user_id": self.user_id,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "status": self.status,
            "status_code": self.status_code,
            "latency_ms": self.latency_ms,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ApiUsageHourly(db.Model):
    """Durable hourly rollup of internal Flask API request volume (Redis-fed, too
    high-volume to log one ApiUsageEvent row per request)."""
    __tablename__ = "api_usage_hourly"

    id = db.Column(
        db.BigInteger().with_variant(db.Integer(), "sqlite"),
        primary_key=True, autoincrement=True,
    )
    bucket_start = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    endpoint = db.Column(db.String(150), nullable=False)
    method = db.Column(db.String(10), nullable=False)
    request_count = db.Column(db.Integer, nullable=False, default=0)
    error_count = db.Column(db.Integer, nullable=False, default=0)
    total_latency_ms = db.Column(db.BigInteger, nullable=False, default=0)

    __table_args__ = (
        db.UniqueConstraint("bucket_start", "endpoint", "method", name="uq_usage_hourly_bucket"),
    )

    def to_dict(self):
        avg_latency = (self.total_latency_ms / self.request_count) if self.request_count else None
        return {
            "id": self.id,
            "bucket_start": self.bucket_start.isoformat() if self.bucket_start else None,
            "endpoint": self.endpoint,
            "method": self.method,
            "request_count": self.request_count,
            "error_count": self.error_count,
            "avg_latency_ms": round(avg_latency, 1) if avg_latency is not None else None,
        }


class UsageAlertConfig(db.Model):
    """Singleton settings row controlling usage-spike notifications. Deliberately
    NOT an AlertRule — those are visible to admin/technician via the Alerts page,
    which would leak this superadmin-only feature's existence/config."""
    __tablename__ = "usage_alert_config"

    id = db.Column(db.String(20), primary_key=True, default="default")
    is_enabled = db.Column(db.Boolean, nullable=False, default=False)
    spike_multiplier = db.Column(db.Float, nullable=False, default=3.0)
    notification_channels = db.Column(db.JSON, nullable=False, default=dict)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                            onupdate=lambda: datetime.now(timezone.utc))
    updated_by = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)

    def to_dict(self):
        return {
            "is_enabled": self.is_enabled,
            "spike_multiplier": self.spike_multiplier,
            "notification_channels": self.notification_channels or {},
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "updated_by": self.updated_by,
        }

    @classmethod
    def get_or_create(cls):
        cfg = db.session.get(cls, "default")
        if not cfg:
            cfg = cls(id="default")
            db.session.add(cfg)
            db.session.commit()
        return cfg
