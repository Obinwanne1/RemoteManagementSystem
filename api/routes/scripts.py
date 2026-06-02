from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from extensions import db
from models.script import Script, ScriptRun
from models.device import Device

scripts_bp = Blueprint("scripts", __name__)

ALLOWED_TYPES = {"bat", "ps1", "py"}
MAX_SCRIPT_SIZE = 512 * 1024  # 512KB


def _require_role(*roles):
    claims = get_jwt()
    if claims.get("role") not in roles:
        return jsonify({"error": "Insufficient permissions"}), 403
    return None


@scripts_bp.route("/", methods=["GET"])
@jwt_required()
def list_scripts():
    is_builtin = request.args.get("is_builtin")
    file_type = request.args.get("file_type")

    query = Script.query
    if is_builtin is not None:
        query = query.filter_by(is_builtin=is_builtin.lower() == "true")
    if file_type:
        query = query.filter_by(file_type=file_type)

    scripts = query.order_by(Script.name).all()
    return jsonify([s.to_dict(include_content=False) for s in scripts]), 200


@scripts_bp.route("/", methods=["POST"])
@jwt_required()
def create_script():
    err = _require_role("admin", "technician")
    if err:
        return err
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    file_type = data.get("file_type", "").strip().lower()
    content = data.get("content", "")

    if not name or not file_type or not content:
        return jsonify({"error": "name, file_type, content required"}), 400
    if file_type not in ALLOWED_TYPES:
        return jsonify({"error": f"file_type must be one of: {', '.join(ALLOWED_TYPES)}"}), 400
    if len(content.encode("utf-8")) > MAX_SCRIPT_SIZE:
        return jsonify({"error": "Script exceeds 512KB limit"}), 400

    script = Script(
        name=name,
        description=data.get("description"),
        file_type=file_type,
        content=content,
        uploaded_by=get_jwt_identity(),
        os_target=data.get("os_target", "windows"),
        tags=data.get("tags", []),
    )
    db.session.add(script)
    db.session.commit()
    return jsonify(script.to_dict()), 201


@scripts_bp.route("/<script_id>", methods=["GET"])
@jwt_required()
def get_script(script_id):
    script = Script.query.get_or_404(script_id)
    return jsonify(script.to_dict(include_content=True)), 200


@scripts_bp.route("/<script_id>", methods=["PUT"])
@jwt_required()
def update_script(script_id):
    err = _require_role("admin", "technician")
    if err:
        return err
    script = Script.query.get_or_404(script_id)
    if script.is_builtin:
        return jsonify({"error": "Cannot edit built-in scripts"}), 400
    data = request.get_json(silent=True) or {}
    for field in ["name", "description", "content", "tags"]:
        if field in data:
            setattr(script, field, data[field])
    db.session.commit()
    return jsonify(script.to_dict()), 200


@scripts_bp.route("/<script_id>", methods=["DELETE"])
@jwt_required()
def delete_script(script_id):
    err = _require_role("admin", "technician")
    if err:
        return err
    script = Script.query.get_or_404(script_id)
    if script.is_builtin:
        return jsonify({"error": "Cannot delete built-in scripts"}), 400
    db.session.delete(script)
    db.session.commit()
    return jsonify({"message": "Script deleted"}), 200


@scripts_bp.route("/<script_id>/run", methods=["POST"])
@jwt_required()
def run_script(script_id):
    err = _require_role("admin", "technician")
    if err:
        return err
    script = Script.query.get_or_404(script_id)
    data = request.get_json(silent=True) or {}
    device_ids = data.get("device_ids", [])
    if not device_ids:
        return jsonify({"error": "device_ids required"}), 400

    runs = []
    for device_id in device_ids:
        device = Device.query.get(device_id)
        if not device:
            continue
        run = ScriptRun(
            script_id=script_id,
            device_id=device_id,
            triggered_by=get_jwt_identity(),
            status="queued",
            timeout_seconds=data.get("timeout_seconds", 300),
        )
        db.session.add(run)
        runs.append(run)
    db.session.commit()
    return jsonify({"queued": len(runs), "run_ids": [r.id for r in runs]}), 202


@scripts_bp.route("/runs", methods=["GET"])
@jwt_required()
def list_runs():
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 50, type=int), 200)
    device_id = request.args.get("device_id")
    script_id = request.args.get("script_id")
    status = request.args.get("status")

    query = ScriptRun.query
    if device_id:
        query = query.filter_by(device_id=device_id)
    if script_id:
        query = query.filter_by(script_id=script_id)
    if status:
        query = query.filter_by(status=status)

    paginated = query.order_by(ScriptRun.triggered_at.desc()).paginate(page=page, per_page=per_page)
    return jsonify({
        "items": [r.to_dict() for r in paginated.items],
        "total": paginated.total,
        "page": page,
    }), 200


@scripts_bp.route("/runs/<run_id>", methods=["GET"])
@jwt_required()
def get_run(run_id):
    run = ScriptRun.query.get_or_404(run_id)
    return jsonify(run.to_dict()), 200
