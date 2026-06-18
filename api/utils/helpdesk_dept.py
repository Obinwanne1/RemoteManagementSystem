"""
Ensure the built-in Help Desk department exists at startup.
Stores the department ID in app.config["HELPDESK_DEPT_ID"] for use
in ticket routing (client-submitted tickets auto-assigned to this dept).
"""
from datetime import datetime, timezone

HELPDESK_NAME = "Help Desk"
HELPDESK_COLOR = "#407E3C"


def ensure_helpdesk_department():
    from extensions import db
    from models.department import Department
    from flask import current_app

    dept = Department.query.filter_by(name=HELPDESK_NAME).first()
    if not dept:
        dept = Department(
            name=HELPDESK_NAME,
            description="Handles all incoming client tickets and internal help requests.",
            color=HELPDESK_COLOR,
            created_at=datetime.now(timezone.utc),
        )
        db.session.add(dept)
        db.session.commit()

    current_app.config["HELPDESK_DEPT_ID"] = dept.id
