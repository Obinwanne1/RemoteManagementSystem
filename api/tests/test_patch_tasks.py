"""Tests for tasks/patch_tasks.py::sync_patch_status and deploy_patches
(audits/testing_audit.md Finding C3, 105 statements, 0% coverage before this
file). Pure DB logic — no external I/O, nothing to mock here."""
import uuid

import tasks._app_singleton as app_singleton
import tasks.patch_tasks as patch_tasks


def _make_customer(app):
    from extensions import db
    from models.customer import Customer
    c = Customer(name=f"PatchCo-{uuid.uuid4().hex[:6]}", slug=f"pc-{uuid.uuid4().hex[:6]}", is_active=True)
    db.session.add(c)
    db.session.commit()
    return c


def _make_device(app, customer_id):
    from extensions import db
    from models.device import Device
    d = Device(hostname=f"host-{uuid.uuid4().hex[:6]}", customer_id=customer_id, platform="windows")
    db.session.add(d)
    db.session.commit()
    return d


def _make_patch(app, device_id, **kwargs):
    from extensions import db
    from models.patch import PatchRecord
    defaults = dict(
        patch_name=f"KB-{uuid.uuid4().hex[:6]}", kb_id="KB1234567",
        patch_type="critical", status="pending",
    )
    defaults.update(kwargs)
    p = PatchRecord(device_id=device_id, **defaults)
    db.session.add(p)
    db.session.commit()
    return p


def _make_policy(app, **kwargs):
    from extensions import db
    from models.patch import PatchPolicy
    defaults = dict(
        name=f"Policy-{uuid.uuid4().hex[:6]}",
        auto_approve_critical=True, auto_approve_security=True,
        auto_approve_service_packs=False, auto_approve_drivers=False,
        excluded_software=[],
    )
    defaults.update(kwargs)
    pol = PatchPolicy(**defaults)
    db.session.add(pol)
    db.session.commit()
    return pol


def _cleanup(app, *, device_ids=(), customer_id=None, policy_ids=(), script_ids=()):
    from extensions import db
    from models.device import Device
    from models.customer import Customer
    from models.patch import PatchRecord, PatchPolicy
    from models.script import Script, ScriptRun
    for did in device_ids:
        PatchRecord.query.filter_by(device_id=did).delete()
        ScriptRun.query.filter_by(device_id=did).delete()
        Device.query.filter_by(id=did).delete()
    for pid in policy_ids:
        PatchPolicy.query.filter_by(id=pid).delete()
    for sid in script_ids:
        Script.query.filter_by(id=sid).delete()
    if customer_id:
        Customer.query.filter_by(id=customer_id).delete()
    db.session.commit()


class TestSyncPatchStatus:
    def test_auto_approves_critical_patch_under_global_policy(self, app):
        app_singleton._app = app
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        patch = _make_patch(app, dev.id, patch_type="critical", status="pending")
        policy = _make_policy(app, auto_approve_critical=True)
        try:
            count = patch_tasks.sync_patch_status()
            assert count >= 1
            from extensions import db
            db.session.refresh(patch)
            assert patch.status == "approved"
        finally:
            _cleanup(app, device_ids=[dev.id], customer_id=cust.id, policy_ids=[policy.id])

    def test_does_not_approve_when_type_not_enabled(self, app):
        app_singleton._app = app
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        patch = _make_patch(app, dev.id, patch_type="driver", status="pending")
        policy = _make_policy(app, auto_approve_drivers=False)
        try:
            patch_tasks.sync_patch_status()
            from extensions import db
            db.session.refresh(patch)
            assert patch.status == "pending"
        finally:
            _cleanup(app, device_ids=[dev.id], customer_id=cust.id, policy_ids=[policy.id])

    def test_respects_excluded_software(self, app):
        app_singleton._app = app
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        patch = _make_patch(app, dev.id, patch_name="Zoom Client Update", patch_type="critical", status="pending")
        policy = _make_policy(app, auto_approve_critical=True, excluded_software=["zoom"])
        try:
            patch_tasks.sync_patch_status()
            from extensions import db
            db.session.refresh(patch)
            assert patch.status == "pending"
        finally:
            _cleanup(app, device_ids=[dev.id], customer_id=cust.id, policy_ids=[policy.id])

    def test_customer_scoped_policy_ignores_other_customers_devices(self, app):
        app_singleton._app = app
        cust_a = _make_customer(app)
        cust_b = _make_customer(app)
        dev_a = _make_device(app, cust_a.id)
        dev_b = _make_device(app, cust_b.id)
        patch_a = _make_patch(app, dev_a.id, patch_type="critical", status="pending")
        patch_b = _make_patch(app, dev_b.id, patch_type="critical", status="pending")
        policy = _make_policy(app, customer_id=cust_a.id, auto_approve_critical=True)
        try:
            patch_tasks.sync_patch_status()
            from extensions import db
            db.session.refresh(patch_a)
            db.session.refresh(patch_b)
            assert patch_a.status == "approved"
            assert patch_b.status == "pending"  # not covered by cust_a's policy
        finally:
            _cleanup(app, device_ids=[dev_a.id, dev_b.id], customer_id=cust_a.id, policy_ids=[policy.id])
            from extensions import db
            from models.customer import Customer
            Customer.query.filter_by(id=cust_b.id).delete()
            db.session.commit()

    def test_skips_policy_outside_maintenance_window(self, app):
        app_singleton._app = app
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        patch = _make_patch(app, dev.id, patch_type="critical", status="pending")
        # A window for a day that's never "today" relative to itself is impossible to
        # construct deterministically without mocking time; instead use an internally
        # inconsistent day name that _within_maintenance_window's day_map.get() maps to
        # None, which — per the function's own contract — returns True (unrestricted).
        # This test instead pins the *documented* skip path: a specific day 6 days from
        # now is never "today", so the policy should be skipped deterministically.
        from datetime import datetime, timezone, timedelta
        not_today = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%A").lower()
        policy = _make_policy(
            app, auto_approve_critical=True,
            maintenance_window={"day": not_today, "time": "02:00", "duration_hours": 1},
        )
        try:
            patch_tasks.sync_patch_status()
            from extensions import db
            db.session.refresh(patch)
            assert patch.status == "pending"  # window is for a different day — skipped
        finally:
            _cleanup(app, device_ids=[dev.id], customer_id=cust.id, policy_ids=[policy.id])


class TestDeployPatches:
    def test_queues_script_run_for_approved_patches(self, app):
        app_singleton._app = app
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        patch = _make_patch(app, dev.id, kb_id="KB5001234", status="approved")
        try:
            patch_tasks.deploy_patches(dev.id, [patch.id])
            from extensions import db
            from models.script import ScriptRun
            db.session.refresh(patch)
            assert patch.status == "deployed"
            assert patch.deployed_at is not None
            run = ScriptRun.query.filter_by(device_id=dev.id).first()
            assert run is not None
            assert "KB5001234" in run.script.content
        finally:
            script = None
            from models.script import ScriptRun
            run = ScriptRun.query.filter_by(device_id=dev.id).first()
            script_ids = [run.script_id] if run else []
            _cleanup(app, device_ids=[dev.id], customer_id=cust.id, script_ids=script_ids)

    def test_no_op_when_no_approved_patches(self, app):
        app_singleton._app = app
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        patch = _make_patch(app, dev.id, status="pending")  # not approved
        try:
            patch_tasks.deploy_patches(dev.id, [patch.id])
            from models.script import ScriptRun
            assert ScriptRun.query.filter_by(device_id=dev.id).first() is None
        finally:
            _cleanup(app, device_ids=[dev.id], customer_id=cust.id)
