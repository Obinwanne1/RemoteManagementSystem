"""Read-only fleet-summary queries for the AI assistant's read tools.

Reuses the exact same cache keys as routes/dashboard.py so a tool call and a human
page load share the same warm cache instead of doubling query load.
"""
from sqlalchemy import func, case, and_
from extensions import db
from models.device import Device
from models.alert import Alert
from models.ticket import Ticket
from models.customer import Customer
from utils.cache import cache_get, cache_set


def get_fleet_summary(actor_role: str, actor_customer_id: str) -> dict:
    cid = actor_customer_id if actor_role == "client" else None
    cache_key = f"rmm:dash:summary:{cid or 'all'}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    dev_q = db.select(
        func.count().label("total"),
        func.sum(case((Device.is_online == True, 1), else_=0)).label("online"),  # noqa: E712
        func.sum(case((Device.status == "critical", 1), else_=0)).label("critical"),
        func.sum(case((Device.status == "warning", 1), else_=0)).label("warning"),
    ).select_from(Device)
    if cid:
        dev_q = dev_q.where(Device.customer_id == cid)
    dev = db.session.execute(dev_q).one()

    alr_q = db.select(
        func.sum(case((Alert.status == "open", 1), else_=0)).label("open"),
        func.sum(case((and_(Alert.status == "open", Alert.severity == "critical"), 1), else_=0)).label("critical"),
    ).select_from(Alert)
    if cid:
        alr_q = alr_q.join(Device, Alert.device_id == Device.id).where(Device.customer_id == cid)
    alr = db.session.execute(alr_q).one()

    _active = Ticket.status.in_(["open", "in_progress"])
    tkt_q = db.select(
        func.sum(case((_active, 1), else_=0)).label("open"),
        func.sum(case((and_(_active, Ticket.priority == "critical"), 1), else_=0)).label("critical"),
        func.sum(case((and_(_active, Ticket.assignee_id == None), 1), else_=0)).label("unassigned"),  # noqa: E711
        func.sum(case((and_(_active, Ticket.sla_breached == True), 1), else_=0)).label("sla_breached"),  # noqa: E712
    ).select_from(Ticket)
    if cid:
        tkt_q = tkt_q.where(Ticket.customer_id == cid)
    tkt = db.session.execute(tkt_q).one()

    total_customers = 1 if cid else db.session.execute(
        db.select(func.count()).select_from(Customer).where(Customer.is_active == True)  # noqa: E712
    ).scalar()

    total = dev.total or 0
    online = dev.online or 0
    result = {
        "devices": {"total": total, "online": online, "offline": total - online,
                    "critical": dev.critical or 0, "warning": dev.warning or 0},
        "alerts": {"open": alr.open or 0, "critical": alr.critical or 0},
        "tickets": {"open": tkt.open or 0, "critical": tkt.critical or 0,
                    "unassigned": tkt.unassigned or 0, "sla_breached": tkt.sla_breached or 0},
        "customers": {"total": total_customers or 0},
    }
    cache_set(cache_key, result, 60)
    return result


def list_alerts_for_assistant(actor_role: str, actor_customer_id: str, status: str = None,
                               severity: str = None, limit: int = 20) -> list:
    cid = actor_customer_id if actor_role == "client" else None
    query = Alert.query.order_by(Alert.triggered_at.desc())
    if cid:
        query = query.join(Device, Alert.device_id == Device.id).filter(Device.customer_id == cid)
    if status:
        query = query.filter(Alert.status == status)
    if severity:
        query = query.filter(Alert.severity == severity)
    alerts = query.limit(min(limit, 50)).all()
    return [a.to_dict() for a in alerts]
