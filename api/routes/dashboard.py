from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy import func, case, and_
from extensions import db
from models.device import Device
from models.alert import Alert
from models.ticket import Ticket
from models.customer import Customer

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/summary", methods=["GET"])
@jwt_required()
def summary():
    # Device counts — 1 query instead of 5
    dev = db.session.execute(
        db.select(
            func.count().label("total"),
            func.sum(case((Device.is_online == True, 1), else_=0)).label("online"),
            func.sum(case((Device.status == "critical", 1), else_=0)).label("critical"),
            func.sum(case((Device.status == "warning", 1), else_=0)).label("warning"),
        ).select_from(Device)
    ).one()

    # Alert counts — 1 query instead of 2
    alr = db.session.execute(
        db.select(
            func.sum(case((Alert.status == "open", 1), else_=0)).label("open"),
            func.sum(case(
                (and_(Alert.status == "open", Alert.severity == "critical"), 1),
                else_=0,
            )).label("critical"),
        ).select_from(Alert)
    ).one()

    # Ticket counts — 1 query instead of 2
    tkt = db.session.execute(
        db.select(
            func.sum(case((Ticket.status.in_(["open", "in_progress"]), 1), else_=0)).label("open"),
            func.sum(case(
                (and_(Ticket.status.in_(["open", "in_progress"]), Ticket.priority == "critical"), 1),
                else_=0,
            )).label("critical"),
        ).select_from(Ticket)
    ).one()

    # Customer count — 1 scalar
    total_customers = db.session.execute(
        db.select(func.count()).select_from(Customer).where(Customer.is_active == True)
    ).scalar()

    total = dev.total or 0
    online = dev.online or 0
    return jsonify({
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
        },
        "customers": {
            "total": total_customers or 0,
        },
    }), 200


@dashboard_bp.route("/health_map", methods=["GET"])
@jwt_required()
def health_map():
    devices = Device.query.order_by(Device.hostname).limit(500).all()
    return jsonify([
        {
            "id": d.id,
            "hostname": d.display_name or d.hostname,
            "status": d.status,
            "is_online": d.is_online,
            "customer_id": d.customer_id,
            "last_seen": d.last_seen.isoformat() if d.last_seen else None,
        }
        for d in devices
    ]), 200


@dashboard_bp.route("/recent_alerts", methods=["GET"])
@jwt_required()
def recent_alerts():
    alerts = Alert.query.order_by(Alert.triggered_at.desc()).limit(20).all()
    return jsonify([a.to_dict() for a in alerts]), 200


@dashboard_bp.route("/activity_feed", methods=["GET"])
@jwt_required()
def activity_feed():
    from models.audit import AuditLog
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(20).all()
    return jsonify([log.to_dict() for log in logs]), 200
