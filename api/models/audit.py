import uuid
from datetime import datetime, timezone
from extensions import db


class AgentToken(db.Model):
    __tablename__ = "agent_tokens"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id = db.Column(db.String(36), db.ForeignKey("devices.id"), nullable=False, index=True)
    token_hash = db.Column(db.String(255), nullable=False, unique=True)
    issued_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime(timezone=True), nullable=True)
    is_revoked = db.Column(db.Boolean, default=False)
    last_used_at = db.Column(db.DateTime(timezone=True), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "device_id": self.device_id,
            "issued_at": self.issued_at.isoformat() if self.issued_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_revoked": self.is_revoked,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
        }


class AuditLog(db.Model):
    __tablename__ = "audit_log"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    resource_type = db.Column(db.String(50), nullable=True)
    resource_id = db.Column(db.String(36), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)
    payload = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "ip_address": self.ip_address,
            "payload": self.payload,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class NetworkScan(db.Model):
    __tablename__ = "network_scans"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_id = db.Column(db.String(36), db.ForeignKey("customers.id"), nullable=False)
    initiated_by = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)
    scan_range = db.Column(db.String(50), nullable=False)
    started_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    status = db.Column(db.String(20), default="running")  # running/completed/failed
    discovered_hosts = db.Column(db.JSON, default=list)
    new_devices_count = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "initiated_by": self.initiated_by,
            "scan_range": self.scan_range,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status,
            "host_count": len(self.discovered_hosts) if self.discovered_hosts else 0,
            "new_devices_count": self.new_devices_count,
        }
