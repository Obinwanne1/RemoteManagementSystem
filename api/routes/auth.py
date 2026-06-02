from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity, get_jwt
)
from extensions import db, limiter
from models.user import User
from models.audit import AuditLog

auth_bp = Blueprint("auth", __name__)


def _audit(action, user_id=None, payload=None):
    log = AuditLog(
        user_id=user_id,
        action=action,
        resource_type="user",
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent", "")[:500],
        payload=payload,
    )
    db.session.add(log)


@auth_bp.route("/login", methods=["POST"])
@limiter.limit("10 per minute")
def login():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400

    user = User.query.filter_by(email=email, is_active=True).first()
    if not user or not user.check_password(password):
        _audit("login_failed", payload={"email": email})
        db.session.commit()
        return jsonify({"error": "Invalid credentials"}), 401

    user.last_login = datetime.now(timezone.utc)
    _audit("login_success", user_id=user.id)
    db.session.commit()

    access_token = create_access_token(
        identity=user.id,
        additional_claims={"role": user.role, "email": user.email}
    )
    refresh_token = create_refresh_token(identity=user.id)

    return jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": user.to_dict(),
    }), 200


@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    identity = get_jwt_identity()
    user = User.query.get(identity)
    if not user or not user.is_active:
        return jsonify({"error": "User not found"}), 401

    access_token = create_access_token(
        identity=user.id,
        additional_claims={"role": user.role, "email": user.email}
    )
    return jsonify({"access_token": access_token}), 200


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    identity = get_jwt_identity()
    user = User.query.get(identity)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user.to_dict()), 200


@auth_bp.route("/me/password", methods=["PUT"])
@jwt_required()
def change_password():
    identity = get_jwt_identity()
    user = User.query.get(identity)
    data = request.get_json(silent=True) or {}

    if not user.check_password(data.get("current_password", "")):
        return jsonify({"error": "Current password incorrect"}), 400

    new_pw = data.get("new_password", "")
    if len(new_pw) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    user.set_password(new_pw)
    _audit("password_changed", user_id=user.id)
    db.session.commit()
    return jsonify({"message": "Password updated"}), 200
