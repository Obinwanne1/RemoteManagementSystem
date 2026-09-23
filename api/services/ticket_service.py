"""Ticket creation logic shared by the human-facing route and the AI assistant tool executor.

Extracted from routes/tickets.py::create_ticket so both callers run the exact same
authorization/SLA/audit/notification logic — no duplicated permission checks.
"""
from datetime import datetime, timezone, timedelta

from flask import request, current_app
from extensions import db
from models.ticket import Ticket
from models.user import User
from models.customer import Customer
from models.audit import AuditLog


def _sla_resolution_hours(priority: str, customer_id: str) -> int:
    import time
    from models.sla_policy import SLAPolicy

    _SLA_HOURS = {"critical": 4, "high": 8, "medium": 24, "low": 72}
    if not hasattr(_sla_resolution_hours, "_cache"):
        _sla_resolution_hours._cache = {}
    cache = _sla_resolution_hours._cache
    ttl = 120

    key = (customer_id, priority)
    entry = cache.get(key)
    if entry and entry[1] > time.monotonic():
        return entry[0]

    hours = None
    if customer_id:
        policy = SLAPolicy.query.filter_by(customer_id=customer_id, priority=priority).first()
        if policy:
            hours = policy.resolution_hours
    if hours is None:
        global_policy = SLAPolicy.query.filter_by(customer_id=None, priority=priority).first()
        if global_policy:
            hours = global_policy.resolution_hours
    if hours is None:
        hours = _SLA_HOURS.get(priority, 24)

    cache[key] = (hours, time.monotonic() + ttl)
    return hours


def _customer_name(customer_id: str) -> str:
    c = db.session.get(Customer, customer_id)
    return c.name if c else "Unknown"


def create_ticket_service(
    actor_user_id: str,
    actor_role: str,
    actor_customer_id: str,
    *,
    title: str,
    description: str = None,
    customer_id: str = None,
    device_id: str = None,
    assignee_id: str = None,
    priority: str = "medium",
    status: str = "open",
    alert_id: str = None,
    department_id: str = None,
    tags: list = None,
    due_date=None,
    source: str = "manual",
):
    """Returns (ticket_dict, error) where error is None or (message, status_code)."""
    if actor_role not in ("admin", "technician", "client", "superadmin"):
        return None, ("Insufficient permissions", 403)

    if actor_role == "client":
        if not actor_customer_id:
            return None, ("Client account not linked to a customer", 400)
        resolved_customer_id = actor_customer_id
        source = "client"
        dept_id = current_app.config.get("HELPDESK_DEPT_ID")
    else:
        resolved_customer_id = customer_id
        if not resolved_customer_id:
            return None, ("customer_id required", 400)
        dept_id = department_id

    title = (title or "").strip()
    if not title:
        return None, ("title required", 400)

    due_date = due_date or (
        datetime.now(timezone.utc) + timedelta(hours=_sla_resolution_hours(priority, resolved_customer_id))
    )
    ticket = Ticket(
        title=title,
        description=description,
        customer_id=resolved_customer_id,
        device_id=device_id,
        assignee_id=assignee_id,
        priority=priority,
        status=status,
        source=source,
        alert_id=alert_id,
        department_id=dept_id,
        due_date=due_date,
        tags=tags or [],
    )
    db.session.add(ticket)
    db.session.flush()  # populate ticket.id (client-side UUID default) before referencing it below
    db.session.add(AuditLog(
        user_id=actor_user_id,
        action="CREATE",
        resource_type="ticket",
        resource_id=ticket.id,
        ip_address=request.remote_addr if request else None,
        user_agent=(request.headers.get("User-Agent", "")[:500] if request else None),
        payload={"title": ticket.title, "priority": ticket.priority, "source": source},
    ))
    db.session.commit()

    try:
        from utils.notifications import send_ticket_created_client, send_ticket_assigned
        if source == "client":
            creator = db.session.get(User, actor_user_id)
            if creator and creator.email:
                send_ticket_created_client(ticket.title, ticket.id, ticket.priority, [creator.email])
        if ticket.assignee_id:
            assignee = db.session.get(User, ticket.assignee_id)
            if assignee and assignee.email:
                send_ticket_assigned(ticket.title, ticket.id, _customer_name(ticket.customer_id),
                                     ticket.priority, assignee.email)
    except Exception:
        current_app.logger.warning("Ticket create notification failed for ticket %s", ticket.id)

    try:
        from utils.events import publish_event
        publish_event("new_ticket", {
            "ticket_id": ticket.id,
            "title": ticket.title,
            "priority": ticket.priority,
            "source": source,
            "customer": _customer_name(ticket.customer_id),
        })
    except Exception:
        pass

    return ticket.to_dict(), None
