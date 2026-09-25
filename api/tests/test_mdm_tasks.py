"""Tests for tasks/mdm_tasks.py (audits/testing_audit.md Finding C3, 81
statements, 0% coverage before this file). Real Android Management API calls
are never made — MdmIntegration.get_client() is always mocked."""
import uuid
from unittest.mock import MagicMock, patch

import tasks._app_singleton as app_singleton
import tasks.mdm_tasks as mdm_tasks


def _make_customer(app):
    from extensions import db
    from models.customer import Customer
    c = Customer(name=f"MdmCo-{uuid.uuid4().hex[:6]}", slug=f"mdc-{uuid.uuid4().hex[:6]}", is_active=True)
    db.session.add(c)
    db.session.commit()
    return c


def _make_integration(app, **kwargs):
    from extensions import db
    from models.mdm_integration import MdmIntegration
    defaults = dict(
        name=f"MDM-{uuid.uuid4().hex[:6]}", type="android",
        enterprise_id="enterprises/LC00abc123", is_active=True,
    )
    defaults.update(kwargs)
    integ = MdmIntegration(**defaults)
    db.session.add(integ)
    db.session.commit()
    return integ


def _make_pending_enrollment(app, integration_id, customer_id, token=None):
    from extensions import db
    from models.mdm_integration import MobileEnrollment
    e = MobileEnrollment(
        mdm_integration_id=integration_id, customer_id=customer_id,
        status="pending", ownership_type="byod",
        enrollment_token=token or f"tok-{uuid.uuid4().hex[:8]}",
    )
    db.session.add(e)
    db.session.commit()
    return e


def _cleanup(app, *, integration_ids=(), customer_ids=(), device_ids=()):
    from extensions import db
    from models.mdm_integration import MdmIntegration, MobileEnrollment
    from models.customer import Customer
    from models.device import Device
    for iid in integration_ids:
        MobileEnrollment.query.filter_by(mdm_integration_id=iid).delete()
        MdmIntegration.query.filter_by(id=iid).delete()
    for did in device_ids:
        Device.query.filter_by(id=did).delete()
    for cid in customer_ids:
        Customer.query.filter_by(id=cid).delete()
    db.session.commit()


def _run_sync(app, integration_id, fake_client):
    app_singleton._app = app
    with patch("models.mdm_integration.MdmIntegration.get_client", return_value=fake_client):
        mdm_tasks.sync_mdm_integration(integration_id)


class TestSyncAllMdmIntegrations:
    def test_dispatches_one_task_per_active_bound_integration(self, app):
        app_singleton._app = app
        integ = _make_integration(app)
        try:
            with patch("tasks.mdm_tasks.sync_mdm_integration.delay") as mock_delay:
                mdm_tasks.sync_all_mdm_integrations()
                mock_delay.assert_called_once_with(integ.id)
        finally:
            _cleanup(app, integration_ids=[integ.id])

    def test_skips_integration_without_enterprise_id(self, app):
        """Not yet bound to a Google enterprise — nothing to sync."""
        app_singleton._app = app
        integ = _make_integration(app, enterprise_id=None)
        try:
            with patch("tasks.mdm_tasks.sync_mdm_integration.delay") as mock_delay:
                mdm_tasks.sync_all_mdm_integrations()
                mock_delay.assert_not_called()
        finally:
            _cleanup(app, integration_ids=[integ.id])

    def test_skips_inactive_integration(self, app):
        app_singleton._app = app
        integ = _make_integration(app, is_active=False)
        try:
            with patch("tasks.mdm_tasks.sync_mdm_integration.delay") as mock_delay:
                mdm_tasks.sync_all_mdm_integrations()
                mock_delay.assert_not_called()
        finally:
            _cleanup(app, integration_ids=[integ.id])


