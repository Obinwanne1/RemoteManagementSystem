from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from sqlalchemy import func, case, and_
from extensions import db
from models.device import Device
from models.alert import Alert
from models.ticket import Ticket
from models.customer import Customer
from utils.cache import cache_get, cache_set

dashboard_bp = Blueprint("dashboard", __name__)

_SUMMARY_TTL = 60   # seconds
_HEALTHMAP_TTL = 30  # seconds


def _scoped_customer_id():
    """Return customer_id if caller is client role, else None (MSP staff see all)."""
    claims = get_jwt()
    if claims.get("role") == "client":
        return claims.get("customer_id")
    return None


@dashboard_bp.route("/summary", methods=["GET"])
@jwt_required()
def summary():
    cid = _scoped_customer_id()  # None = MSP staff (no filter); UUID = client (their tenant only)
    cache_key = f"rmm:dash:summary:{cid or 'all'}"
    cached = cache_get(cache_key)
    if cached:
        return jsonify(cached), 200

    # Device counts — 1 query instead of 5
    dev_q = db.select(
        func.count().label("total"),
        func.sum(case((Device.is_online == True, 1), else_=0)).label("online"),
        func.sum(case((Device.status == "critical", 1), else_=0)).label("critical"),
        func.sum(case((Device.status == "warning", 1), else_=0)).label("warning"),
    ).select_from(Device)
    if cid:
        dev_q = dev_q.where(Device.customer_id == cid)
    dev = db.session.execute(dev_q).one()

    # Alert counts — 1 query instead of 2
    alr_q = db.select(
        func.sum(case((Alert.status == "open", 1), else_=0)).label("open"),
        func.sum(case(
            (and_(Alert.status == "open", Alert.severity == "critical"), 1),
            else_=0,
        )).label("critical"),
    ).select_from(Alert)
    if cid:
        alr_q = alr_q.join(Device, Alert.device_id == Device.id).where(Device.customer_id == cid)
    alr = db.session.execute(alr_q).one()

    # Ticket counts — 1 query
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

    # Customer count — 1 scalar (clients see just their own, MSP staff see all)
    total_customers = 1 if cid else db.session.execute(
        db.select(func.count()).select_from(Customer).where(Customer.is_active == True)
    ).scalar()

    total = dev.total or 0
    online = dev.online or 0
    result = {
        "devices": {
            "total": total,
            "online": online,
            "offline": total - online,
            "critical": dev.critical or 0,
            "warning": dev.warning or 0,
        },
        "alerts": {
            "open": alr.open or 0,
            "critical": alr.critical or 0,
        },
        "tickets": {
            "open": tkt.open or 0,
            "critical": tkt.critical or 0,
            "unassigned": tkt.unassigned or 0,
            "sla_breached": tkt.sla_breached or 0,
        },
        "customers": {
            "total": total_customers or 0,
        },
    }
    cache_set(cache_key, result, _SUMMARY_TTL)
    return jsonify(result), 200


@dashboard_bp.route("/health_map", methods=["GET"])
@jwt_required()
def health_map():
    from sqlalchemy.orm import load_only
    cid = _scoped_customer_id()
    cache_key = f"rmm:dash:health_map:{cid or 'all'}"
    cached = cache_get(cache_key)
    if cached:
        return jsonify(cached), 200

    q = Device.query.options(load_only(
        Device.id, Device.hostname, Device.display_name,
        Device.status, Device.is_online, Device.customer_id, Device.last_seen,
    ))
    if cid:
        q = q.filter(Device.customer_id == cid)
    devices = q.order_by(Device.hostname).limit(500).all()
    result = [
        {
            "id": d.id,
            "hostname": d.display_name or d.hostname,
            "status": d.status,
            "is_online": d.is_online,
            "customer_id": d.customer_id,
            "last_seen": d.last_seen.isoformat() if d.last_seen else None,
        }
        for d in devices
    ]
    cache_set(cache_key, result, _HEALTHMAP_TTL)
    return jsonify(result), 200


@dashboard_bp.route("/recent_alerts", methods=["GET"])
@jwt_required()
def recent_alerts():
    cid = _scoped_customer_id()
    cache_key = f"rmm:dash:recent_alerts:{cid or 'all'}"
    cached = cache_get(cache_key)
    if cached:
        return jsonify(cached), 200

    q = Alert.query.order_by(Alert.triggered_at.desc())
    if cid:
        q = q.join(Device, Alert.device_id == Device.id).filter(Device.customer_id == cid)
    alerts = q.limit(20).all()
    result = [a.to_dict() for a in alerts]
    cache_set(cache_key, result, 15)
    return jsonify(result), 200


@dashboard_bp.route("/activity_feed", methods=["GET"])
@jwt_required()
def activity_feed():
    from models.audit import AuditLog
    from models.user import User
    claims = get_jwt()
    if claims.get("role") == "client":
        return jsonify([]), 200

    _FEED_TTL = 60
    cached = cache_get("rmm:dash:activity_feed")
    if cached:
        return jsonify(cached), 200

    rows = (
        db.session.query(AuditLog, User.email, User.full_name)
        .outerjoin(User, AuditLog.user_id == User.id)
        .order_by(AuditLog.created_at.desc())
        .limit(25)
        .all()
    )

    result = []
    for log, user_email, user_full_name in rows:
        d = log.to_dict()
        d["user_email"] = user_email or "—"
        d["user_full_name"] = user_full_name or "—"
        result.append(d)

    cache_set("rmm:dash:activity_feed", result, _FEED_TTL)
    return jsonify(result), 200
