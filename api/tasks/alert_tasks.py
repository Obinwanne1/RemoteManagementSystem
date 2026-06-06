"""
Periodic tasks: evaluate alert rules against latest device metrics,
mark devices offline if heartbeat timeout exceeded.
"""
import logging
from datetime import datetime, timezone, timedelta
from tasks.celery_app import celery
from sqlalchemy import func

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

                if not devices:
                    continue

                # Batch-load latest metrics for all devices in one query (eliminates N+1)
                device_ids = [d.id for d in devices]
                max_id_subq = (
                    db.select(func.max(DeviceMetrics.id).label("max_id"))
                    .where(DeviceMetrics.device_id.in_(device_ids))
                    .group_by(DeviceMetrics.device_id)
                    .subquery()
                )
                latest_by_device = {
                    m.device_id: m
                    for m in DeviceMetrics.query.join(
                        max_id_subq, DeviceMetrics.id == max_id_subq.c.max_id
                    ).all()
                }

                for device in devices:
                    latest = latest_by_device.get(device.id)
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
                        last_seen_str = (
                            device.last_seen.strftime("%Y-%m-%d %H:%M UTC")
                            if device.last_seen else "unknown"
                        )
                        alert = Alert(
                            rule_id=offline_rule.id,
                            device_id=device.id,
                            severity="critical",
                            message=f"{device.hostname} has gone offline (last seen: {last_seen_str})",
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


@celery.task(name="tasks.alert_tasks.unlock_expired_accounts", bind=True, max_retries=3)
def unlock_expired_accounts(self):
    """Proactively unlock accounts whose lockout window has expired.

    Runs every 60 seconds. Finds all users where is_locked=True and
    locked_until <= now(), resets their lockout state.
    """
    from app import create_app
    from extensions import db
    from models.user import User
    from sqlalchemy.exc import OperationalError

    app = create_app()
    with app.app_context():
        try:
            now = datetime.now(timezone.utc)
            expired = User.query.filter(
                User.is_locked == True,
                User.locked_until != None,
                User.locked_until <= now,
            ).all()

            for user in expired:
                user.is_locked = False
                user.locked_until = None
                user.failed_login_attempts = 0
                logger.info("Auto-unlocked account: %s (lockout expired)", user.email)

            if expired:
                db.session.commit()
                logger.info("unlock_expired_accounts: unlocked %d account(s)", len(expired))

            return len(expired)

        except OperationalError as exc:
            db.session.rollback()
            raise self.retry(exc=exc, countdown=30)
        except Exception:
            db.session.rollback()
            logger.exception("unlock_expired_accounts failed")
            raise


@celery.task(name="tasks.alert_tasks.deactivate_dormant_accounts", bind=True, max_retries=3)
def deactivate_dormant_accounts(self):
    """Daily: deactivate accounts with no login for 30+ days. Emails user + admins."""
    from app import create_app
    from extensions import db
    from models.user import User
    from sqlalchemy.exc import OperationalError
    from utils.notifications import send_account_deactivated_email, send_dormant_admin_alert

    app = create_app()
    with app.app_context():
        try:
            now = datetime.now(timezone.utc)
            threshold = now - timedelta(days=30)

            dormant = User.query.filter(
                User.is_active == True,
                User.role != "superadmin",
                db.or_(
                    User.last_login < threshold,
                    db.and_(User.last_login == None, User.created_at < threshold),
                ),
            ).all()

            deactivated = []
            for user in dormant:
                user.is_active = False
                send_account_deactivated_email(user.email)
                deactivated.append(user.email)
                logger.info("Auto-deactivated dormant account: %s", user.email)

            if deactivated:
                admin_emails = [
                    u.email for u in User.query.filter(
                        User.role == "admin", User.is_active == True
                    ).all()
                ]
                send_dormant_admin_alert(deactivated, admin_emails)
                db.session.commit()
                logger.info("deactivate_dormant_accounts: deactivated %d account(s)", len(deactivated))

            return len(deactivated)

        except OperationalError as exc:
            db.session.rollback()
            raise self.retry(exc=exc, countdown=60)
        except Exception:
            db.session.rollback()
            logger.exception("deactivate_dormant_accounts failed")
            raise


@celery.task(name="tasks.alert_tasks.check_password_expiry", bind=True, max_retries=3)
def check_password_expiry(self):
    """Daily: send 7-day expiry warning to users whose password is 83-89 days old."""
    from app import create_app
    from extensions import db
    from models.user import User
    from sqlalchemy.exc import OperationalError
    from utils.notifications import send_password_expiry_warning

    app = create_app()
    with app.app_context():
        try:
            now = datetime.now(timezone.utc)
            warning_floor = now - timedelta(days=89)   # 89 days old → 1 day left
            warning_ceil  = now - timedelta(days=83)   # 83 days old → 7 days left

            warning_users = User.query.filter(
                User.is_active == True,
                User.role != "superadmin",
                User.password_changed_at != None,
                User.password_changed_at <= warning_ceil,
                User.password_changed_at >= warning_floor,
                User.must_change_password == False,
            ).all()

            for user in warning_users:
                days_left = 90 - (now - user.password_changed_at).days
                send_password_expiry_warning(user.email, max(1, days_left))
                logger.info("Password expiry warning sent: %s (%d days left)", user.email, days_left)

            return len(warning_users)

        except OperationalError as exc:
            db.session.rollback()
            raise self.retry(exc=exc, countdown=60)
        except Exception:
            db.session.rollback()
            logger.exception("check_password_expiry failed")
            raise
