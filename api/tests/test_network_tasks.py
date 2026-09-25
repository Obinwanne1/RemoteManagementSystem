"""Tests for tasks/network_tasks.py (audits/testing_audit.md Finding C3).
Covers the pure detection-heuristic functions, _upsert_agentless_host's DB
logic, and the ping_agentless_devices beat task. `_run_scan`/run_network_scan`
(the full ICMP+port sweep across a subnet) is NOT covered here — it would
need mocking dozens of socket calls across an IP range for proportionally
little additional confidence over the already-tested building blocks
(_guess_platform, _probe_platform's port logic, _upsert_agentless_host)."""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import tasks._app_singleton as app_singleton
import tasks.network_tasks as network_tasks
from conftest import delete_user


class TestGuessPlatform:
    def test_apple_vendor_is_ios(self):
        assert network_tasks._guess_platform("Apple, Inc.") == ("ios", "mobile")

    def test_samsung_vendor_is_android(self):
        assert network_tasks._guess_platform("Samsung Electronics") == ("android", "mobile")

    def test_unknown_vendor(self):
        assert network_tasks._guess_platform("Some Random Corp") == ("unknown", "unknown")


class TestGuessPlatformFromHostname:
    def test_iphone_hostname(self):
        assert network_tasks._guess_platform_from_hostname("Johns-iPhone.local") == ("ios", "mobile")

    def test_samsung_model_hostname(self):
        assert network_tasks._guess_platform_from_hostname("Galaxy-S21-Ultra") == ("android", "mobile")

    def test_no_hostname(self):
        assert network_tasks._guess_platform_from_hostname("") == ("unknown", "unknown")

    def test_router_hostname_is_unknown(self):
        assert network_tasks._guess_platform_from_hostname("fritz.box") == ("unknown", "unknown")


class TestProbePlatform:
    def test_windows_requires_two_ports(self):
        """Regression test for the false-positive fix documented in CLAUDE.md —
        a single open SMB port (445) must NOT be enough to call it Windows.
        _probe_platform() does `import socket` locally, so the real `socket`
        module (not a network_tasks.socket attribute) is what needs patching —
        it's the same module object either way via sys.modules."""
        import contextlib

        def fake_create_connection(addr, timeout=0.5):
            port = addr[1]
            if port == 445:  # only SMB open, like a router/NAS
                return contextlib.nullcontext()
            raise OSError("refused")

        with patch("socket.create_connection", side_effect=fake_create_connection):
            assert network_tasks._probe_platform("10.0.0.1") == ("unknown", "unknown")

    def test_windows_with_two_ports_open(self):
        import contextlib

        def fake_create_connection(addr, timeout=0.5):
            port = addr[1]
            if port in (445, 139):
                return contextlib.nullcontext()
            raise OSError("refused")

        with patch("socket.create_connection", side_effect=fake_create_connection):
            assert network_tasks._probe_platform("10.0.0.1") == ("windows", "desktop")


def _make_agentless_device(app, ip, *, last_seen=None, is_online=True):
    from extensions import db
    from models.device import Device
    d = Device(
        hostname=f"host-{uuid.uuid4().hex[:6]}", ip_address=ip, is_agentless=True,
        is_online=is_online, platform="unknown", last_seen=last_seen,
    )
    db.session.add(d)
    db.session.commit()
    return d


def _cleanup_devices(device_ids):
    from extensions import db
    from models.device import Device
    Device.query.filter(Device.id.in_(device_ids)).delete(synchronize_session=False)
    db.session.commit()


