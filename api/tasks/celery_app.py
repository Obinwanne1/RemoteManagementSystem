import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()


def make_celery(app=None):
    celery = Celery(
        "rmm",
        broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
        backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
        include=[
            "tasks.alert_tasks",
            "tasks.patch_tasks",
            "tasks.script_tasks",
            "tasks.maintenance_tasks",
            "tasks.report_tasks",
            "tasks.automation_tasks",
        ],
    )

    celery.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        worker_pool="solo",  # Required on Windows
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        task_default_retry_delay=60,
        task_max_retries=3,
        worker_prefetch_multiplier=1,
        beat_schedule={
            "evaluate-alert-rules-every-minute": {
                "task": "tasks.alert_tasks.evaluate_all_rules",
                "schedule": 60.0,
            },
            "mark-offline-devices-every-3-min": {
                "task": "tasks.alert_tasks.mark_offline_devices",
                "schedule": 180.0,
            },
        },
    )

    if app is not None:
        class ContextTask(celery.Task):
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)

        celery.Task = ContextTask

    return celery


# Standalone celery instance for worker startup
celery = make_celery()
