import uuid
from datetime import datetime, timezone
from extensions import db


class PatchPolicy(db.Model):
    __tablename__ = "patch_policies"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255), nullable=False)
    customer_id = db.Column(db.String(36), db.ForeignKey("customers.id"), nullable=True)
    device_group_id = db.Column(db.String(36), db.ForeignKey("device_groups.id"), nullable=True)
    auto_approve_critical = db.Column(db.Boolean, default=True)
    auto_approve_security = db.Column(db.Boolean, default=True)
    auto_approve_service_packs = db.Column(db.Boolean, default=False)
    auto_approve_drivers = db.Column(db.Boolean, default=False)
    reboot_behavior = db.Column(db.String(20), default="prompt")  # auto/prompt/never
    maintenance_window = db.Column(db.JSON, nullable=True)  # {"day": "sunday", "time": "02:00"}
    winget_enabled = db.Column(db.Boolean, default=True)
    choco_enabled = db.Column(db.Boolean, default=False)
    excluded_software = db.Column(db.JSON, default=list)  # ["Zoom", "Teams"]
    software_bundles = db.Column(db.JSON, default=list)   # [{"name": "Browsers Bundle", "packages": [...]}]
    upgrade_os = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "customer_id": self.customer_id,
            "device_group_id": self.device_group_id,
            "auto_approve_critical": self.auto_approve_critical,
            "auto_approve_security": self.auto_approve_security,
            "auto_approve_service_packs": self.auto_approve_service_packs,
            "auto_approve_drivers": self.auto_approve_drivers,
            "reboot_behavior": self.reboot_behavior,
            "maintenance_window": self.maintenance_window,
            "winget_enabled": self.winget_enabled,
            "choco_enabled": self.choco_enabled,
            "excluded_software": self.excluded_software,
            "software_bundles": self.software_bundles,
            "upgrade_os": self.upgrade_os,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class PatchRecord(db.Model):
    __tablename__ = "patch_records"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id = db.Column(db.String(36), db.ForeignKey("devices.id"), nullable=False, index=True)
    patch_name = db.Column(db.String(500), nullable=False)
    kb_id = db.Column(db.String(50), nullable=True)
    patch_type = db.Column(db.String(50), nullable=True)  # critical/security/service_pack/driver/feature
    source = db.Column(db.String(20), default="wu")  # wu/winget/choco
    version_from = db.Column(db.String(255), nullable=True)
    version_to = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(30), default="pending")  # pending/approved/deployed/failed/excluded
    deployed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    deployed_by = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "device_id": self.device_id,
            "patch_name": self.patch_name,
            "kb_id": self.kb_id,
            "patch_type": self.patch_type,
            "source": self.source,
            "version_from": self.version_from,
            "version_to": self.version_to,
            "status": self.status,
            "deployed_at": self.deployed_at.isoformat() if self.deployed_at else None,
            "deployed_by": self.deployed_by,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