class TestUpsertAgentlessHost:
    def test_creates_new_device(self, app):
        # A hardcoded placeholder MAC here previously collided with an
        # identical placeholder in tests/test_agents.py (both used
        # "AA:BB:CC:DD:EE:FF") — the session-scoped shared test DB (see
        # conftest.py::app's docstring) means every test needs a genuinely
        # unique identifier, not just a locally-unique one.
        mac = f"AA:BB:CC:{uuid.uuid4().hex[:2]}:{uuid.uuid4().hex[2:4]}:{uuid.uuid4().hex[4:6]}".upper()
        with app.app_context():
            dev = None
            try:
                result = network_tasks._upsert_agentless_host(
                    "10.0.0.50", mac, "Apple, Inc.", "ios", "mobile",
                )
                assert result == "created"
                from models.device import Device
                dev = Device.query.filter_by(mac_address=mac).first()
                assert dev is not None
                assert dev.is_agentless is True
                assert dev.platform == "ios"
            finally:
                if dev:
                    _cleanup_devices([dev.id])

    def test_never_demotes_agent_managed_device(self, app):
        with app.app_context():
            from extensions import db
            from models.device import Device
            agent_device = Device(hostname="REAL-PC", ip_address="10.0.0.60", is_agentless=False)
            db.session.add(agent_device)
            db.session.commit()
            try:
                result = network_tasks._upsert_agentless_host(
                    "10.0.0.60", None, "Unknown", "windows", "desktop",
                )
                assert result == "skipped"
                db.session.refresh(agent_device)
                assert agent_device.is_agentless is False
            finally:
                _cleanup_devices([agent_device.id])

    def test_updates_existing_agentless_device_by_mac(self, app):
        with app.app_context():
            dev = _make_agentless_device(app, "10.0.0.70")
            from extensions import db
            from models.device import Device
            dev.mac_address = "11:22:33:44:55:66"
            db.session.commit()
            try:
                result = network_tasks._upsert_agentless_host(
                    "10.0.0.71", "11:22:33:44:55:66", "Samsung", "android", "mobile",
                )
                assert result == "updated"
                db.session.refresh(dev)
                assert dev.ip_address == "10.0.0.71"
            finally:
                _cleanup_devices([dev.id])


class TestPingAgentlessDevices:
    def test_online_device_stays_online(self, app):
        app_singleton._app = app
        with app.app_context():
            dev_id = _make_agentless_device(app, "10.0.0.80", last_seen=datetime.now(timezone.utc)).id
        try:
            with patch("tasks.network_tasks._ping_host", return_value=True):
                network_tasks.ping_agentless_devices()
            with app.app_context():
                from extensions import db
                from models.device import Device
                fresh = db.session.get(Device, dev_id)
                assert fresh.is_online is True
                assert fresh.status == "healthy"
        finally:
            with app.app_context():
                _cleanup_devices([dev_id])

    def test_recently_unreachable_device_stays_online_within_grace_period(self, app):
        """600s grace period before marking offline — a single missed ping
        shouldn't flip status immediately."""
        app_singleton._app = app
        with app.app_context():
            dev_id = _make_agentless_device(
                app, "10.0.0.81", last_seen=datetime.now(timezone.utc) - timedelta(seconds=60),
            ).id
        try:
            with patch("tasks.network_tasks._ping_host", return_value=False):
                network_tasks.ping_agentless_devices()
            with app.app_context():
                from extensions import db
                from models.device import Device
                fresh = db.session.get(Device, dev_id)
                assert fresh.is_online is True
        finally:
            with app.app_context():
                _cleanup_devices([dev_id])

    def test_unreachable_past_grace_period_marked_offline(self, app):
        app_singleton._app = app
        with app.app_context():
            dev_id = _make_agentless_device(
                app, "10.0.0.82", last_seen=datetime.now(timezone.utc) - timedelta(seconds=700),
            ).id
        try:
            with patch("tasks.network_tasks._ping_host", return_value=False):
                network_tasks.ping_agentless_devices()
            with app.app_context():
                from extensions import db
                from models.device import Device
                fresh = db.session.get(Device, dev_id)
                assert fresh.is_online is False
                assert fresh.status == "offline"
        finally:
            with app.app_context():
                _cleanup_devices([dev_id])
