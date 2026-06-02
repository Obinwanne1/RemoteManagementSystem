"""Script dispatch tasks — Phase 4 implementation."""
from tasks.celery_app import celery


@celery.task(name="tasks.script_tasks.dispatch_script_run")
def dispatch_script_run(run_id: str):
    """Signal agent to pick up a queued script run."""
    # Agent polls via GET /agents/{id}/tasks — no push needed for Phase 4
    pass
