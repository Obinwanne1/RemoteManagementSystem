import hashlib
import uuid
import secrets
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token

from extensions import db, limiter
from models.device import Device, DeviceMetrics, InstalledSoftware
from models.audit import AgentToken
from models.customer import Customer

agents_bp = Blueprint("agents", __name__)

OFFLINE_THRESHOLD_SECONDS = 180  # 3 minutes without heartbeat = offline


def _get_device_by_token(device_id: str):
    """Validate agent token from Authorization header. Returns device or None."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:]
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    agent_token = AgentToken.query.filter_by(
        device_id=device_id,
        token_hash=token_hash,
        is_revoked=False,
    ).first()
    if not agent_token:
        return None

    agent_token.last_used_at = datetime.now(timezone.utc)
    db.session.add(agent_token)
    return Device.query.get(device_id)


@agents_bp.route("/register", methods=["POST"])
@limiter.limit("10 per minute")
def register():
    """Agent first-time registration. Returns device_id + agent_token."""
    data = request.get_json(silent=True) or {}

    # Validate org registration token
    org_token = data.get("org_token", "")
    if not secrets.compare_digest(org_token, current_app.config["ORG_REGISTRATION_TOKEN"]):
        return jsonify({"error": "Invalid org token"}), 403

    # Find or create device by hardware fingerprint
    hostname = data.get("hostname", "").strip()
    mac_address = data.get("mac_address", "").strip()
    serial = data.get("serial_number", "").strip()

    if not hostname:
        return jsonify({"error": "hostname required"}), 400

    fingerprint = hashlib.sha256(
        f"{hostname}|{mac_address}|{serial}".encode("utf-8")
    ).hexdigest()

    # Check if device already registered by fingerprint
    existing = Device.query.filter_by(hardware_fingerprint=fingerprint).first()
    if existing:
        # Re-registration: revoke old tokens, issue new one
        AgentToken.query.filter_by(device_id=existing.id, is_revoked=False).update(
            {"is_revoked": True}
        )
        device = existing
    else:
        # Look up customer via org token (first customer for now, extend later)
        customer = Customer.query.filter_by(is_active=True).first()
        if not customer:
            return jsonify({"error": "No active customer found. Create a customer first."}), 400

        device = Device(
            customer_id=customer.id,
            hostname=hostname,
            platform=data.get("platform", "windows"),
            hardware_fingerprint=fingerprint,
        )
        db.session.add(device)
        db.session.flush()  # Get device.id

    # Update device info from registration payload
    device.hostname = hostname
    device.os_name = data.get("os_name")
    device.os_version = data.get("os_version")
    device.os_build = data.get("os_build")
    device.architecture = data.get("architecture")
    device.cpu_model = data.get("cpu_model")
    device.cpu_cores = data.get("cpu_cores")
    device.ram_gb = data.get("ram_gb")
    device.serial_number = serial
    device.mac_address = mac_address
    device.ip_address = request.remote_addr
    device.agent_version = data.get("agent_version", "1.0.0")
    device.last_seen = datetime.now(timezone.utc)
    device.is_online = True
    device.status = "healthy"

    # Issue new agent token
    raw_token = str(uuid.uuid4()) + secrets.token_hex(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    agent_token = AgentToken(
        device_id=device.id,
        token_hash=token_hash,
    )
    db.session.add(agent_token)
    db.session.commit()

    return jsonify({
        "device_id": device.id,
        "agent_token": raw_token,
        "message": "Registered successfully",
    }), 201


@agents_bp.route("/<device_id>/heartbeat", methods=["POST"])
def heartbeat(device_id):
    """Receive metrics payload from agent. Updates device status."""
    device = _get_device_by_token(device_id)
    if not device:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    now = datetime.now(timezone.utc)

    # Update device online status
    device.last_seen = now
    device.is_online = True
    device.ip_address = request.remote_addr
    if data.get("agent_version"):
        device.agent_version = data["agent_version"]

    # Determine device status from metrics
    cpu = data.get("cpu_pct", 0)
    ram = data.get("ram_pct", 0)
    disk = data.get("disk_pct", 0)
    if cpu > 90 or ram > 90 or disk > 90:
        device.status = "critical"
    elif cpu > 75 or ram > 75 or disk > 80:
        device.status = "warning"
    else:
        device.status = "healthy"

    # Store metrics snapshot
    metrics = DeviceMetrics(
        device_id=device.id,
        collected_at=now,
        cpu_pct=cpu,
        ram_pct=ram,
        ram_used_gb=data.get("ram_used_gb"),
        disk_pct=disk,
        disk_used_gb=data.get("disk_used_gb"),
        disk_total_gb=data.get("disk_total_gb"),
        network_bytes_sent=data.get("network_bytes_sent"),
        network_bytes_recv=data.get("network_bytes_recv"),
        battery_pct=data.get("battery_pct"),
        battery_plugged=data.get("battery_plugged"),
        uptime_seconds=data.get("uptime_seconds"),
        top_processes=data.get("top_processes"),
        disks=data.get("disks"),
    )
    db.session.add(metrics)
    db.session.commit()

    return jsonify({"status": "ok", "server_time": now.isoformat()}), 200


@agents_bp.route("/<device_id>/tasks", methods=["GET"])
def get_tasks(device_id):
    """Return pending tasks for this device."""
    device = _get_device_by_token(device_id)
    if not device:
        return jsonify({"error": "Unauthorized"}), 401

    # Import here to avoid circular imports
    from models.script import ScriptRun, Script
    from models.automation import ScheduledTaskRun

    tasks = []

    # Pending script runs
    pending_scripts = ScriptRun.query.filter_by(
        device_id=device_id, status="queued"
    ).all()
    # Batch-fetch all needed scripts in one query (eliminates N+1)
    script_ids = {run.script_id for run in pending_scripts}
    scripts_by_id = {}
    if script_ids:
        scripts_by_id = {
            s.id: s for s in Script.query.filter(Script.id.in_(script_ids)).all()
        }
    for run in pending_scripts:
        script = scripts_by_id.get(run.script_id)
        if script:
            tasks.append({
                "task_id": run.id,
                "type": "run_script",
                "payload": {
                    "script_id": script.id,
                    "file_type": script.file_type,
                    "content": script.content,
                    "timeout_seconds": run.timeout_seconds,
                },
            })
            run.status = "running"
            run.started_at = datetime.now(timezone.utc)

    db.session.commit()
    return jsonify({"tasks": tasks}), 200


@agents_bp.route("/<device_id>/task_result", methods=["POST"])
def task_result(device_id):
    """Agent posts completed task result."""
    device = _get_device_by_token(device_id)
    if not device:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    task_id = data.get("task_id")
    task_type = data.get("type")

    if task_type == "run_script":
        from models.script import ScriptRun
        run = ScriptRun.query.get(task_id)
        if run and run.device_id == device_id:
            run.exit_code = data.get("exit_code")
            run.stdout = (data.get("stdout") or "")[:65536]  # 64KB cap
            run.stderr = (data.get("stderr") or "")[:65536]
            run.completed_at = datetime.now(timezone.utc)
            run.status = "success" if data.get("exit_code") == 0 else "failed"
            db.session.commit()

    return jsonify({"status": "ok"}), 200


@agents_bp.route("/<device_id>/patches", methods=["PUT"])
def update_patches(device_id):
    """Agent reports pending Windows Update patches."""
    device = _get_device_by_token(device_id)
    if not device:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    patch_list = data.get("patches", [])

    from models.patch import PatchRecord

    # Build set of existing pending patch names to avoid duplicates
    existing_names = {
        p.patch_name
        for p in PatchRecord.query.filter_by(device_id=device_id, status="pending").all()
    }

    added = 0
    for item in patch_list[:500]:
        name = (item.get("name") or "")[:500]
        if not name or name in existing_names:
            continue
        patch = PatchRecord(
            device_id=device_id,
            patch_name=name,
            kb_id=item.get("kb_id"),
            patch_type=item.get("patch_type", "feature"),
            source="wu",
        )
        db.session.add(patch)
        existing_names.add(name)
        added += 1

    db.session.commit()
    return jsonify({"status": "ok", "added": added}), 200


@agents_bp.route("/<device_id>/software", methods=["PUT"])
def update_software(device_id):
    """Agent posts full installed software list (replaces previous)."""
    device = _get_device_by_token(device_id)
    if not device:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    software_list = data.get("software", [])

    # Delete old entries and replace
    InstalledSoftware.query.filter_by(device_id=device_id).delete()
    now = datetime.now(timezone.utc)
    for item in software_list[:2000]:  # cap at 2000 entries
        sw = InstalledSoftware(
            device_id=device_id,
            name=str(item.get("name", ""))[:500],
            version=str(item.get("version", ""))[:255] if item.get("version") else None,
            publisher=str(item.get("publisher", ""))[:255] if item.get("publisher") else None,
            install_date=item.get("install_date"),
            source=item.get("source", "registry"),
            last_seen=now,
        )
        db.session.add(sw)

    db.session.commit()
    return jsonify({"status": "ok", "count": len(software_list)}), 200
