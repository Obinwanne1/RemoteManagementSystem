"""
Automation profile execution task.
Runs asynchronously so the HTTP request returns immediately.
"""
import logging
from datetime import datetime, timezone
from tasks.celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(name="tasks.automation_tasks.enqueue_profile_run", bind=True, max_retries=3)
def enqueue_profile_run(self, profile_id: str):
    from app import create_app
    from extensions import db
    from models.automation import AutomationProfile, ScheduledTaskRun
    from models.device import Device
    from sqlalchemy.exc import OperationalError

    app = create_app()
    with app.app_context():
        try:
            profile = AutomationProfile.query.get(profile_id)
            if not profile:
                logger.warning("enqueue_profile_run: profile %s not found", profile_id)
                return

            # Resolve target devices
            if profile.device_group_id:
                devices = Device.query.filter_by(
                    group_id=profile.device_group_id, is_online=True
                ).all()
            elif profile.customer_id:
                devices = Device.query.filter_by(
                    customer_id=profile.customer_id, is_online=True
                ).all()
            else:
                devices = Device.query.filter_by(is_online=True).all()

            if not devices:
                logger.info("enqueue_profile_run: no online devices for profile %s", profile_id)
                return

            for device in devices:
                run = ScheduledTaskRun(
                    profile_id=profile_id,
                    device_id=device.id,
                    status="queued",
                )
                db.session.add(run)

            db.session.commit()
            logger.info(
                "enqueue_profile_run: queued %d devices for profile %s",
                len(devices), profile_id,
            )

        except OperationalError as exc:
            db.session.rollback()
            raise self.retry(exc=exc, countdown=30)
        except Exception:
            db.session.rollback()
            logger.exception("enqueue_profile_run failed for profile %s", profile_id)
            raise
