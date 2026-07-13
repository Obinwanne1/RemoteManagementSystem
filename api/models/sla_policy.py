import uuid
from datetime import datetime, timezone
from extensions import db


class SLAPolicy(db.Model):
    __tablename__ = "sla_policies"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_id = db.Column(db.String(36), db.ForeignKey("customers.id"), nullable=True, index=True)
    priority = db.Column(db.String(20), nullable=False)        # critical/high/medium/low
    response_hours = db.Column(db.Integer, nullable=False)     # hours to first response
    resolution_hours = db.Column(db.Integer, nullable=False)   # hours to resolution (used for due_date)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint("customer_id", "priority", name="uq_sla_customer_priority"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "priority": self.priority,
            "response_hours": self.response_hours,
            "resolution_hours": self.resolution_hours,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
