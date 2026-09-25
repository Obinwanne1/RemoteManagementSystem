"""Tests for tasks/automation_tasks.py::enqueue_profile_run (audits/testing_audit.md
Finding C3 — was 0% covered). No Redis lock in this file."""
import uuid

import tasks._app_singleton as app_singleton
import tasks.automation_tasks as automation_tasks
from conftest import delete_user


def _make_customer(app):
    from extensions import db
    from models.customer import Customer
    c = Customer(name=f"AutoCo-{uuid.uuid4().hex[:6]}", slug=f"at-{uuid.uuid4().hex[:6]}", is_active=True)
    db.session.add(c)
    db.session.commit()
    return c


def _make_device(app, customer_id, *, is_online=True):
    from extensions import db
    from models.device import Device
    d = Device(
        hostname=f"host-{uuid.uuid4().hex[:6]}", customer_id=customer_id,
        platform="windows", os_name="Windows 11", ip_address="10.0.0.1", is_online=is_online,
    )
    db.session.add(d)
    db.session.commit()
    return d


def _make_profile(app, customer_id, **kwargs):
    from extensions import db
    from models.automation import AutomationProfile
    defaults = dict(
        name=f"Profile-{uuid.uuid4().hex[:6]}", customer_id=customer_id,
        is_active=True, maintenance_config={}, disk_config={}, scripts=[],
    )
    defaults.update(kwargs)
    p = AutomationProfile(**defaults)
    db.session.add(p)
    db.session.commit()
    return p


def _make_script(app, name, *, is_builtin=False, tags=None):
    from extensions import db
    from models.script import Script
    s = Script(
        name=name, file_type="ps1", content="Write-Output 'ok'",
        is_builtin=is_builtin, tags=tags or [],
    )
    db.session.add(s)
    db.session.commit()
    return s


def _cleanup(app, *, device_ids=(), customer_id=None, profile_ids=(), script_ids=(), user_id=None):
    from extensions import db
    from models.device import Device
    from models.customer import Customer
    from models.automation import AutomationProfile, ScheduledTaskRun
    from models.script import Script, ScriptRun
    for pid in profile_ids:
        ScheduledTaskRun.query.filter_by(profile_id=pid).delete()
        AutomationProfile.query.filter_by(id=pid).delete()
    for did in device_ids:
        ScriptRun.query.filter_by(device_id=did).delete()
        Device.query.filter_by(id=did).delete()
    for sid in script_ids:
        Script.query.filter_by(id=sid).delete()
    if customer_id:
        Customer.query.filter_by(id=customer_id).delete()
    db.session.commit()
    if user_id:
        delete_user(app, user_id)


def _run_enqueue(app, profile_id):
    app_singleton._app = app
    automation_tasks.enqueue_profile_run(profile_id)


class TestEnqueueProfileRun:
    def test_queues_run_for_online_devices_in_customer(self, app):
        cust = _make_customer(app)
        dev = _make_device(app, cust.id, is_online=True)
        profile = _make_profile(app, cust.id)
        try:
            _run_enqueue(app, profile.id)
            from models.automation import ScheduledTaskRun
            from extensions import db
            run = ScheduledTaskRun.query.filter_by(profile_id=profile.id, device_id=dev.id).first()
            assert run is not None
            assert run.status == "queued"
            db.session.refresh(profile)
            assert profile.last_run_at is not None
        finally:
            _cleanup(app, device_ids=[dev.id], customer_id=cust.id, profile_ids=[profile.id])

    def test_offline_devices_are_excluded(self, app):
        cust = _make_customer(app)
        dev = _make_device(app, cust.id, is_online=False)
        profile = _make_profile(app, cust.id)
        try:
            _run_enqueue(app, profile.id)
            from models.automation import ScheduledTaskRun
            assert ScheduledTaskRun.query.filter_by(profile_id=profile.id, device_id=dev.id).first() is None
        finally:
            _cleanup(app, device_ids=[dev.id], customer_id=cust.id, profile_ids=[profile.id])

    def test_missing_profile_returns_quietly(self, app):
        app_singleton._app = app
        automation_tasks.enqueue_profile_run("not-a-real-profile-id")  # must not raise

    def test_dispatches_builtin_script_for_configured_maintenance_task(self, app):
        """profile.maintenance_config={'delete_temp': True} should create a
        ScriptRun pointing at the builtin 'Clean Temp Files' script."""
        from extensions import db
        cust = _make_customer(app)
        dev = _make_device(app, cust.id, is_online=True)
        builtin = _make_script(app, "Clean Temp Files", is_builtin=True, tags=["__builtin_clean_temp__"])
        profile = _make_profile(app, cust.id, maintenance_config={"delete_temp": True})
        try:
            _run_enqueue(app, profile.id)
            from models.script import ScriptRun
            run = ScriptRun.query.filter_by(device_id=dev.id, script_id=builtin.id).first()
            assert run is not None
        finally:
            _cleanup(app, device_ids=[dev.id], customer_id=cust.id, profile_ids=[profile.id], script_ids=[builtin.id])

    def test_dispatches_explicitly_configured_scripts(self, app):
        cust = _make_customer(app)
        dev = _make_device(app, cust.id, is_online=True)
        custom_script = _make_script(app, "My Custom Script")
        profile = _make_profile(app, cust.id, scripts=[custom_script.id])
        try:
            _run_enqueue(app, profile.id)
            from models.script import ScriptRun
            run = ScriptRun.query.filter_by(device_id=dev.id, script_id=custom_script.id).first()
            assert run is not None
        finally:
            _cleanup(app, device_ids=[dev.id], customer_id=cust.id, profile_ids=[profile.id], script_ids=[custom_script.id])

    def test_no_devices_does_not_error(self, app):
        cust = _make_customer(app)
        profile = _make_profile(app, cust.id)
        try:
            _run_enqueue(app, profile.id)  # no devices at all — must not raise
        finally:
            _cleanup(app, customer_id=cust.id, profile_ids=[profile.id])
