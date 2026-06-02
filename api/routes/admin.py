"""
Admin routes — user management (admin-only).
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models.user import User
from models.audit import AuditLog

admin_bp = Blueprint("admin", __name__)


def _require_admin():
    uid = get_jwt_identity()
    user = User.query.get(uid)
    if not user or user.role != "admin":
        return None, jsonify({"error": "Admin access required"}), 403
    return user, None, None


def _audit(action, admin_id, resource_id=None, payload=None):
    log = AuditLog(
        user_id=admin_id,
        action=action,
        resource_type="user",
        resource_id=resource_id,
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent", "")[:500],
        payload=payload,
    )
    db.session.add(log)


@admin_bp.route("/users", methods=["GET"])
@jwt_required()
def list_users():
    admin, err, code = _require_admin()
    if err:
        return err, code

    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify({"users": [u.to_dict() for u in users], "total": len(users)})


@admin_bp.route("/users", methods=["POST"])
@jwt_required()
def create_user():
    admin, err, code = _require_admin()
    if err:
        return err, code

    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    full_name = (data.get("full_name") or "").strip()
    role = (data.get("role") or "technician").strip().lower()
    password = data.get("password") or ""

    if not email or not full_name or not password:
        return jsonify({"error": "email, full_name, and password are required"}), 400
    if role not in ("admin", "technician", "viewer"):
        return jsonify({"error": "role must be admin, technician, or viewer"}), 400
    if len(password) < 8:
        return jsonify({"error": "password must be at least 8 characters"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already in use"}), 409

    user = User(email=email, full_name=full_name, role=role)
    user.set_password(password)
    db.session.add(user)
    _audit("CREATE", admin.id, payload={"email": email, "role": role})
    db.session.commit()
    return jsonify(user.to_dict()), 201


@admin_bp.route("/users/<user_id>", methods=["PUT"])
@jwt_required()
def update_user(user_id):
    admin, err, code = _require_admin()
    if err:
        return err, code

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json(silent=True) or {}
    if "full_name" in data:
        user.full_name = data["full_name"].strip()
    if "role" in data:
        role = data["role"].strip().lower()
        if role not in ("admin", "technician", "viewer"):
            return jsonify({"error": "role must be admin, technician, or viewer"}), 400
        user.role = role
    if "is_active" in data:
        user.is_active = bool(data["is_active"])
    if data.get("password"):
        if len(data["password"]) < 8:
            return jsonify({"error": "password must be at least 8 characters"}), 400
        user.set_password(data["password"])

    _audit("UPDATE", admin.id, resource_id=user_id, payload={"email": user.email})
    db.session.commit()
    return jsonify(user.to_dict())


@admin_bp.route("/users/<user_id>", methods=["DELETE"])
@jwt_required()
def delete_user(user_id):
    admin, err, code = _require_admin()
    if err:
        return err, code

    if user_id == admin.id:
        return jsonify({"error": "Cannot delete your own account"}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    _audit("DELETE", admin.id, resource_id=user_id, payload={"email": user.email})
    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": "User deleted"})
