"""
Periodic tasks: evaluate alert rules against latest device metrics,
mark devices offline if heartbeat timeout exceeded.
"""
import logging
from datetime import datetime, timezone, timedelta
from tasks.celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(name="tasks.alert_tasks.evaluate_all_rules", bind=True, max_retries=3)
def evaluate_all_rules(self):
    from app import create_app
    from extensions import db
    from models.alert import AlertRule, Alert
    from models.device import Device, DeviceMetrics
    from sqlalchemy.exc import OperationalError

    app = create_app()
    with app.app_context():
        try:
            rules = AlertRule.query.filter_by(is_active=True).all()
            now = datetime.now(timezone.utc)

            for rule in rules:
                # Get relevant devices
                if rule.device_group_id:
                    devices = Device.query.filter_by(group_id=rule.device_group_id, is_online=True).all()
                elif rule.customer_id:
                    devices = Device.query.filter_by(customer_id=rule.customer_id, is_online=True).all()
                else:
                    devices = Device.query.filter_by(is_online=True).all()

                for device in devices:
                    latest = DeviceMetrics.query.filter_by(device_id=device.id).order_by(
                        DeviceMetrics.collected_at.desc()
                    ).first()
                    if not latest:
                        continue

                    metric_val = _get_metric_value(latest, rule.metric)
                    if metric_val is None:
                        continue

                    triggered = _evaluate(metric_val, rule.operator, rule.threshold)
                    if not triggered:
                        continue

                    # Check cooldown — don't fire if already open or recent
                    cooldown_since = now - timedelta(minutes=rule.cooldown_minutes)
                    existing = Alert.query.filter(
                        Alert.rule_id == rule.id,
                        Alert.device_id == device.id,
                        Alert.status.in_(["open", "acknowledged"]),
                        Alert.triggered_at >= cooldown_since,
                    ).first()
                    if existing:
                        continue

                    # Create alert
                    alert = Alert(
                        rule_id=rule.id,
                        device_id=device.id,
                        severity=rule.severity,
                        message=f"{rule.name}: {rule.metric} is {metric_val:.1f} (threshold {rule.threshold})",
                    )
                    db.session.add(alert)

                    # Auto-create ticket if configured
                    if rule.auto_create_ticket:
                        from models.ticket import Ticket
                        ticket = Ticket(
                            title=f"[AUTO] {rule.name} on {device.hostname}",
                            description=alert.message,
                            customer_id=device.customer_id,
                            device_id=device.id,
                            priority="critical" if rule.severity == "critical" else "high",
                            source="alert",
                        )
                        db.session.add(ticket)

                    # Email notifications
                    channels = rule.notification_channels or {}
                    emails = channels.get("email", [])
                    if emails:
                        from utils.notifications import send_alert_notification
                        send_alert_notification(rule.name, device.hostname, alert.message, emails)

            db.session.commit()

        except OperationalError as exc:
            db.session.rollback()
            raise self.retry(exc=exc, countdown=30)
        except Exception:
            db.session.rollback()
            logger.exception("evaluate_all_rules failed")
            raise


@celery.task(name="tasks.alert_tasks.mark_offline_devices", bind=True, max_retries=3)
def mark_offline_devices(self):
    from app import create_app
    from extensions import db
    from models.device import Device
    from models.alert import AlertRule, Alert
    from sqlalchemy.exc import OperationalError

    app = create_app()
    with app.app_context():
        try:
            threshold = datetime.now(timezone.utc) - timedelta(minutes=3)
            stale_devices = Device.query.filter(
                Device.is_online == True,
                Device.last_seen < threshold,
            ).all()

            # Load offline rule once, not inside the loop
            offline_rule = AlertRule.query.filter_by(metric="offline", is_active=True).first()

            for device in stale_devices:
                device.is_online = False
                device.status = "offline"

                if offline_rule:
                    existing = Alert.query.filter_by(
                        device_id=device.id,
                        status="open",
                        rule_id=offline_rule.id,
                    ).first()
                    if not existing:
                        alert = Alert(
                            rule_id=offline_rule.id,
                            device_id=device.id,
                            severity="critical",
                            message=f"{device.hostname} has gone offline",
                        )
                        db.session.add(alert)

            db.session.commit()
            return len(stale_devices)

        except OperationalError as exc:
            db.session.rollback()
            raise self.retry(exc=exc, countdown=30)
        except Exception:
            db.session.rollback()
            logger.exception("mark_offline_devices failed")
            raise


def _get_metric_value(metrics, metric_name: str):
    mapping = {
        "cpu": metrics.cpu_pct,
        "ram": metrics.ram_pct,
        "disk": metrics.disk_pct,
        "battery": metrics.battery_pct,
    }
    return mapping.get(metric_name)


def _evaluate(value, operator: str, threshold: float) -> bool:
    if threshold is None:
        return False
    ops = {
        "gt": value > threshold,
        "gte": value >= threshold,
        "lt": value < threshold,
        "lte": value <= threshold,
        "eq": abs(value - threshold) < 0.01,
    }
    return ops.get(operator, False)
