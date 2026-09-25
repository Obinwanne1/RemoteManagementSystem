"""Tests for tasks/anomaly_tasks.py::detect_metric_anomalies (audits/testing_audit.md
Finding C3 — was 0% covered). No Redis lock in this file, so no mocking needed
there; the task is called directly via the established tasks._app_singleton
priming pattern (see test_alert_tasks.py / test_usage.py)."""
import uuid
from datetime import datetime, timezone, timedelta

import pytest

import tasks._app_singleton as app_singleton
import tasks.anomaly_tasks as anomaly_tasks
from conftest import delete_user

# tasks/anomaly_tasks.py:154 (`recent_rows = [r for r in rows if r.collected_at
# >= cutoff_1h]`) compares a DB-read DeviceMetrics.collected_at against a fresh
# datetime.now(timezone.utc). Under SQLite (this suite's DB), DateTime(timezone=True)
# columns round-trip as naive datetimes (SQLite has no native tz-aware timestamp
# type), so the comparison raises `TypeError: can't compare offset-naive and
# offset-aware datetimes` for any device with enough history to reach that line.
# Verified real — reproduced directly, not a test-writing mistake. Would not
# reproduce against Postgres (production), which preserves tz-awareness. Not
# fixed here (out of this fork's scope — see the accompanying report); the fix
# would be normalizing with `r.collected_at.replace(tzinfo=timezone.utc)` (or
# equivalent) before the comparison at line 154 (and the identical shape at 117-118).
_SQLITE_NAIVE_DATETIME_BUG = (
    "anomaly_tasks.py compares DB-read collected_at against datetime.now(timezone.utc); "
    "SQLite returns naive datetimes for DateTime(timezone=True) columns, causing "
    "TypeError: can't compare offset-naive and offset-aware datetimes. Real bug, "
    "not reproducible against Postgres. See test file docstring/comment for detail."
)


def _make_customer(app):
    from extensions import db
    from models.customer import Customer
    c = Customer(name=f"AnomCo-{uuid.uuid4().hex[:6]}", slug=f"an-{uuid.uuid4().hex[:6]}", is_active=True)
    db.session.add(c)
    db.session.commit()
    return c


def _make_device(app, customer_id):
    from extensions import db
    from models.device import Device
    d = Device(
        hostname=f"host-{uuid.uuid4().hex[:6]}", customer_id=customer_id,
        platform="windows", os_name="Windows 11", ip_address="10.0.0.1", is_online=True,
    )
    db.session.add(d)
    db.session.commit()
    return d


def _seed_metrics_history(app, device_id, *, baseline_value, baseline_count, spike_value=None, spike_count=0):
    """20 baseline samples spread 2h-23h ago (steady baseline_value +/- jitter),
    then `spike_count` samples in the last 1h at spike_value (or baseline_value
    again, for the "no spike" case)."""
    from extensions import db
    from models.device import DeviceMetrics
    now = datetime.now(timezone.utc)
    jitter = [0, 1, -1, 0, 2, -2, 0, 1, -1, 0, 0, 1, -1, 0, 2, -2, 0, 1, -1, 0]
    for i in range(baseline_count):
        ts = now - timedelta(hours=23 - (i * 20 // max(baseline_count, 1)))
        db.session.add(DeviceMetrics(
            device_id=device_id, collected_at=ts,
            cpu_pct=baseline_value + jitter[i % len(jitter)],
        ))
    for i in range(spike_count):
        ts = now - timedelta(minutes=50 - i * 10)
        db.session.add(DeviceMetrics(
            device_id=device_id, collected_at=ts,
            cpu_pct=spike_value if spike_value is not None else baseline_value,
        ))
    db.session.commit()


def _cleanup(app, *, device_ids=(), customer_id=None, user_id=None):
    from extensions import db
    from models.device import Device, DeviceMetrics
    from models.customer import Customer
    from models.alert import Alert
    for did in device_ids:
        DeviceMetrics.query.filter_by(device_id=did).delete()
        Alert.query.filter_by(device_id=did).delete()
        Device.query.filter_by(id=did).delete()
    if customer_id:
        Customer.query.filter_by(id=customer_id).delete()
    db.session.commit()
    if user_id:
        delete_user(app, user_id)


def _run_detect(app):
    app_singleton._app = app
    anomaly_tasks.detect_metric_anomalies()


class TestDetectMetricAnomalies:
    @pytest.mark.xfail(reason=_SQLITE_NAIVE_DATETIME_BUG, strict=True)
    def test_fires_alert_on_real_spike(self, app):
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        _seed_metrics_history(app, dev.id, baseline_value=20, baseline_count=20, spike_value=90, spike_count=3)
        try:
            _run_detect(app)
            from models.alert import Alert
            alert = Alert.query.filter(
                Alert.device_id == dev.id, Alert.message.like("Anomaly: CPU%"),
            ).first()
            assert alert is not None
            assert alert.status == "open"
            assert alert.severity == "warning"
        finally:
            _cleanup(app, device_ids=[dev.id], customer_id=cust.id)

    @pytest.mark.xfail(reason=_SQLITE_NAIVE_DATETIME_BUG, strict=True)
    def test_no_alert_when_metrics_are_stable(self, app):
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        _seed_metrics_history(app, dev.id, baseline_value=20, baseline_count=20, spike_count=3)
        try:
            _run_detect(app)
            from models.alert import Alert
            assert Alert.query.filter_by(device_id=dev.id).first() is None
        finally:
            _cleanup(app, device_ids=[dev.id], customer_id=cust.id)

    def test_skips_device_with_insufficient_samples(self, app):
        """MIN_SAMPLES=10 — fewer rows than that must not crash or alert."""
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        _seed_metrics_history(app, dev.id, baseline_value=20, baseline_count=5)
        try:
            _run_detect(app)  # must not raise
            from models.alert import Alert
            assert Alert.query.filter_by(device_id=dev.id).first() is None
        finally:
            _cleanup(app, device_ids=[dev.id], customer_id=cust.id)

    @pytest.mark.xfail(reason=_SQLITE_NAIVE_DATETIME_BUG, strict=True)
    def test_second_spike_updates_existing_alert_instead_of_duplicating(self, app):
        """_fire_anomaly_alert dedups on the message-prefix match (Alert has no
        rule_id for anomaly-detected alerts) — two consecutive spiky runs must
        not create two Alert rows."""
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        _seed_metrics_history(app, dev.id, baseline_value=20, baseline_count=20, spike_value=90, spike_count=3)
        try:
            _run_detect(app)
            _run_detect(app)
            from models.alert import Alert
            alerts = Alert.query.filter(
                Alert.device_id == dev.id, Alert.message.like("Anomaly: CPU%"),
            ).all()
            assert len(alerts) == 1
        finally:
            _cleanup(app, device_ids=[dev.id], customer_id=cust.id)

    def test_offline_device_is_excluded(self, app):
        from extensions import db
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        dev.is_online = False
        db.session.commit()
        _seed_metrics_history(app, dev.id, baseline_value=20, baseline_count=20, spike_value=90, spike_count=3)
        try:
            _run_detect(app)
            from models.alert import Alert
            assert Alert.query.filter_by(device_id=dev.id).first() is None
        finally:
            _cleanup(app, device_ids=[dev.id], customer_id=cust.id)
