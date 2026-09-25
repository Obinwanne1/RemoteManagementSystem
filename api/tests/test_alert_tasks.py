"""Tests for tasks/alert_tasks.py::evaluate_all_rules — the highest-value
untested file in api/tasks/ (audits/testing_audit.md Finding C3, 243
statements, 0% coverage before this file). Regression coverage for the
"alert storm fix" documented in CLAUDE.md (open_alert_map/resolved_alert_map
split preventing re-fire within a cooldown window).

Redis is mocked (not just for isolation — this session also has a real
Celery beat running evaluate_all_rules every 60s against the live stack, per
audits/testing_audit.md's own note about environment-dependent Redis
flakiness; a real _get_redis() here could collide with that lock)."""
import uuid
from unittest.mock import MagicMock, patch

import tasks._app_singleton as app_singleton
import tasks.alert_tasks as alert_tasks
from conftest import delete_user


def _make_customer(app):
    from extensions import db
    from models.customer import Customer
    c = Customer(name=f"AlertCo-{uuid.uuid4().hex[:6]}", slug=f"ac-{uuid.uuid4().hex[:6]}", is_active=True)
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


def _make_metrics(app, device_id, cpu_pct):
    from extensions import db
    from models.device import DeviceMetrics
    m = DeviceMetrics(device_id=device_id, cpu_pct=cpu_pct)
    db.session.add(m)
    db.session.commit()
    return m


def _make_rule(app, **kwargs):
    from extensions import db
    from models.alert import AlertRule
    defaults = dict(
        name=f"Rule-{uuid.uuid4().hex[:6]}", metric="cpu", operator="gt",
        threshold=90.0, severity="critical", cooldown_minutes=15,
        notification_channels={}, is_active=True,
    )
    defaults.update(kwargs)
    r = AlertRule(**defaults)
    db.session.add(r)
    db.session.commit()
    return r


def _cleanup(app, *, device_ids=(), customer_id=None, rule_ids=(), user_id=None):
    from extensions import db
    from models.device import Device, DeviceMetrics
    from models.customer import Customer
    from models.alert import Alert, AlertRule
    for did in device_ids:
        DeviceMetrics.query.filter_by(device_id=did).delete()
        Alert.query.filter_by(device_id=did).delete()
        Device.query.filter_by(id=did).delete()
    for rid in rule_ids:
        AlertRule.query.filter_by(id=rid).delete()
    if customer_id:
        Customer.query.filter_by(id=customer_id).delete()
    db.session.commit()
    if user_id:
        delete_user(app, user_id)


def _run_evaluate_all_rules(app):
    """Runs the real task body with a mocked Redis lock (always acquires)."""
    app_singleton._app = app
    mock_redis = MagicMock()
    mock_redis.set.return_value = True  # lock acquired
    with patch("tasks.alert_tasks._get_redis", return_value=mock_redis):
        alert_tasks.evaluate_all_rules()


class TestEvaluateAllRules:
    def test_fires_alert_when_threshold_crossed(self, app):
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        _make_metrics(app, dev.id, cpu_pct=95.0)
        rule = _make_rule(app, metric="cpu", operator="gt", threshold=90.0)
        try:
            _run_evaluate_all_rules(app)
            from models.alert import Alert
            alert = Alert.query.filter_by(rule_id=rule.id, device_id=dev.id).first()
            assert alert is not None
            assert alert.status == "open"
            assert alert.severity == "critical"
        finally:
            _cleanup(app, device_ids=[dev.id], customer_id=cust.id, rule_ids=[rule.id])

    def test_no_alert_when_below_threshold(self, app):
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        _make_metrics(app, dev.id, cpu_pct=10.0)
        rule = _make_rule(app, metric="cpu", operator="gt", threshold=90.0)
        try:
            _run_evaluate_all_rules(app)
            from models.alert import Alert
            assert Alert.query.filter_by(rule_id=rule.id, device_id=dev.id).first() is None
        finally:
            _cleanup(app, device_ids=[dev.id], customer_id=cust.id, rule_ids=[rule.id])

    def test_does_not_storm_when_alert_already_open(self, app):
        """Regression test: a device that stays above threshold across two
        evaluation runs must not get a second Alert row for the same rule."""
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        _make_metrics(app, dev.id, cpu_pct=95.0)
        rule = _make_rule(app, metric="cpu", operator="gt", threshold=90.0)
        try:
            _run_evaluate_all_rules(app)
            _run_evaluate_all_rules(app)  # second run, still above threshold
            from models.alert import Alert
            alerts = Alert.query.filter_by(rule_id=rule.id, device_id=dev.id).all()
            assert len(alerts) == 1
        finally:
            _cleanup(app, device_ids=[dev.id], customer_id=cust.id, rule_ids=[rule.id])

    def test_auto_resolves_when_metric_drops_back_below_threshold(self, app):
        """Regression test for the 'alert storm fix' in CLAUDE.md — an open
        alert must auto-resolve once the metric recovers, not stay open forever."""
        from extensions import db
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        _make_metrics(app, dev.id, cpu_pct=95.0)
        rule = _make_rule(app, metric="cpu", operator="gt", threshold=90.0)
        try:
            _run_evaluate_all_rules(app)
            from models.alert import Alert
            alert = Alert.query.filter_by(rule_id=rule.id, device_id=dev.id).first()
            assert alert.status == "open"

            # Metric recovers — add a newer, lower reading
            _make_metrics(app, dev.id, cpu_pct=10.0)
            _run_evaluate_all_rules(app)

            db.session.refresh(alert)
            assert alert.status == "resolved"
            assert alert.resolved_at is not None
        finally:
            _cleanup(app, device_ids=[dev.id], customer_id=cust.id, rule_ids=[rule.id])

    def test_offline_device_is_excluded(self, app):
        from extensions import db
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        dev.is_online = False
        db.session.commit()
        _make_metrics(app, dev.id, cpu_pct=95.0)
        rule = _make_rule(app, metric="cpu", operator="gt", threshold=90.0)
        try:
            _run_evaluate_all_rules(app)
            from models.alert import Alert
            assert Alert.query.filter_by(rule_id=rule.id, device_id=dev.id).first() is None
        finally:
            _cleanup(app, device_ids=[dev.id], customer_id=cust.id, rule_ids=[rule.id])
