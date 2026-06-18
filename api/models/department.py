import uuid
from datetime import datetime, timezone
from extensions import db


class Department(db.Model):
    __tablename__ = "departments"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    color = db.Column(db.String(7), nullable=False, default="#407E3C")
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    members = db.relationship("User", backref="department", lazy="dynamic",
                              foreign_keys="User.department_id")

    def to_dict(self, include_members=False):
        d = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "color": self.color,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "member_count": self.members.count(),
        }
        if include_members:
            d["members"] = [u.to_dict() for u in self.members.filter_by(is_active=True)]
        return d
