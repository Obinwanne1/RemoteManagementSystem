import uuid
from datetime import datetime, timezone
from extensions import db


class Ticket(db.Model):
    __tablename__ = "tickets"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text, nullable=True)
    customer_id = db.Column(db.String(36), db.ForeignKey("customers.id"), nullable=False, index=True)
    device_id = db.Column(db.String(36), db.ForeignKey("devices.id"), nullable=True)
    assignee_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)
    priority = db.Column(db.String(20), default="medium")  # low/medium/high/critical
    status = db.Column(db.String(30), default="open")  # open/in_progress/resolved/closed
    source = db.Column(db.String(30), default="manual")  # manual/alert
    alert_id = db.Column(db.String(36), db.ForeignKey("alerts.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))
    resolved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    tags = db.Column(db.JSON, default=list)

    comments = db.relationship("TicketComment", backref="ticket", lazy="dynamic",
                               cascade="all, delete-orphan")

    def to_dict(self, include_comments=False):
        d = {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "customer_id": self.customer_id,
            "device_id": self.device_id,
            "assignee_id": self.assignee_id,
            "priority": self.priority,
            "status": self.status,
            "source": self.source,
            "alert_id": self.alert_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "tags": self.tags,
        }
        if include_comments:
            d["comments"] = [c.to_dict() for c in self.comments.order_by(TicketComment.created_at)]
        return d


class TicketComment(db.Model):
    __tablename__ = "ticket_comments"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ticket_id = db.Column(db.String(36), db.ForeignKey("tickets.id"), nullable=False, index=True)
    author_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    is_internal = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "ticket_id": self.ticket_id,
            "author_id": self.author_id,
            "body": self.body,
            "is_internal": self.is_internal,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
