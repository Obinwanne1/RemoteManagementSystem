from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from sqlalchemy import func
from extensions import db
from models.device import Device, DeviceMetrics

devices_bp = Blueprint("devices", __name__)


def _batch_latest_metrics(device_ids: list) -> dict:
    """Return {device_id: metrics_dict} for a list of device IDs. 1 query."""
    if not device_ids:
        return {}
    subq = (
        db.select(func.max(DeviceMetrics.id).label("max_id"))
        .where(DeviceMetrics.device_id.in_(device_ids))
        .group_by(DeviceMetrics.device_id)
        .subquery()
    )
    rows = db.session.execute(
        db.select(DeviceMetrics).join(subq, DeviceMetrics.id == subq.c.max_id)
    ).scalars().all()
    return {m.device_id: m.to_dict() for m in rows}


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

    platform_filter = request.args.get("platform")
    is_agentless = request.args.get("is_agentless")
    device_type = request.args.get("device_type")

    query = Device.query
    if customer_id:
        query = query.filter_by(customer_id=customer_id)
    if group_id:
        query = query.filter_by(group_id=group_id)
    if status:
        query = query.filter_by(status=status)
    if is_online is not None:
        query = query.filter_by(is_online=is_online.lower() == "true")
    if platform_filter:
        query = query.filter_by(platform=platform_filter)
    if is_agentless is not None:
        query = query.filter_by(is_agentless=is_agentless.lower() == "true")
    if device_type:
        query = query.filter_by(device_type=device_type)
    if q:
        query = query.filter(Device.hostname.ilike(f"%{q}%"))

    paginated = query.order_by(Device.hostname).paginate(page=page, per_page=per_page)
    metrics_by_device = _batch_latest_metrics([d.id for d in paginated.items])
    return jsonify({
        "items": [
            d.to_dict(include_latest_metrics=True, latest_metrics_data=metrics_by_device.get(d.id))
            for d in paginated.items
        ],
        "total": paginated.total,
        "page": page,
        "pages": paginated.pages,
    }), 200


@devices_bp.route("/platform_counts", methods=["GET"])
@jwt_required()
def platform_counts():
    rows = db.session.execute(
        db.select(Device.platform, func.count(Device.id)).group_by(Device.platform)
    ).all()
    by_platform = {r[0]: r[1] for r in rows if r[0]}
    agentless_count = Device.query.filter_by(is_agentless=True).count()
    return jsonify({"by_platform": by_platform, "agentless": agentless_count}), 200


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
    for field in ["display_name", "group_id", "customer_id"]:
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
    run_id = _queue_builtin_task(device_id, "reboot")
    return jsonify({"message": "Reboot queued", "device_id": device_id, "run_id": run_id}), 202


@devices_bp.route("/<device_id>/shutdown", methods=["POST"])
@jwt_required()
def shutdown_device(device_id):
    err = _require_role("admin", "technician")
    if err:
        return err
    device = Device.query.get_or_404(device_id)
    if not device.is_online:
        return jsonify({"error": "Device is offline"}), 400
    run_id = _queue_builtin_task(device_id, "shutdown")
    return jsonify({"message": "Shutdown queued", "device_id": device_id, "run_id": run_id}), 202


@devices_bp.route("/<device_id>/queue_task", methods=["POST"])
@jwt_required()
def queue_device_task(device_id):
    """Queue a built-in maintenance task for a device. Agent picks it up on next poll."""
    err = _require_role("admin", "technician")
    if err:
        return err
    Device.query.get_or_404(device_id)
    data = request.get_json(silent=True) or {}
    task_type = (data.get("task_type") or "").strip()
    if not task_type:
        return jsonify({"error": "task_type required"}), 400

    from utils.builtin_scripts import get_builtin_script_id, TASK_TYPE_TO_TAG
    if task_type not in TASK_TYPE_TO_TAG:
        return jsonify({"error": f"Unknown task_type '{task_type}'. Valid: {list(TASK_TYPE_TO_TAG)}"}), 400

    run_id = _queue_builtin_task(device_id, task_type, timeout=data.get("timeout_seconds", 300))
    if not run_id:
        return jsonify({"error": "Built-in script not found. Restart API to re-sync."}), 500

    return jsonify({"run_id": run_id, "task_type": task_type, "status": "queued"}), 202


@devices_bp.route("/<device_id>/deploy_patches", methods=["POST"])
@jwt_required()
def deploy_patches_route(device_id):
    """Trigger Celery task to deploy approved patches to a device."""
    err = _require_role("admin", "technician")
    if err:
        return err
    Device.query.get_or_404(device_id)
    data = request.get_json(silent=True) or {}
    patch_ids = data.get("patch_ids", [])
    if not patch_ids:
        return jsonify({"error": "patch_ids required"}), 400
    from tasks.patch_tasks import deploy_patches
    deploy_patches.delay(device_id, patch_ids)
    return jsonify({"message": "Patch deployment queued", "count": len(patch_ids)}), 202


@devices_bp.route("/<device_id>/ping_check", methods=["POST"])
@jwt_required()
def ping_check(device_id):
    """Immediately ping an agentless device and update its online status."""
    device = Device.query.get_or_404(device_id)
    if not device.is_agentless or not device.ip_address:
        return jsonify({"error": "Only available for agentless devices with an IP"}), 400
    from tasks.network_tasks import _ping_host
    alive = _ping_host(device.ip_address)
    now = datetime.now(timezone.utc)
    device.is_online = alive
    if alive:
        device.last_seen = now
    db.session.commit()
    return jsonify({"is_online": alive, "checked_at": now.isoformat()}), 200


def _queue_builtin_task(device_id: str, task_type: str, timeout: int = 300):
    """Create a ScriptRun for a built-in task. Returns run_id or None."""
    from models.script import ScriptRun
    from utils.builtin_scripts import get_builtin_script_id
    from flask_jwt_extended import get_jwt_identity

    script_id = get_builtin_script_id(task_type)
    if not script_id:
        return None
    try:
        uid = get_jwt_identity()
    except Exception:
        uid = None

    run = ScriptRun(
        script_id=script_id,
        device_id=device_id,
        triggered_by=uid,
        timeout_seconds=timeout,
    )
    db.session.add(run)
    db.session.commit()
    return run.id
