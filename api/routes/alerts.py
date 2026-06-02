from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from extensions import db
from models.alert import Alert, AlertRule

alerts_bp = Blueprint("alerts", __name__)


def _require_role(*roles):
    claims = get_jwt()
    if claims.get("role") not in roles:
        return jsonify({"error": "Insufficient permissions"}), 403
    return None


# --- Alert Rules ---

@alerts_bp.route("/alert_rules", methods=["GET"])
@jwt_required()
def list_rules():
    rules = AlertRule.query.order_by(AlertRule.name).all()
    return jsonify([r.to_dict() for r in rules]), 200


@alerts_bp.route("/alert_rules", methods=["POST"])
@jwt_required()
def create_rule():
    err = _require_role("admin", "technician")
    if err:
        return err
    data = request.get_json(silent=True) or {}
    if not data.get("name") or not data.get("metric") or not data.get("operator"):
        return jsonify({"error": "name, metric, operator required"}), 400
    rule = AlertRule(
        name=data["name"],
        customer_id=data.get("customer_id"),
        device_group_id=data.get("device_group_id"),
        metric=data["metric"],
        operator=data["operator"],
        threshold=data.get("threshold"),
        severity=data.get("severity", "warning"),
        cooldown_minutes=data.get("cooldown_minutes", 15),
        notification_channels=data.get("notification_channels", {}),
        auto_create_ticket=data.get("auto_create_ticket", False),
        is_active=data.get("is_active", True),
    )
    db.session.add(rule)
    db.session.commit()
    return jsonify(rule.to_dict()), 201


@alerts_bp.route("/alert_rules/<rule_id>", methods=["GET"])
@jwt_required()
def get_rule(rule_id):
    rule = AlertRule.query.get_or_404(rule_id)
    return jsonify(rule.to_dict()), 200


@alerts_bp.route("/alert_rules/<rule_id>", methods=["PUT"])
@jwt_required()
def update_rule(rule_id):
    err = _require_role("admin", "technician")
    if err:
        return err
    rule = AlertRule.query.get_or_404(rule_id)
    data = request.get_json(silent=True) or {}
    for field in ["name", "metric", "operator", "threshold", "severity",
                  "cooldown_minutes", "notification_channels", "auto_create_ticket", "is_active"]:
        if field in data:
            setattr(rule, field, data[field])
    db.session.commit()
    return jsonify(rule.to_dict()), 200


@alerts_bp.route("/alert_rules/<rule_id>", methods=["DELETE"])
@jwt_required()
def delete_rule(rule_id):
    err = _require_role("admin")
    if err:
        return err
    rule = AlertRule.query.get_or_404(rule_id)
    db.session.delete(rule)
    db.session.commit()
    return jsonify({"message": "Rule deleted"}), 200


# --- Active Alerts ---

@alerts_bp.route("/alerts", methods=["GET"])
@jwt_required()
def list_alerts():
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 50, type=int), 200)
    status = request.args.get("status")
    severity = request.args.get("severity")
    device_id = request.args.get("device_id")

    query = Alert.query
    if status:
        query = query.filter_by(status=status)
    if severity:
        query = query.filter_by(severity=severity)
    if device_id:
        query = query.filter_by(device_id=device_id)

    paginated = query.order_by(Alert.triggered_at.desc()).paginate(page=page, per_page=per_page)
    return jsonify({
        "items": [a.to_dict() for a in paginated.items],
        "total": paginated.total,
        "page": page,
    }), 200


@alerts_bp.route("/alerts/<alert_id>/acknowledge", methods=["POST"])
@jwt_required()
def acknowledge_alert(alert_id):
    alert = Alert.query.get_or_404(alert_id)
    alert.status = "acknowledged"
    alert.acknowledged_by = get_jwt_identity()
    alert.acknowledged_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(alert.to_dict()), 200


@alerts_bp.route("/alerts/<alert_id>/resolve", methods=["POST"])
@jwt_required()
def resolve_alert(alert_id):
    alert = Alert.query.get_or_404(alert_id)
    alert.status = "resolved"
    alert.resolved_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(alert.to_dict()), 200
