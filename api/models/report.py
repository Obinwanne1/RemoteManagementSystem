import uuid
from datetime import datetime, timezone
from extensions import db


class Report(db.Model):
    __tablename__ = "reports"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255), nullable=False)
    template_type = db.Column(db.String(50), nullable=False)
    # patch_summary/device_health/ticket_summary/billing/software_inventory
    customer_id = db.Column(db.String(36), db.ForeignKey("customers.id"), nullable=True)
    date_range_start = db.Column(db.DateTime(timezone=True), nullable=True)
    date_range_end = db.Column(db.DateTime(timezone=True), nullable=True)
    generated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    generated_by = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)
    file_path = db.Column(db.String(500), nullable=True)
    format = db.Column(db.String(10), default="pdf")  # pdf/xlsx/csv
    parameters = db.Column(db.JSON, default=dict)
    is_scheduled = db.Column(db.Boolean, default=False)
    schedule_config = db.Column(db.JSON, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "template_type": self.template_type,
            "customer_id": self.customer_id,
            "date_range_start": self.date_range_start.isoformat() if self.date_range_start else None,
            "date_range_end": self.date_range_end.isoformat() if self.date_range_end else None,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "generated_by": self.generated_by,
            "format": self.format,
            "parameters": self.parameters,
            "is_scheduled": self.is_scheduled,
            "has_file": bool(self.file_path),
            "file_path": self.file_path,
        }
