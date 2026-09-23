"""Script/built-in-action execution logic shared by the route and the AI assistant tool executor."""
from flask import request
from extensions import db
from models.script import Script, ScriptRun
from models.device import Device
from models.audit import AuditLog

BUILTIN_ACTIONS = (
    "reboot", "shutdown", "clean_temp", "defrag", "check_disk",
    "restore_point", "clear_browser", "software_rescan",
)


def run_script_service(actor_user_id: str, actor_role: str, actor_customer_id: str,
                        script_id: str, device_ids: list, timeout_seconds: int = 300):
    """Returns ({"queued": n, "run_ids": [...]}, None) or (None, (message, status))."""
    if actor_role not in ("admin", "technician", "superadmin"):
        return None, ("Insufficient permissions", 403)
    script = db.session.get(Script, script_id)
    if not script:
        return None, ("Script not found", 404)
    if not device_ids:
        return None, ("device_ids required", 400)

    cid = actor_customer_id if actor_role == "client" else None
    dq = Device.query.filter(Device.id.in_(device_ids))
    if cid:
        dq = dq.filter_by(customer_id=cid)
    valid_devices = {d.id for d in dq.all()}

    runs = []
    for device_id in device_ids:
        if device_id not in valid_devices:
            continue
        run = ScriptRun(
            script_id=script_id,
            device_id=device_id,
            triggered_by=actor_user_id,
            status="queued",
            timeout_seconds=timeout_seconds,
        )
        db.session.add(run)
        runs.append(run)

    db.session.flush()
    db.session.add(AuditLog(
        user_id=actor_user_id,
        action="script_run",
        resource_type="script",
        resource_id=script_id,
        ip_address=request.remote_addr if request else None,
        payload={"script_name": script.name, "device_count": len(runs), "device_ids": [r.device_id for r in runs]},
    ))
    db.session.commit()
    return {"queued": len(runs), "run_ids": [r.id for r in runs]}, None


def run_builtin_action_service(actor_user_id: str, actor_role: str, actor_customer_id: str,
                                device_ids: list, action: str, timeout_seconds: int = 300):
    """Queue a built-in maintenance action (reboot/shutdown/clean_temp/...) across one or more
    devices. Mirrors routes/devices.py's reboot_device/shutdown_device/queue_device_task, but
    accepts multiple device_ids in one call (the assistant may target several devices at once)."""
    if actor_role not in ("admin", "technician", "superadmin"):
        return None, ("Insufficient permissions", 403)
    if action not in BUILTIN_ACTIONS:
        return None, (f"Unknown action '{action}'. Valid: {list(BUILTIN_ACTIONS)}", 400)
    if not device_ids:
        return None, ("device_ids required", 400)

    from utils.builtin_scripts import get_builtin_script_id
    script_id = get_builtin_script_id(action)
    if not script_id:
        return None, ("Built-in script not found. Restart API to re-sync.", 500)

    cid = actor_customer_id if actor_role == "client" else None
    dq = Device.query.filter(Device.id.in_(device_ids))
    if cid:
        dq = dq.filter_by(customer_id=cid)
    devices_by_id = {d.id: d for d in dq.all()}

    run_ids = []
    skipped = []
    for device_id in device_ids:
        device = devices_by_id.get(device_id)
        if not device:
            skipped.append({"device_id": device_id, "reason": "not found or not accessible"})
            continue
        if action in ("reboot", "shutdown") and not device.is_online:
            skipped.append({"device_id": device_id, "reason": "offline"})
            continue
        run = ScriptRun(
            script_id=script_id,
            device_id=device_id,
            triggered_by=actor_user_id,
            status="queued",
            timeout_seconds=timeout_seconds,
        )
        db.session.add(run)
        db.session.flush()
        run_ids.append(run.id)

    db.session.add(AuditLog(
        user_id=actor_user_id,
        action=f"builtin_action_{action}",
        resource_type="device",
        resource_id=",".join(device_ids)[:36],
        ip_address=request.remote_addr if request else None,
        payload={"action": action, "device_ids": device_ids, "run_ids": run_ids, "skipped": skipped},
    ))
    db.session.commit()
    return {"queued": len(run_ids), "run_ids": run_ids, "skipped": skipped}, None
