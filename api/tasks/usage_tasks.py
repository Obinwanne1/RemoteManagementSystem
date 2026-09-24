"""Usage-monitoring rollup + spike-detection tasks (sibling to anomaly_tasks.py)."""
import logging
from datetime import datetime, timezone, timedelta
from tasks.celery_app import celery

logger = logging.getLogger(__name__)

from tasks._app_singleton import get_app as _get_app


@celery.task(name="tasks.usage_tasks.persist_hourly_usage_rollup", bind=True, max_retries=2)
def persist_hourly_usage_rollup(self):
    """Reads the previous completed hour's Redis usage-counter hash and upserts it
    into the durable ApiUsageHourly table, so history survives past the Redis TTL."""
    from extensions import db
    from models.usage import ApiUsageHourly
    from utils.cache import _get_client
    from utils.usage_tracker import _hourly_redis_key
    from sqlalchemy.exc import OperationalError

    with _get_app().app_context():
        hour_start = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(
            minute=0, second=0, microsecond=0
        )
        key = _hourly_redis_key(hour_start)

        try:
            client = _get_client()
            raw = client.hgetall(key)
        except Exception as exc:
            logger.warning("persist_hourly_usage_rollup: Redis read failed: %s", exc)
            return {"rows": 0}

        if not raw:
            return {"rows": 0}

        # raw fields look like "{endpoint}|{method}|count" -> "N"
        buckets = {}
        for field, value in raw.items():
            try:
                endpoint_method, kind = field.rsplit("|", 1)
                endpoint, method = endpoint_method.rsplit("|", 1)
            except ValueError:
                continue
            b = buckets.setdefault((endpoint, method), {"count": 0, "errors": 0, "latency_sum": 0})
            if kind == "count":
                b["count"] = int(value)
            elif kind == "errors":
                b["errors"] = int(value)
            elif kind == "latency_sum":
                b["latency_sum"] = int(value)

        try:
            rows_written = 0
            for (endpoint, method), stats in buckets.items():
                existing = ApiUsageHourly.query.filter_by(
                    bucket_start=hour_start, endpoint=endpoint, method=method
                ).first()
                if existing:
                    existing.request_count = stats["count"]
                    existing.error_count = stats["errors"]
                    existing.total_latency_ms = stats["latency_sum"]
                else:
                    db.session.add(ApiUsageHourly(
                        bucket_start=hour_start, endpoint=endpoint, method=method,
                        request_count=stats["count"], error_count=stats["errors"],
                        total_latency_ms=stats["latency_sum"],
                    ))
                rows_written += 1
            db.session.commit()
            logger.info("persist_hourly_usage_rollup: wrote %d row(s) for hour %s", rows_written, hour_start)
            return {"rows": rows_written}
        except OperationalError as exc:
            db.session.rollback()
            raise self.retry(exc=exc, countdown=60)
        except Exception:
            db.session.rollback()
            logger.exception("persist_hourly_usage_rollup failed")
            raise


@celery.task(name="tasks.usage_tasks.detect_usage_anomaly")
def detect_usage_anomaly():
    """If enabled, fires a real email/webhook notification for any service whose
    last completed hour exceeds its trailing-7-day baseline by spike_multiplier."""
    from models.usage import UsageAlertConfig
    from utils.usage_tracker import compute_anomalies

    with _get_app().app_context():
        cfg = UsageAlertConfig.get_or_create()
        if not cfg.is_enabled:
            return {"checked": False}

        anomalies = compute_anomalies(cfg.spike_multiplier)
        if not anomalies:
            return {"checked": True, "anomalies": 0}

        channels = cfg.notification_channels or {}
        for a in anomalies:
            rule_name = f"Usage Spike: {a['service']}"
            message = (
                f"{a['service']} usage in the last hour was {a['current_hour_count']} "
                f"({a['multiplier']}x the 7-day average of {a['baseline_avg']})."
            )
            try:
                emails = channels.get("email", [])
                if emails:
                    from utils.notifications import send_alert_notification
                    send_alert_notification(rule_name, "System / API Usage", message, emails)
                if any(channels.get(k) for k in ("slack", "teams", "webhook")):
                    from utils.webhook import dispatch_alert_webhooks
                    dispatch_alert_webhooks(channels, rule_name, "System / API Usage", message, "warning")
            except Exception:
                logger.exception("detect_usage_anomaly: notification dispatch failed for %s", a["service"])

        logger.info("detect_usage_anomaly: fired %d notification(s)", len(anomalies))
        return {"checked": True, "anomalies": len(anomalies)}
