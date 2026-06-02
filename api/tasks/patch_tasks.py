"""Patch deployment tasks — Phase 6 implementation."""
from tasks.celery_app import celery


@celery.task(name="tasks.patch_tasks.deploy_patches")
def deploy_patches(device_id: str, patch_ids: list):
    """Queue patch installation on agent via task queue."""
    # Phase 6: implement patch deployment dispatch
    pass


@celery.task(name="tasks.patch_tasks.sync_patch_status")
def sync_patch_status():
    """Periodically sync Windows Update status from all online agents."""
    # Phase 6: implement
    pass
