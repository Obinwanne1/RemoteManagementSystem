import uuid
from datetime import datetime, timezone
from extensions import db


class AiConversation(db.Model):
    __tablename__ = "ai_conversations"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    page = db.Column(db.String(60), nullable=False, default="Overview")
    is_archived = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                            onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.Index("ix_ai_conv_user_active", "user_id", "is_archived", "updated_at"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "page": self.page,
            "is_archived": self.is_archived,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class AiMessage(db.Model):
    __tablename__ = "ai_messages"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = db.Column(db.String(36), db.ForeignKey("ai_conversations.id", ondelete="CASCADE"),
                                 nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False)  # user | assistant | tool
    content = db.Column(db.Text, nullable=False)
    tool_calls = db.Column(db.JSON, nullable=True)
    contains_warning = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    __table_args__ = (
        db.Index("ix_ai_msg_conv_created", "conversation_id", "created_at"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "role": self.role,
            "content": self.content,
            "tool_calls": self.tool_calls,
            "contains_warning": self.contains_warning,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AiPendingAction(db.Model):
    __tablename__ = "ai_pending_actions"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = db.Column(db.String(36), db.ForeignKey("ai_conversations.id", ondelete="CASCADE"),
                                 nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    tool_name = db.Column(db.String(60), nullable=False)
    tool_input = db.Column(db.JSON, nullable=False)
    tool_use_id = db.Column(db.String(120), nullable=True)
    summary = db.Column(db.String(500), nullable=True)
    contains_warning = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default="pending", index=True)  # pending/confirmed/denied/expired/failed
    result = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    resolved_at = db.Column(db.DateTime(timezone=True), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "tool_name": self.tool_name,
            "tool_input": self.tool_input,
            "summary": self.summary,
            "contains_warning": self.contains_warning,
            "status": self.status,
            "result": self.result,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }
