"""Mobile Device Management routes — Android Management API integrations,
enrollment (with enforced device-owner consent for BYOD), and remote commands.

No custom agent runs on the phone. Managed devices stay `Device.is_agentless=True`
— what unlocks real actions is `device.mdm_enrollment is not None`, checked via
`_mdm_scope_check` below on every mutating route (same pattern as devices.py's
`_client_scope_check`, established after the cross-tenant leak fixed in 4d4362a).
"""
import logging
import secrets
from datetime import datetime, timezone, timedelta

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity

from extensions import db, limiter
from models.mdm_integration import MdmIntegration, MobileEnrollment, encrypt_cred
from models.device import Device
from models.user import User
from models.audit import AuditLog
from utils.cache import cache_get, cache_set, cache_delete
from utils.auth_decorators import require_role as _require_role
from utils.scope import require_customer_scope as _mdm_scope_check

logger = logging.getLogger(__name__)
mobile_mdm_bp = Blueprint("mobile_mdm", __name__)

CONSENT_TEXT_VERSION = "2026-09-22-v1"
_BIND_STATE_TTL = 900  # 15 min to complete the Google-hosted signup flow

# Commands a self-service `role=client` may issue on their own enrolled device.
_CLIENT_ALLOWED_COMMANDS = {"lock", "start_lost_mode", "stop_lost_mode"}


def _client_customer_id_or_error():
    claims = get_jwt()
    if claims.get("role") != "client":
        return None, None
    uid = get_jwt_identity()
    user = db.session.get(User, uid)
    if not user or not user.customer_id:
        return None, (jsonify({"error": "No customer assigned to this account"}), 403)
    return user.customer_id, None


def _audit(action, resource_id, payload):
    try:
        uid = get_jwt_identity()
    except Exception:
        uid = None
    db.session.add(AuditLog(
        user_id=uid, action=action, resource_type="mobile_device",
        resource_id=resource_id, ip_address=request.remote_addr, payload=payload,
    ))


# ─── Integration CRUD ──────────────────────────────────────────────────────────

@mobile_mdm_bp.route("/integrations", methods=["GET"])
@jwt_required()
def list_integrations():
    err = _require_role("admin", "technician")
    if err:
        return err
    integrations = MdmIntegration.query.order_by(MdmIntegration.created_at.desc()).all()
    return jsonify([i.to_dict() for i in integrations]), 200


@mobile_mdm_bp.route("/integrations", methods=["POST"])
@jwt_required()
@limiter.limit("10 per minute")
def create_integration():
    err = _require_role("admin")
    if err:
        return err
    data = request.get_json(silent=True) or {}
    if not data.get("name") or not data.get("project_id"):
        return jsonify({"error": "name and project_id required"}), 400

    integration = MdmIntegration(
        name=data["name"],
        type=data.get("type", "android"),
        customer_id=data.get("customer_id"),
        project_id=data["project_id"],
    )
    db.session.add(integration)
    db.session.commit()
    return jsonify(integration.to_dict()), 201


@mobile_mdm_bp.route("/integrations/<integration_id>", methods=["DELETE"])
@jwt_required()
def delete_integration(integration_id):
    err = _require_role("admin")
    if err:
        return err
    integration = db.get_or_404(MdmIntegration, integration_id)
    db.session.delete(integration)
    db.session.commit()
    return jsonify({"message": "Integration deleted"}), 200


@mobile_mdm_bp.route("/integrations/<integration_id>/credentials", methods=["POST"])
@jwt_required()
@limiter.limit("10 per minute")
def upload_credentials(integration_id):
    """Multipart upload of the Google service-account JSON key. Never written to
    disk — straight into the encrypted DB column."""
    err = _require_role("admin")
    if err:
        return err
    integration = db.get_or_404(MdmIntegration, integration_id)
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "file required"}), 400
    raw = file.read().decode("utf-8", errors="replace")
    try:
        import json
        json.loads(raw)  # validate it's actually JSON before storing
    except ValueError:
        return jsonify({"error": "Uploaded file is not valid JSON"}), 400

    integration.service_account_json_enc = encrypt_cred(raw)
    db.session.commit()
    return jsonify({"message": "Credentials stored"}), 200


@mobile_mdm_bp.route("/integrations/<integration_id>/bind", methods=["POST"])
@jwt_required()
def start_binding(integration_id):
    """Step 1 of one-time enterprise binding. Returns {signup_url} for the admin
    to open in a browser and complete Google's hosted business-signup flow."""
    err = _require_role("admin")
    if err:
        return err
    integration = db.get_or_404(MdmIntegration, integration_id)
    if not integration.service_account_json_enc:
        return jsonify({"error": "Upload service-account credentials first"}), 400

    data = request.get_json(silent=True) or {}
    callback_base = data.get("callback_base_url") or request.host_url.rstrip("/")
    callback_url = f"{callback_base}/api/mdm/integrations/{integration_id}/bind_callback"

    try:
        client = integration.get_client()
        result = client.create_signup_url(callback_url)
    except Exception as exc:
        logger.error("MDM bind start failed for %s: %s", integration_id, exc, exc_info=True)
        return jsonify({"error": "Could not start MDM enrollment. Check integration credentials and try again."}), 502

    state = secrets.token_urlsafe(24)
    cache_set(f"rmm:mdm:bind_state:{state}", {
        "integration_id": integration_id,
        "signup_url_name": result.get("name"),
    }, _BIND_STATE_TTL)

    return jsonify({"signup_url": f"{result.get('url')}&state={state}"}), 200


@mobile_mdm_bp.route("/integrations/<integration_id>/bind_callback", methods=["GET"])
def bind_callback(integration_id):
    """Google's browser redirect target — no JWT on this request. Validated via
    the short-TTL `state` nonce created in start_binding instead."""
    state = request.args.get("state", "")
    enterprise_token = request.args.get("enterpriseToken", "")
    pending = cache_get(f"rmm:mdm:bind_state:{state}") if state else None
    if not pending or pending.get("integration_id") != integration_id or not enterprise_token:
        return jsonify({"error": "Invalid or expired binding request"}), 400
    cache_delete(f"rmm:mdm:bind_state:{state}")

    integration = db.get_or_404(MdmIntegration, integration_id)
    try:
        client = integration.get_client()
        result = client.create_enterprise(
            signup_url_name=pending["signup_url_name"],
            enterprise_token=enterprise_token,
            display_name=integration.name,
        )
    except Exception as exc:
        logger.error("MDM enterprise creation failed for %s: %s", integration_id, exc, exc_info=True)
        return jsonify({"error": "Could not complete MDM enterprise binding. Check integration credentials and try again."}), 502

    integration.enterprise_id = result.get("name")  # "enterprises/{id}"
    db.session.commit()
    return jsonify({"message": "Enterprise bound", "enterprise_id": integration.enterprise_id}), 200


@mobile_mdm_bp.route("/integrations/<integration_id>/policy", methods=["PUT"])
@jwt_required()
def update_policy(integration_id):
    err = _require_role("admin", "technician")
    if err:
        return err
    integration = db.get_or_404(MdmIntegration, integration_id)
    if not integration.enterprise_id:
        return jsonify({"error": "Integration is not bound to an enterprise yet"}), 400
    data = request.get_json(silent=True) or {}
    policy_name = data.get("policy_name", "default")
    policy_body = data.get("policy") or {}

    try:
        client = integration.get_client()
        client.patch_policy(policy_name, policy_body)
    except Exception as exc:
        logger.error("MDM policy update failed for %s: %s", integration_id, exc, exc_info=True)
        return jsonify({"error": "Could not update MDM policy. Check integration credentials and try again."}), 502

    integration.default_policy_name = policy_name
    db.session.commit()
    return jsonify({"message": "Policy updated", "policy_name": policy_name}), 200


# ─── Client-safe integration discovery ─────────────────────────────────────────

@mobile_mdm_bp.route("/available_integrations", methods=["GET"])
@jwt_required()
def available_integrations():
    """Minimal, secret-free list of bound integrations this caller may enroll
    a device into — staff-wide (customer_id is null) or scoped to their own
    customer. Used by the Client Portal's self-enrollment flow."""
    client_customer_id, err = _client_customer_id_or_error()
    if err:
        return err
    query = MdmIntegration.query.filter(
        MdmIntegration.is_active == True,  # noqa: E712
        MdmIntegration.enterprise_id.isnot(None),
    )
    if client_customer_id:
        query = query.filter(
            db.or_(MdmIntegration.customer_id == client_customer_id, MdmIntegration.customer_id.is_(None))
        )
    integrations = query.all()
    return jsonify([{"id": i.id, "name": i.name, "type": i.type} for i in integrations]), 200


# ─── Enrollment (consent-gated) ────────────────────────────────────────────────

