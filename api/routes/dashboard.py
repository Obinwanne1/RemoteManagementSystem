from datetime import datetime, timezone, timedelta
from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required
from extensions import db
from models.device import Device
from models.alert import Alert
from models.ticket import Ticket
from models.customer import Customer

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/summary", methods=["GET"])
@jwt_required()
def summary():
    total_devices = Device.query.count()
    online_devices = Device.query.filter_by(is_online=True).count()
    offline_devices = total_devices - online_devices
    critical_devices = Device.query.filter_by(status="critical").count()
    warning_devices = Device.query.filter_by(status="warning").count()

    open_alerts = Alert.query.filter_by(status="open").count()
    critical_alerts = Alert.query.filter(
        Alert.status == "open", Alert.severity == "critical"
    ).count()

    open_tickets = Ticket.query.filter(
        Ticket.status.in_(["open", "in_progress"])
    ).count()
    critical_tickets = Ticket.query.filter(
        Ticket.status.in_(["open", "in_progress"]),
        Ticket.priority == "critical",
    ).count()

    total_customers = Customer.query.filter_by(is_active=True).count()

    return jsonify({
        "devices": {
            "total": total_devices,
            "online": online_devices,
            "offline": offline_devices,
            "critical": critical_devices,
            "warning": warning_devices,
        },
        "alerts": {
            "open": open_alerts,
            "critical": critical_alerts,
        },
        "tickets": {
            "open": open_tickets,
            "critical": critical_tickets,
        },
        "customers": {
            "total": total_customers,
        },
    }), 200


@dashboard_bp.route("/health_map", methods=["GET"])
@jwt_required()
def health_map():
    devices = Device.query.order_by(Device.hostname).all()
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
