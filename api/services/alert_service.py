"""Alert acknowledge/resolve logic shared by the route and the AI assistant tool executor.

SECURITY FIX: the previous routes/alerts.py acknowledge_alert/resolve_alert had NO role
check and NO tenant-scope check at all — any authenticated user of any role could act on
any customer's alert, and nothing was audit-logged. This module adds both, mirroring the
_require_role / client-scope-check pattern used in routes/devices.py.
"""
from datetime import datetime, timezone

from flask import request
from extensions import db
from models.alert import Alert
from models.audit import AuditLog
from utils.cache import cache_delete_pattern


def _check_access(actor_role: str):
    """Alerts are staff-only (viewer/client excluded), matching _ROLE_CAPABILITIES —
    clients "cannot access monitoring, devices, alerts". Admin/technician are fleet-wide
    by design in this codebase (see scripts.py::run_script — only role=="client" gets
    customer_id scoping), so no per-alert tenant check is needed once role passes."""
    if actor_role not in ("admin", "technician", "superadmin"):
        return ("Insufficient permissions", 403)
    return None


def acknowledge_alert_service(actor_user_id: str, actor_role: str, actor_customer_id: str, alert_id: str):
    err = _check_access(actor_role)
    if err:
        return None, err
    alert = db.session.get(Alert, alert_id)
    if not alert:
        return None, ("Alert not found", 404)

    alert.status = "acknowledged"
    alert.acknowledged_by = actor_user_id
    alert.acknowledged_at = datetime.now(timezone.utc)
    db.session.add(AuditLog(
        user_id=actor_user_id,
        action="alert_acknowledge",
        resource_type="alert",
        resource_id=alert.id,
        ip_address=request.remote_addr if request else None,
        payload={"device_id": alert.device_id, "severity": alert.severity},
    ))
    db.session.commit()
    cache_delete_pattern("rmm:alerts:list:*")
    return alert.to_dict(), None


def resolve_alert_service(actor_user_id: str, actor_role: str, actor_customer_id: str, alert_id: str,
                           resolution_note: str = None):
    err = _check_access(actor_role)
    if err:
        return None, err
    alert = db.session.get(Alert, alert_id)
    if not alert:
        return None, ("Alert not found", 404)

    alert.status = "resolved"
    alert.resolved_at = datetime.now(timezone.utc)
    db.session.add(AuditLog(
        user_id=actor_user_id,
        action="alert_resolve",
        resource_type="alert",
        resource_id=alert.id,
        ip_address=request.remote_addr if request else None,
        payload={"device_id": alert.device_id, "severity": alert.severity, "note": resolution_note},
    ))
    db.session.commit()
    cache_delete_pattern("rmm:alerts:list:*")
    return alert.to_dict(), None