@mobile_mdm_bp.route("/enrollments", methods=["POST"])
@jwt_required()
def create_enrollment():
    claims = get_jwt()
    role = claims.get("role")
    err = _require_role("admin", "technician", "client")
    if err:
        return err
    data = request.get_json(silent=True) or {}

    integration_id = data.get("mdm_integration_id")
    if not integration_id:
        return jsonify({"error": "mdm_integration_id required"}), 400
    integration = db.get_or_404(MdmIntegration, integration_id)
    if not integration.enterprise_id:
        return jsonify({"error": "Integration is not bound to an enterprise yet"}), 400

    client_customer_id, cerr = _client_customer_id_or_error()
    if cerr:
        return cerr

    if role == "client":
        # Consent is an enforced gate, not just UI copy — ownership is always
        # forced to BYOD for self-service customer enrollment, regardless of
        # what the request body says.
        if integration.customer_id not in (None, client_customer_id):
            return jsonify({"error": "Not found"}), 404
        ownership_type = "byod"
        customer_id = client_customer_id
        if not data.get("consent_acknowledged"):
            return jsonify({"error": "consent_acknowledged is required to enroll a device"}), 400
    else:
        ownership_type = data.get("ownership_type", "corporate")
        if ownership_type not in ("byod", "corporate"):
            return jsonify({"error": "ownership_type must be 'byod' or 'corporate'"}), 400
        customer_id = data.get("customer_id") or integration.customer_id
        if ownership_type == "byod" and not data.get("consent_acknowledged"):
            return jsonify({"error": "consent_acknowledged is required for BYOD enrollment"}), 400

    policy_name = integration.default_policy_name or "default"
    allow_personal_usage = ownership_type == "byod"

    try:
        client = integration.get_client()
        token_result = client.create_enrollment_token(
            policy_name=policy_name, ttl_hours=1, allow_personal_usage=allow_personal_usage,
        )
    except Exception as exc:
        logger.error("MDM enrollment token creation failed: %s", exc, exc_info=True)
        return jsonify({"error": "Could not create enrollment token. Check integration credentials and try again."}), 502

    now = datetime.now(timezone.utc)
    enrollment = MobileEnrollment(
        mdm_integration_id=integration.id,
        customer_id=customer_id,
        enrollment_token=token_result.get("value"),
        enrollment_token_expires_at=now + timedelta(hours=1),
        ownership_type=ownership_type,
        status="pending",
        policy_name=policy_name,
        consent_given_by_user_id=get_jwt_identity(),
        consent_given_at=now,
        consent_text_version=CONSENT_TEXT_VERSION,
        consent_ip_address=request.remote_addr,
    )
    db.session.add(enrollment)
    db.session.flush()
    _audit("mdm_consent_recorded", enrollment.id, {
        "ownership_type": ownership_type, "customer_id": customer_id,
        "consent_text_version": CONSENT_TEXT_VERSION,
    })
    _audit("mdm_enrollment_created", enrollment.id, {
        "integration_id": integration.id, "ownership_type": ownership_type,
    })
    db.session.commit()

    return jsonify({
        "enrollment_id": enrollment.id,
        "qr_code_json": token_result.get("qrCode"),
        "enrollment_link": f"https://enterprise.google.com/android/enroll?et={token_result.get('value')}",
        "expires_at": enrollment.enrollment_token_expires_at.isoformat(),
    }), 201


@mobile_mdm_bp.route("/enrollments", methods=["GET"])
@jwt_required()
def list_enrollments():
    client_customer_id, err = _client_customer_id_or_error()
    if err:
        return err
    query = MobileEnrollment.query
    if client_customer_id:
        query = query.filter_by(customer_id=client_customer_id)
    else:
        customer_id = request.args.get("customer_id")
        if customer_id:
            query = query.filter_by(customer_id=customer_id)
    enrollments = query.order_by(MobileEnrollment.created_at.desc()).all()
    return jsonify([e.to_dict() for e in enrollments]), 200


