import uuid
from datetime import datetime, timezone
from extensions import db


class Customer(db.Model):
    __tablename__ = "customers"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    address = db.Column(db.Text, nullable=True)
    primary_tech_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)
    tier = db.Column(db.String(50), default="standard")  # standard/premium/enterprise
    notes = db.Column(db.Text, nullable=True)
    registration_token_hash = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    devices = db.relationship("Device", backref="customer", lazy="dynamic")
    device_groups = db.relationship("DeviceGroup", backref="customer", lazy="dynamic")

    def to_dict(self, include_counts=False):
        d = {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "email": self.email,
            "phone": self.phone,
            "address": self.address,
            "primary_tech_id": self.primary_tech_id,
            "tier": self.tier,
            "notes": self.notes,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_counts:
            d["device_count"] = self.devices.count()
            d["online_count"] = self.devices.filter_by(is_online=True).count()
        return d


class DeviceGroup(db.Model):
    __tablename__ = "device_groups"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_id = db.Column(db.String(36), db.ForeignKey("customers.id"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    devices = db.relationship("Device", backref="group", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "name": self.name,
            "description": self.description,
            "device_count": self.devices.count(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
