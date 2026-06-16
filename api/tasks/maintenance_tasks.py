"""Maintenance tasks: automation profile execution and data retention pruning."""
import logging
from datetime import datetime, timezone, timedelta
from tasks.celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(name="tasks.maintenance_tasks.execute_profile")
def execute_profile(profile_id: str, run_id: str):
    """Execute a scheduled automation profile run on a device."""
    pass


@celery.task(name="tasks.maintenance_tasks.prune_old_data")
def prune_old_data():
    """Delete stale time-series and log data to prevent unbounded disk growth.

    Retention policy:
      - device_metrics : 90 days  (high-volume, ~1 row/min per device)
      - audit_log      : 365 days (compliance, lower volume)
      - script_run     : 180 days (execution history)
    """
    from app import create_app
    from extensions import db
    from models.device import DeviceMetrics
    from models.audit import AuditLog
    from models.script import ScriptRun

    app = create_app()
    with app.app_context():
        now = datetime.now(timezone.utc)

        metrics_cutoff = now - timedelta(days=90)
        audit_cutoff = now - timedelta(days=365)
        script_cutoff = now - timedelta(days=180)

        metrics_deleted = DeviceMetrics.query.filter(
            DeviceMetrics.collected_at < metrics_cutoff
        ).delete(synchronize_session=False)

        audit_deleted = AuditLog.query.filter(
            AuditLog.created_at < audit_cutoff
        ).delete(synchronize_session=False)

        script_deleted = ScriptRun.query.filter(
            ScriptRun.triggered_at < script_cutoff
        ).delete(synchronize_session=False)

        db.session.commit()

        logger.info(
            "Data pruning complete: metrics=%d audit=%d scripts=%d",
            metrics_deleted, audit_deleted, script_deleted,
        )
        return {
            "metrics_deleted": metrics_deleted,
            "audit_deleted": audit_deleted,
            "scripts_deleted": script_deleted,
        }
