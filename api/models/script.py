import uuid
from datetime import datetime, timezone
from extensions import db


class Script(db.Model):
    __tablename__ = "scripts"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    file_type = db.Column(db.String(10), nullable=False)  # bat/ps1/py
    content = db.Column(db.Text, nullable=False)
    uploaded_by = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)
    is_builtin = db.Column(db.Boolean, default=False)
    os_target = db.Column(db.String(20), default="windows")
    tags = db.Column(db.JSON, default=list)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    runs = db.relationship("ScriptRun", backref="script", lazy="dynamic")

    def to_dict(self, include_content=True):
        d = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "file_type": self.file_type,
            "uploaded_by": self.uploaded_by,
            "is_builtin": self.is_builtin,
            "os_target": self.os_target,
            "tags": self.tags,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_content:
            d["content"] = self.content
        return d


class ScriptRun(db.Model):
    __tablename__ = "script_runs"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    script_id = db.Column(db.String(36), db.ForeignKey("scripts.id"), nullable=False, index=True)
    device_id = db.Column(db.String(36), db.ForeignKey("devices.id"), nullable=False, index=True)
    triggered_by = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)
    triggered_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    started_at = db.Column(db.DateTime(timezone=True), nullable=True)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    exit_code = db.Column(db.Integer, nullable=True)
    stdout = db.Column(db.Text, nullable=True)
    stderr = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default="queued")  # queued/running/success/failed/timeout
    timeout_seconds = db.Column(db.Integer, default=300)

    def to_dict(self):
        return {
            "id": self.id,
            "script_id": self.script_id,
            "device_id": self.device_id,
            "triggered_by": self.triggered_by,
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "status": self.status,
            "timeout_seconds": self.timeout_seconds,
        }
