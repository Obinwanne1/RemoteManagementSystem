"""Tests for tasks/snmp_tasks.py::poll_snmp_devices (audits/testing_audit.md
Finding C3 — 0% coverage before this file). _snmp_get is always mocked — it
does real UDP network I/O via pysnmp, which must never run in a test."""
import uuid
from unittest.mock import patch

import tasks._app_singleton as app_singleton
import tasks.snmp_tasks as snmp_tasks


def _make_device(app, *, device_type="ups", is_online=True, metadata_=None, ip_address="10.0.0.5"):
    from extensions import db
    from models.device import Device
    d = Device(
        hostname=f"snmp-{uuid.uuid4().hex[:6]}", device_type=device_type,
        is_online=is_online, ip_address=ip_address, metadata_=metadata_,
    )
    db.session.add(d)
    db.session.commit()
    return d


def _cleanup(app, device_ids):
    from extensions import db
    from models.device import Device, DeviceSensorReading
    for did in device_ids:
        DeviceSensorReading.query.filter_by(device_id=did).delete()
        Device.query.filter_by(id=did).delete()
    db.session.commit()


def _run_poll(app):
    app_singleton._app = app
    return snmp_tasks.poll_snmp_devices()


class TestPollSnmpDevices:
    def test_returns_zero_when_no_candidate_devices(self, app):
        app_singleton._app = app
        assert snmp_tasks.poll_snmp_devices() == 0

    def test_skips_snmp_capable_device_with_no_community_string(self, app):
        dev = _make_device(app, device_type="ups", metadata_=None)
        try:
            assert _run_poll(app) == 0
        finally:
            _cleanup(app, [dev.id])

    def test_skips_offline_device(self, app):
        dev = _make_device(app, device_type="ups", is_online=False, metadata_={"snmp_community": "public"})
        try:
            assert _run_poll(app) == 0
        finally:
            _cleanup(app, [dev.id])

    def test_ups_device_records_battery_and_load_readings(self, app):
        dev = _make_device(app, device_type="ups", metadata_={"snmp_community": "public"})
        try:
            # _snmp_get(ip, community, oid) -> (value, error); battery OID first, then load OID
            with patch("tasks.snmp_tasks._snmp_get", side_effect=[(87, None), (42, None)]):
                inserted = _run_poll(app)
            assert inserted == 2
            from models.device import DeviceSensorReading
            readings = DeviceSensorReading.query.filter_by(device_id=dev.id).all()
            types = {r.sensor_type: r.value for r in readings}
            assert types["ups_battery"] == 87.0
            assert types["ups_load"] == 42.0
        finally:
            _cleanup(app, [dev.id])

    def test_switch_device_records_interface_octet_readings(self, app):
        dev = _make_device(app, device_type="switch", metadata_={"snmp_community": "public"})
        try:
            with patch("tasks.snmp_tasks._snmp_get", side_effect=[(1000, None), (2000, None)]):
                inserted = _run_poll(app)
            assert inserted == 2
        finally:
            _cleanup(app, [dev.id])

    def test_pysnmp_not_installed_short_circuits_ups_poll(self, app):
        """Regression guard: a missing pysnmp install must degrade to a clean
        0-reading return, not raise and break the beat schedule."""
        dev = _make_device(app, device_type="ups", metadata_={"snmp_community": "public"})
        try:
            with patch("tasks.snmp_tasks._snmp_get", return_value=(None, "pysnmp_not_installed")):
                inserted = _run_poll(app)
            assert inserted == 0
        finally:
            _cleanup(app, [dev.id])

    def test_device_with_no_ip_is_skipped(self, app):
        dev = _make_device(app, device_type="ups", metadata_={"snmp_community": "public"}, ip_address=None)
        try:
            with patch("tasks.snmp_tasks._snmp_get") as mock_get:
                inserted = _run_poll(app)
            mock_get.assert_not_called()
            assert inserted == 0
        finally:
            _cleanup(app, [dev.id])
