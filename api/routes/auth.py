from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity, get_jwt
)
import pyotp
from extensions import db, limiter
from models.user import User
from models.audit import AuditLog

# Short-lived JWT purpose claim used for the MFA pending step
_MFA_PENDING = "mfa_pending"

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

    # If MFA is enabled, issue a short-lived pending token — full JWT comes after TOTP
    if user.mfa_enabled and user.mfa_secret:
        mfa_token = create_access_token(
            identity=user.id,
            additional_claims={"purpose": _MFA_PENDING},
            expires_delta=__import__("datetime").timedelta(minutes=5),
        )
        return jsonify({"status": "mfa_required", "mfa_token": mfa_token}), 200

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
    user.must_change_password = False
    _audit("password_changed", user_id=user.id)
    db.session.commit()
    return jsonify({"message": "Password updated"}), 200


@auth_bp.route("/me/force-change-password", methods=["POST"])
@jwt_required()
def force_change_password():
    """Used on forced first-login password change — no current password required."""
    identity = get_jwt_identity()
    user = User.query.get(identity)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json(silent=True) or {}
    new_pw = data.get("new_password", "")
    if len(new_pw) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    user.set_password(new_pw)
    user.must_change_password = False
    _audit("force_password_changed", user_id=user.id)
    db.session.commit()
    return jsonify({"message": "Password updated"}), 200


# ── MFA endpoints ────────────────────────────────────────────────────────────

@auth_bp.route("/mfa/setup", methods=["POST"])
@jwt_required()
def mfa_setup():
    """Generate a new TOTP secret for the current user. Returns QR code URI.
    User must call /mfa/enable with a valid code to activate MFA."""
    identity = get_jwt_identity()
    user = User.query.get(identity)
    if not user:
        return jsonify({"error": "User not found"}), 404

    secret = pyotp.random_base32()
    # Store provisionally — not active until verified
    user.mfa_secret = secret
    db.session.commit()

    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(
        name=user.email, issuer_name="RMM System"
    )
    return jsonify({
        "secret": secret,
        "provisioning_uri": provisioning_uri,
        "message": "Scan the QR code with your authenticator app, then call /mfa/enable with a valid code.",
    }), 200


@auth_bp.route("/mfa/enable", methods=["POST"])
@jwt_required()
def mfa_enable():
    """Verify TOTP code and activate MFA on the account."""
    identity = get_jwt_identity()
    user = User.query.get(identity)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json(silent=True) or {}
    code = str(data.get("code", "")).strip()
    if not code:
        return jsonify({"error": "TOTP code required"}), 400

    if not user.mfa_secret:
        return jsonify({"error": "Call /mfa/setup first"}), 400

    totp = pyotp.TOTP(user.mfa_secret)
    if not totp.verify(code, valid_window=1):
        return jsonify({"error": "Invalid or expired TOTP code"}), 401

    user.mfa_enabled = True
    _audit("mfa_enabled", user_id=user.id)
    db.session.commit()
    return jsonify({"message": "MFA enabled successfully"}), 200


@auth_bp.route("/mfa/login", methods=["POST"])
@limiter.limit("10 per minute")
def mfa_login():
    """Second step of MFA login. Accepts mfa_token + TOTP code, returns full JWT."""
    data = request.get_json(silent=True) or {}
    mfa_token = data.get("mfa_token", "")
    code = str(data.get("code", "")).strip()

    if not mfa_token or not code:
        return jsonify({"error": "mfa_token and code required"}), 400

    # Validate the pending MFA token
    from flask_jwt_extended import decode_token
    try:
        decoded = decode_token(mfa_token)
    except Exception:
        return jsonify({"error": "Invalid or expired MFA token"}), 401

    if decoded.get("purpose") != _MFA_PENDING:
        return jsonify({"error": "Invalid token type"}), 401

    user_id = decoded.get("sub")
    user = User.query.get(user_id)
    if not user or not user.is_active or not user.mfa_secret:
        return jsonify({"error": "User not found or MFA not configured"}), 401

    totp = pyotp.TOTP(user.mfa_secret)
    if not totp.verify(code, valid_window=1):
        _audit("mfa_failed", user_id=user.id)
        db.session.commit()
        return jsonify({"error": "Invalid or expired TOTP code"}), 401

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


@auth_bp.route("/mfa/disable", methods=["POST"])
@jwt_required()
def mfa_disable():
    """Disable MFA. Requires current password for confirmation."""
    identity = get_jwt_identity()
    user = User.query.get(identity)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json(silent=True) or {}
    if not user.check_password(data.get("password", "")):
        return jsonify({"error": "Password confirmation required"}), 401

    user.mfa_enabled = False
    user.mfa_secret = None
    _audit("mfa_disabled", user_id=user.id)
    db.session.commit()
    return jsonify({"message": "MFA disabled"}), 200
