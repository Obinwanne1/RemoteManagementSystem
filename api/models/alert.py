import uuid
from datetime import datetime, timezone
from extensions import db


class AlertRule(db.Model):
    __tablename__ = "alert_rules"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255), nullable=False)
    customer_id = db.Column(db.String(36), db.ForeignKey("customers.id"), nullable=True)
    device_group_id = db.Column(db.String(36), db.ForeignKey("device_groups.id"), nullable=True)
    metric = db.Column(db.String(50), nullable=False)  # cpu/ram/disk/offline/event
    operator = db.Column(db.String(10), nullable=False)  # gt/lt/eq/gte/lte
    threshold = db.Column(db.Float, nullable=True)
    severity = db.Column(db.String(20), default="warning")  # info/warning/critical
    cooldown_minutes = db.Column(db.Integer, default=15)
    notification_channels = db.Column(db.JSON, default=dict)  # {"email": ["a@b.com"]}
    auto_create_ticket = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    alerts = db.relationship("Alert", backref="rule", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "customer_id": self.customer_id,
            "device_group_id": self.device_group_id,
            "metric": self.metric,
            "operator": self.operator,
            "threshold": self.threshold,
            "severity": self.severity,
            "cooldown_minutes": self.cooldown_minutes,
            "notification_channels": self.notification_channels,
            "auto_create_ticket": self.auto_create_ticket,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Alert(db.Model):
    __tablename__ = "alerts"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    rule_id = db.Column(db.String(36), db.ForeignKey("alert_rules.id"), nullable=True)
    device_id = db.Column(db.String(36), db.ForeignKey("devices.id"), nullable=False, index=True)
    triggered_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    resolved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    severity = db.Column(db.String(20), default="warning")
    message = db.Column(db.Text, nullable=False)
    acknowledged_by = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)
    acknowledged_at = db.Column(db.DateTime(timezone=True), nullable=True)
    status = db.Column(db.String(20), default="open")  # open/acknowledged/resolved

    def to_dict(self):
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "device_id": self.device_id,
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "severity": self.severity,
            "message": self.message,
            "acknowledged_by": self.acknowledged_by,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "status": self.status,
        }
