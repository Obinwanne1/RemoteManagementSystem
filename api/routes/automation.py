from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from extensions import db
from models.automation import AutomationProfile, ScheduledTaskRun
from models.device import Device

automation_bp = Blueprint("automation", __name__)


def _require_role(*roles):
    claims = get_jwt()
    if claims.get("role") not in roles:
        return jsonify({"error": "Insufficient permissions"}), 403
    return None


@automation_bp.route("/profiles", methods=["GET"])
@jwt_required()
def list_profiles():
    customer_id = request.args.get("customer_id")
    query = AutomationProfile.query
    if customer_id:
        query = query.filter_by(customer_id=customer_id)
    profiles = query.order_by(AutomationProfile.name).all()
    return jsonify([p.to_dict() for p in profiles]), 200


@automation_bp.route("/profiles", methods=["POST"])
@jwt_required()
def create_profile():
    err = _require_role("admin", "technician")
    if err:
        return err
    data = request.get_json(silent=True) or {}
    if not data.get("name"):
        return jsonify({"error": "name required"}), 400
    profile = AutomationProfile(
        name=data["name"],
        customer_id=data.get("customer_id"),
        device_group_id=data.get("device_group_id"),
        is_active=data.get("is_active", True),
        schedule_type=data.get("schedule_type", "weekly"),
        schedule_config=data.get("schedule_config", {}),
        run_on_new_agents=data.get("run_on_new_agents", False),
        notification_emails=data.get("notification_emails", []),
        os_patch_config=data.get("os_patch_config", {}),
        software_patch_config=data.get("software_patch_config", {}),
        disk_config=data.get("disk_config", {}),
        maintenance_config=data.get("maintenance_config", {}),
        scripts=data.get("scripts", []),
    )
    db.session.add(profile)
    db.session.commit()
    return jsonify(profile.to_dict()), 201


@automation_bp.route("/profiles/<profile_id>", methods=["GET"])
@jwt_required()
def get_profile(profile_id):
    profile = AutomationProfile.query.get_or_404(profile_id)
    return jsonify(profile.to_dict()), 200


@automation_bp.route("/profiles/<profile_id>", methods=["PUT"])
@jwt_required()
def update_profile(profile_id):
    err = _require_role("admin", "technician")
    if err:
        return err
    profile = AutomationProfile.query.get_or_404(profile_id)
    data = request.get_json(silent=True) or {}
    for field in ["name", "is_active", "schedule_type", "schedule_config",
                  "run_on_new_agents", "notification_emails", "os_patch_config",
                  "software_patch_config", "disk_config", "maintenance_config", "scripts"]:
        if field in data:
            setattr(profile, field, data[field])
    profile.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(profile.to_dict()), 200


@automation_bp.route("/profiles/<profile_id>", methods=["DELETE"])
@jwt_required()
def delete_profile(profile_id):
    err = _require_role("admin")
    if err:
        return err
    profile = AutomationProfile.query.get_or_404(profile_id)
    db.session.delete(profile)
    db.session.commit()
    return jsonify({"message": "Profile deleted"}), 200


@automation_bp.route("/profiles/<profile_id>/run", methods=["POST"])
@jwt_required()
def run_profile_now(profile_id):
    err = _require_role("admin", "technician")
    if err:
        return err
    profile = AutomationProfile.query.get_or_404(profile_id)

    # Find target devices
    from models.customer import DeviceGroup
    if profile.device_group_id:
        devices = Device.query.filter_by(
            group_id=profile.device_group_id, is_online=True
        ).all()
    elif profile.customer_id:
        devices = Device.query.filter_by(
            customer_id=profile.customer_id, is_online=True
        ).all()
    else:
        devices = Device.query.filter_by(is_online=True).all()

    if not devices:
        return jsonify({"error": "No online devices found for this profile"}), 400

    runs = []
    for device in devices:
        run = ScheduledTaskRun(
            profile_id=profile_id,
            device_id=device.id,
            status="queued",
        )
        db.session.add(run)
        runs.append(run)

    profile.last_run_at = datetime.now(timezone.utc)
    db.session.commit()

    return jsonify({
        "message": "Profile run queued",
        "device_count": len(runs),
        "run_ids": [r.id for r in runs],
    }), 202


@automation_bp.route("/runs", methods=["GET"])
@jwt_required()
def list_runs():
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 50, type=int), 200)
    profile_id = request.args.get("profile_id")

    query = ScheduledTaskRun.query
    if profile_id:
        query = query.filter_by(profile_id=profile_id)

    paginated = query.order_by(ScheduledTaskRun.started_at.desc()).paginate(page=page, per_page=per_page)
    return jsonify({
        "items": [r.to_dict() for r in paginated.items],
        "total": paginated.total,
        "page": page,
    }), 200