@mobile_mdm_bp.route("/enrollments/<enrollment_id>", methods=["DELETE"])
@jwt_required()
def revoke_enrollment(enrollment_id):
    """BYOD: RELINQUISH_OWNERSHIP (removes only the managed work profile, personal
    side of the phone untouched — this reversibility is what makes BYOD defensible).
    Corporate: full device removal/wipe."""
    enrollment = db.get_or_404(MobileEnrollment, enrollment_id)
    err = _mdm_scope_check(enrollment.customer_id)
    if err:
        return err
    if enrollment.ownership_type == "corporate":
        err = _require_role("admin")
        if err:
            return err
    else:
        err = _require_role("admin", "technician", "client")
        if err:
            return err

    integration = db.session.get(MdmIntegration, enrollment.mdm_integration_id)
    if enrollment.android_enterprise_device_name and integration:
        try:
            client = integration.get_client()
            if enrollment.ownership_type == "byod":
                client.issue_command(enrollment.android_enterprise_device_name, "RELINQUISH_OWNERSHIP")
            else:
                client.delete_device(enrollment.android_enterprise_device_name)
        except Exception as exc:
            logger.error("MDM revoke failed for enrollment %s: %s", enrollment_id, exc, exc_info=True)
            return jsonify({"error": "Could not revoke MDM enrollment. Check integration credentials and try again."}), 502

    enrollment.status = "revoked"
    enrollment.revoked_at = datetime.now(timezone.utc)
    enrollment.revoked_by_user_id = get_jwt_identity()
    _audit("mdm_enrollment_revoked", enrollment.id, {"ownership_type": enrollment.ownership_type})
    db.session.commit()
    return jsonify({"message": "Enrollment revoked"}), 200


# ─── Remote commands ────────────────────────────────────────────────────────────

def _issue_device_command(device_id, command_type, role_allowed, **extra):
    err = _require_role(*role_allowed)
    if err:
        return err
    device = db.get_or_404(Device, device_id)
    err = _mdm_scope_check(device.customer_id)
    if err:
        return err
    enrollment = device.mdm_enrollment
    if not enrollment or enrollment.status != "enrolled" or not enrollment.android_enterprise_device_name:
        return jsonify({"error": "Device is not an enrolled, managed mobile device"}), 400

    claims = get_jwt()
    if claims.get("role") == "client" and command_type.lower() not in _CLIENT_ALLOWED_COMMANDS:
        return jsonify({"error": "Insufficient permissions"}), 403

    integration = db.session.get(MdmIntegration, enrollment.mdm_integration_id)
    try:
        client = integration.get_client()
        client.issue_command(enrollment.android_enterprise_device_name, command_type.upper(), **extra)
    except Exception as exc:
        logger.error("MDM command %s failed for device %s: %s", command_type, device_id, exc, exc_info=True)
        return jsonify({"error": "Could not send command to device. Check integration credentials and try again."}), 502

    _audit(f"mdm_command_{command_type.lower()}", device_id, {
        "enrollment_id": enrollment.id, "command": command_type,
    })
    db.session.commit()
    return jsonify({"message": "Command sent — applies when the device next checks in."}), 202


@mobile_mdm_bp.route("/devices/<device_id>/lock", methods=["POST"])
@jwt_required()
def lock_device(device_id):
    return _issue_device_command(device_id, "LOCK", ("admin", "technician", "client"))


@mobile_mdm_bp.route("/devices/<device_id>/reboot", methods=["POST"])
@jwt_required()
def reboot_mobile_device(device_id):
    return _issue_device_command(device_id, "REBOOT", ("admin", "technician"))


@mobile_mdm_bp.route("/devices/<device_id>/reset_password", methods=["POST"])
@jwt_required()
def reset_password_device(device_id):
    return _issue_device_command(device_id, "RESET_PASSWORD", ("admin", "technician"))


@mobile_mdm_bp.route("/devices/<device_id>/wipe", methods=["POST"])
@jwt_required()
def wipe_device(device_id):
    # Wipe is the most destructive/irreversible action — admin-only, matching the
    # existing admin-only gate on delete_device in devices.py.
    return _issue_device_command(device_id, "WIPE", ("admin",))


@mobile_mdm_bp.route("/devices/<device_id>/start_lost_mode", methods=["POST"])
@jwt_required()
def start_lost_mode(device_id):
    data = request.get_json(silent=True) or {}
    lost_message = {}
    if data.get("message"):
        lost_message["lostMessage"] = {"defaultMessage": data["message"]}
    if data.get("phone_number"):
        lost_message["lostPhoneNumber"] = {"defaultMessage": data["phone_number"]}
    return _issue_device_command(
        device_id, "START_LOST_MODE", ("admin", "technician", "client"), **lost_message
    )


@mobile_mdm_bp.route("/devices/<device_id>/stop_lost_mode", methods=["POST"])
@jwt_required()
def stop_lost_mode(device_id):
    return _issue_device_command(device_id, "STOP_LOST_MODE", ("admin", "technician", "client"))
