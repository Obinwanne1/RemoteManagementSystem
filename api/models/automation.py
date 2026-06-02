import uuid
from datetime import datetime, timezone
from extensions import db


class AutomationProfile(db.Model):
    __tablename__ = "automation_profiles"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255), nullable=False)
    customer_id = db.Column(db.String(36), db.ForeignKey("customers.id"), nullable=True)
    device_group_id = db.Column(db.String(36), db.ForeignKey("device_groups.id"), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    schedule_type = db.Column(db.String(20), default="weekly")  # once/daily/weekly/monthly
    schedule_config = db.Column(db.JSON, default=dict)
    # e.g. {"day": "monday", "time": "01:00", "timezone": "UTC"}
    run_on_new_agents = db.Column(db.Boolean, default=False)
    notification_emails = db.Column(db.JSON, default=list)

    # Task configuration — mirrors reference screenshot columns
    os_patch_config = db.Column(db.JSON, default=dict)
    # {"enabled": true, "critical": true, "security": true, "service_packs": true, "drivers": true}
    software_patch_config = db.Column(db.JSON, default=dict)
    # {"update_all": false, "excluded": ["Zoom"], "bundles": ["Browsers Bundle"], "upgrade_os": false}
    disk_config = db.Column(db.JSON, default=dict)
    # {"defrag": false, "checkdisk": false}
    maintenance_config = db.Column(db.JSON, default=dict)
    # {"restore_point": false, "delete_temp": false, "clear_history": false, "reboot": false, "shutdown": false}
    scripts = db.Column(db.JSON, default=list)  # [script_id, ...]

    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))
    last_run_at = db.Column(db.DateTime(timezone=True), nullable=True)
    next_run_at = db.Column(db.DateTime(timezone=True), nullable=True)

    runs = db.relationship("ScheduledTaskRun", backref="profile", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "customer_id": self.customer_id,
            "device_group_id": self.device_group_id,
            "is_active": self.is_active,
            "schedule_type": self.schedule_type,
            "schedule_config": self.schedule_config,
            "run_on_new_agents": self.run_on_new_agents,
            "notification_emails": self.notification_emails,
            "os_patch_config": self.os_patch_config,
            "software_patch_config": self.software_patch_config,
            "disk_config": self.disk_config,
            "maintenance_config": self.maintenance_config,
            "scripts": self.scripts,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
        }


class ScheduledTaskRun(db.Model):
    __tablename__ = "scheduled_task_runs"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_id = db.Column(db.String(36), db.ForeignKey("automation_profiles.id"), nullable=False, index=True)
    device_id = db.Column(db.String(36), db.ForeignKey("devices.id"), nullable=False)
    started_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    status = db.Column(db.String(20), default="queued")  # queued/running/success/failed/partial
    result_summary = db.Column(db.JSON, nullable=True)
    celery_task_id = db.Column(db.String(255), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "profile_id": self.profile_id,
            "device_id": self.device_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status,
            "result_summary": self.result_summary,
            "celery_task_id": self.celery_task_id,
        }
