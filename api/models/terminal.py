import uuid
from datetime import datetime, timezone
from extensions import db


class TerminalSession(db.Model):
    __tablename__ = "terminal_sessions"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id = db.Column(db.String(36), db.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status = db.Column(db.String(20), default="active")  # active | closed
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    closed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    last_activity_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    commands = db.relationship("TerminalCommand", backref="session", cascade="all, delete-orphan", lazy="dynamic")
    outputs = db.relationship("TerminalOutput", backref="session", cascade="all, delete-orphan", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "device_id": self.device_id,
            "user_id": self.user_id,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "last_activity_at": self.last_activity_at.isoformat() if self.last_activity_at else None,
        }


class TerminalCommand(db.Model):
    __tablename__ = "terminal_commands"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = db.Column(db.String(36), db.ForeignKey("terminal_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    command = db.Column(db.String(2000), nullable=False)
    status = db.Column(db.String(20), default="pending")  # pending | running | done | error
    sent_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    picked_up_at = db.Column(db.DateTime(timezone=True), nullable=True)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "command": self.command,
            "status": self.status,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "picked_up_at": self.picked_up_at.isoformat() if self.picked_up_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class TerminalOutput(db.Model):
    __tablename__ = "terminal_outputs"

    id = db.Column(
        db.BigInteger().with_variant(db.Integer(), "sqlite"),
        primary_key=True, autoincrement=True,
    )
    session_id = db.Column(db.String(36), db.ForeignKey("terminal_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    command_id = db.Column(db.String(36), db.ForeignKey("terminal_commands.id", ondelete="SET NULL"), nullable=True)
    content = db.Column(db.Text, nullable=False)
    stream = db.Column(db.String(10), default="stdout")  # stdout | stderr | system
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "command_id": self.command_id,
            "content": self.content,
            "stream": self.stream,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
