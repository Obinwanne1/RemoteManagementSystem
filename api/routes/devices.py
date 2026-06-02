from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from extensions import db
from models.device import Device, DeviceMetrics

devices_bp = Blueprint("devices", __name__)


def _require_role(*roles):
    claims = get_jwt()
    if claims.get("role") not in roles:
        return jsonify({"error": "Insufficient permissions"}), 403
    return None


@devices_bp.route("/", methods=["GET"])
@jwt_required()
def list_devices():
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 50, type=int), 200)
    customer_id = request.args.get("customer_id")
    group_id = request.args.get("group_id")
    status = request.args.get("status")
    is_online = request.args.get("is_online")
    q = request.args.get("q", "")

    query = Device.query
    if customer_id:
        query = query.filter_by(customer_id=customer_id)
    if group_id:
        query = query.filter_by(group_id=group_id)
    if status:
        query = query.filter_by(status=status)
    if is_online is not None:
        query = query.filter_by(is_online=is_online.lower() == "true")
    if q:
        query = query.filter(Device.hostname.ilike(f"%{q}%"))

    paginated = query.order_by(Device.hostname).paginate(page=page, per_page=per_page)
    return jsonify({
        "items": [d.to_dict(include_latest_metrics=True) for d in paginated.items],
        "total": paginated.total,
        "page": page,
        "pages": paginated.pages,
    }), 200


@devices_bp.route("/<device_id>", methods=["GET"])
@jwt_required()
def get_device(device_id):
    device = Device.query.get_or_404(device_id)
    return jsonify(device.to_dict(include_latest_metrics=True)), 200


@devices_bp.route("/<device_id>", methods=["PUT"])
@jwt_required()
def update_device(device_id):
    err = _require_role("admin", "technician")
    if err:
        return err
    device = Device.query.get_or_404(device_id)
    data = request.get_json(silent=True) or {}
    for field in ["display_name", "group_id"]:
        if field in data:
            setattr(device, field, data[field])
    db.session.commit()
    return jsonify(device.to_dict()), 200


@devices_bp.route("/<device_id>", methods=["DELETE"])
@jwt_required()
def delete_device(device_id):
    err = _require_role("admin")
    if err:
        return err
    device = Device.query.get_or_404(device_id)
    db.session.delete(device)
    db.session.commit()
    return jsonify({"message": "Device removed"}), 200


@devices_bp.route("/<device_id>/metrics", methods=["GET"])
@jwt_required()
def device_metrics(device_id):
    Device.query.get_or_404(device_id)
    hours = request.args.get("hours", 24, type=int)
    since = datetime.now(timezone.utc) - timedelta(hours=min(hours, 168))

    metrics = DeviceMetrics.query.filter(
        DeviceMetrics.device_id == device_id,
        DeviceMetrics.collected_at >= since,
    ).order_by(DeviceMetrics.collected_at).all()

    return jsonify([m.to_dict() for m in metrics]), 200


@devices_bp.route("/<device_id>/software", methods=["GET"])
@jwt_required()
def device_software(device_id):
    Device.query.get_or_404(device_id)
    from models.device import InstalledSoftware
    q = request.args.get("q", "")
    query = InstalledSoftware.query.filter_by(device_id=device_id)
    if q:
        query = query.filter(InstalledSoftware.name.ilike(f"%{q}%"))
    software = query.order_by(InstalledSoftware.name).all()
    return jsonify([s.to_dict() for s in software]), 200


@devices_bp.route("/<device_id>/reboot", methods=["POST"])
@jwt_required()
def reboot_device(device_id):
    err = _require_role("admin", "technician")
    if err:
        return err
    device = Device.query.get_or_404(device_id)
    if not device.is_online:
        return jsonify({"error": "Device is offline"}), 400
    # Task queuing handled in Phase 4/5
    return jsonify({"message": "Reboot queued", "device_id": device_id}), 202


@devices_bp.route("/<device_id>/shutdown", methods=["POST"])
@jwt_required()
def shutdown_device(device_id):
    err = _require_role("admin", "technician")
    if err:
        return err
    device = Device.query.get_or_404(device_id)
    if not device.is_online:
        return jsonify({"error": "Device is offline"}), 400
    return jsonify({"message": "Shutdown queued", "device_id": device_id}), 202
