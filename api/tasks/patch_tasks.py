"""Patch deployment and auto-approval tasks — Phase 6."""
import logging
from datetime import datetime, timezone
from tasks.celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(name="tasks.patch_tasks.deploy_patches", bind=True, max_retries=3)
def deploy_patches(self, device_id: str, patch_ids: list):
    """Create a ScriptRun to install approved patches on a device via PSWindowsUpdate."""
    from app import create_app
    from extensions import db
    from models.patch import PatchRecord
    from models.script import Script, ScriptRun
    from sqlalchemy.exc import OperationalError

    app = create_app()
    with app.app_context():
        try:
            patches = PatchRecord.query.filter(
                PatchRecord.id.in_(patch_ids),
                PatchRecord.device_id == device_id,
                PatchRecord.status == "approved",
            ).all()

            if not patches:
                logger.info("deploy_patches: no approved patches found for device %s", device_id)
                return

            kb_ids = [p.kb_id for p in patches if p.kb_id]
            names = [p.patch_name for p in patches if not p.kb_id]

            # Build install script — try PSWindowsUpdate first, fall back to wusa
            if kb_ids:
                kb_list = ", ".join(f'"{k}"' for k in kb_ids)
                script_content = (
                    f"$kbs = @({kb_list})\n"
                    "if (Get-Module -ListAvailable -Name PSWindowsUpdate) {\n"
                    "    Import-Module PSWindowsUpdate\n"
                    "    foreach ($kb in $kbs) {\n"
                    "        try {\n"
                    "            Get-WindowsUpdate -KBArticleID $kb -Install -AcceptAll -IgnoreReboot -ErrorAction Stop\n"
                    "            Write-Output \"Installed: $kb\"\n"
                    "        } catch { Write-Output \"Failed $kb: $($_.Exception.Message)\" }\n"
                    "    }\n"
                    "} else {\n"
                    "    foreach ($kb in $kbs) {\n"
                    "        $num = $kb -replace 'KB',''\n"
                    "        wusa /quiet /norestart /kb:$num\n"
                    "        Write-Output \"wusa queued: $kb\"\n"
                    "    }\n"
                    "}\n"
                    "Write-Output \"Patch deployment complete.\""
                )
            else:
                name_list = "; ".join(names[:5])
                script_content = f'Write-Output "No KB IDs available for: {name_list}"'

            # Find or create the transient deploy script record
            deploy_script = Script.query.filter_by(
                name="__deploy_patches_transient__", is_builtin=True
            ).first()
            if not deploy_script:
                deploy_script = Script(
                    name="__deploy_patches_transient__",
                    description="Auto-generated patch deployment script",
                    file_type="ps1",
                    content=script_content,
                    is_builtin=True,
                    os_target="windows",
                    tags=["__builtin_deploy_patches__"],
                )
                db.session.add(deploy_script)
                db.session.flush()
            else:
                deploy_script.content = script_content

            run = ScriptRun(
                script_id=deploy_script.id,
                device_id=device_id,
                timeout_seconds=900,
            )
            db.session.add(run)

            now = datetime.now(timezone.utc)
            for p in patches:
                p.status = "deployed"
                p.deployed_at = now

            db.session.commit()
            logger.info("deploy_patches: queued %d patches for device %s", len(patches), device_id)

        except OperationalError as exc:
            db.session.rollback()
            raise self.retry(exc=exc, countdown=30)
        except Exception:
            db.session.rollback()
            logger.exception("deploy_patches failed for device %s", device_id)
            raise


@celery.task(name="tasks.patch_tasks.sync_patch_status", bind=True, max_retries=3)
def sync_patch_status(self):
    """Auto-approve patches based on PatchPolicy rules."""
    from app import create_app
    from extensions import db
    from models.patch import PatchRecord, PatchPolicy
    from models.device import Device
    from sqlalchemy.exc import OperationalError

    app = create_app()
    with app.app_context():
        try:
            policies = PatchPolicy.query.all()
            approved_count = 0

            for policy in policies:
                query = PatchRecord.query.filter_by(status="pending")
                if policy.customer_id:
                    dev_ids = [
                        d.id for d in Device.query.filter_by(customer_id=policy.customer_id).all()
                    ]
                    if not dev_ids:
                        continue
                    query = query.filter(PatchRecord.device_id.in_(dev_ids))

                excluded = [s.lower() for s in (policy.excluded_software or [])]

                for patch in query.all():
                    if any(ex in patch.patch_name.lower() for ex in excluded):
                        continue

                    should_approve = (
                        (patch.patch_type == "critical" and policy.auto_approve_critical) or
                        (patch.patch_type == "security" and policy.auto_approve_security) or
                        (patch.patch_type == "service_pack" and policy.auto_approve_service_packs) or
                        (patch.patch_type == "driver" and policy.auto_approve_drivers)
                    )
                    if should_approve:
                        patch.status = "approved"
                        approved_count += 1

            db.session.commit()
            logger.info("sync_patch_status: auto-approved %d patches", approved_count)
            return approved_count

        except OperationalError as exc:
            db.session.rollback()
            raise self.retry(exc=exc, countdown=60)
        except Exception:
            db.session.rollback()
            logger.exception("sync_patch_status failed")
            raise