class TestSyncMdmIntegration:
    def test_matches_new_remote_device_to_pending_enrollment(self, app):
        cust = _make_customer(app)
        integ = _make_integration(app)
        enrollment = _make_pending_enrollment(app, integ.id, cust.id)
        try:
            fake_client = MagicMock()
            fake_client.list_devices.return_value = [{
                "name": "enterprises/LC00abc123/devices/dev1",
                "hardwareInfo": {"model": "Pixel 8", "brand": "Google"},
                "softwareInfo": {"androidVersion": "14"},
                "policyCompliant": True,
            }]
            _run_sync(app, integ.id, fake_client)

            from extensions import db
            db.session.refresh(enrollment)
            assert enrollment.status == "enrolled"
            assert enrollment.android_enterprise_device_name == "enterprises/LC00abc123/devices/dev1"
            assert enrollment.device_id is not None
            assert enrollment.policy_compliant is True

            from models.device import Device
            device = db.session.get(Device, enrollment.device_id)
            assert device is not None
            assert device.platform == "android"
            assert device.is_agentless is True
            assert device.vendor == "Google"
        finally:
            dev_id = enrollment.device_id
            _cleanup(app, integration_ids=[integ.id], customer_ids=[cust.id],
                     device_ids=[dev_id] if dev_id else [])

    def test_updates_existing_enrolled_device_compliance(self, app):
        cust = _make_customer(app)
        integ = _make_integration(app)
        enrollment = _make_pending_enrollment(app, integ.id, cust.id)
        try:
            fake_client = MagicMock()
            device_payload = {
                "name": "enterprises/LC00abc123/devices/dev2",
                "hardwareInfo": {"model": "Pixel 8", "brand": "Google"},
                "softwareInfo": {"androidVersion": "14"},
                "policyCompliant": True,
            }
            fake_client.list_devices.return_value = [device_payload]
            _run_sync(app, integ.id, fake_client)  # first sync — creates + enrolls

            device_payload["policyCompliant"] = False
            device_payload["nonComplianceDetails"] = [{"reason": "app not installed"}]
            fake_client.list_devices.return_value = [device_payload]
            _run_sync(app, integ.id, fake_client)  # second sync — same device, now non-compliant

            from extensions import db
            db.session.refresh(enrollment)
            assert enrollment.policy_compliant is False
            assert enrollment.non_compliance_details is not None
        finally:
            dev_id = enrollment.device_id
            _cleanup(app, integration_ids=[integ.id], customer_ids=[cust.id],
                     device_ids=[dev_id] if dev_id else [])

    def test_no_op_for_inactive_integration(self, app):
        integ = _make_integration(app, is_active=False)
        try:
            fake_client = MagicMock()
            _run_sync(app, integ.id, fake_client)
            fake_client.list_devices.assert_not_called()
        finally:
            _cleanup(app, integration_ids=[integ.id])


class TestCircuitBreaker:
    def test_increments_consecutive_failures_on_error(self, app):
        integ = _make_integration(app)
        try:
            fake_client = MagicMock()
            fake_client.list_devices.side_effect = RuntimeError("token revoked")
            app_singleton._app = app
            with patch("models.mdm_integration.MdmIntegration.get_client", return_value=fake_client):
                try:
                    mdm_tasks.sync_mdm_integration(integ.id)
                except Exception:
                    pass

            from extensions import db
            db.session.refresh(integ)
            assert integ.consecutive_failures == 1
            assert integ.sync_error is not None
            assert integ.is_active is True
        finally:
            _cleanup(app, integration_ids=[integ.id])

    def test_disables_integration_after_max_consecutive_failures(self, app):
        integ = _make_integration(app, consecutive_failures=9)
        try:
            fake_client = MagicMock()
            fake_client.list_devices.side_effect = RuntimeError("token revoked")
            app_singleton._app = app
            with patch("models.mdm_integration.MdmIntegration.get_client", return_value=fake_client):
                try:
                    mdm_tasks.sync_mdm_integration(integ.id)
                except Exception:
                    pass

            from extensions import db
            db.session.refresh(integ)
            assert integ.consecutive_failures == 10
            assert integ.is_active is False
        finally:
            _cleanup(app, integration_ids=[integ.id])
