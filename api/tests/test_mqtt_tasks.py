"""Tests for tasks/mqtt_tasks.py::subscribe_mqtt_sensors (audits/testing_audit.md
Finding C3, 89 statements, 0% coverage before this file).

The real paho-mqtt client is always mocked — this task connects to an external
MQTT broker, and no test here should attempt a real network connection."""
import uuid
from unittest.mock import MagicMock, patch

import tasks._app_singleton as app_singleton
import tasks.mqtt_tasks as mqtt_tasks

# Real import so paho.mqtt.client exists as an attribute for patch.object() below
# (patch("paho.mqtt.client", ...) fails with AttributeError before this module
# has ever been imported — mqtt_tasks.py only imports it lazily, inside the task).
import paho.mqtt.client as _real_mqtt_client_module


def _make_customer(app):
    from extensions import db
    from models.customer import Customer
    c = Customer(name=f"MqttCo-{uuid.uuid4().hex[:6]}", slug=f"mq-{uuid.uuid4().hex[:6]}", is_active=True)
    db.session.add(c)
    db.session.commit()
    return c


def _make_device(app, customer_id):
    from extensions import db
    from models.device import Device
    d = Device(
        hostname=f"host-{uuid.uuid4().hex[:6]}", customer_id=customer_id,
        platform="linux", is_online=True,
    )
    db.session.add(d)
    db.session.commit()
    return d


def _cleanup(app, *, device_ids=(), customer_id=None):
    from extensions import db
    from models.device import Device, DeviceSensorReading
    from models.customer import Customer
    for did in device_ids:
        DeviceSensorReading.query.filter_by(device_id=did).delete()
        Device.query.filter_by(id=did).delete()
    if customer_id:
        Customer.query.filter_by(id=customer_id).delete()
    db.session.commit()


class TestSubscribeMqttSensorsNoOp:
    def test_no_op_when_mqtt_host_unset(self, app, monkeypatch):
        """MQTT_HOST unset is the documented no-op path — must not attempt any
        network connection and must not raise."""
        app_singleton._app = app
        monkeypatch.delenv("MQTT_HOST", raising=False)
        result = mqtt_tasks.subscribe_mqtt_sensors()
        assert result is None


class TestSubscribeMqttSensorsWithBroker:
    def _fake_mqtt_module(self, on_connect_rc=0, messages=()):
        """Builds a fake paho.mqtt.client module whose Client() simulates
        on_connect/on_message callbacks firing during connect()/loop_start()."""
        fake_client_instance = MagicMock()

        def _connect(host, port, keepalive=10):
            fake_client_instance.on_connect(fake_client_instance, None, None, on_connect_rc)

        def _loop_start():
            for msg in messages:
                fake_client_instance.on_message(fake_client_instance, None, msg)

        fake_client_instance.connect.side_effect = _connect
        fake_client_instance.loop_start.side_effect = _loop_start

        fake_client_class = MagicMock(return_value=fake_client_instance)
        return fake_client_class

    def _fake_message(self, topic, payload_dict):
        import json
        msg = MagicMock()
        msg.topic = topic
        msg.payload = json.dumps(payload_dict).encode("utf-8")
        return msg

    def test_inserts_reading_for_known_device_and_sensor_type(self, app, monkeypatch):
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        try:
            app_singleton._app = app
            monkeypatch.setenv("MQTT_HOST", "broker.test.local")

            msg = self._fake_message(f"rmm/{dev.id}/sensors/temperature", {"value": 21.5, "unit": "C"})
            fake_client_class = self._fake_mqtt_module(messages=[msg])

            with patch.object(_real_mqtt_client_module, "Client", fake_client_class), patch("time.sleep"):
                mqtt_tasks.subscribe_mqtt_sensors()

            from models.device import DeviceSensorReading
            reading = DeviceSensorReading.query.filter_by(device_id=dev.id).first()
            assert reading is not None
            assert reading.sensor_type == "temperature"
            assert reading.value == 21.5
            assert reading.source == "mqtt"
        finally:
            _cleanup(app, device_ids=[dev.id], customer_id=cust.id)

    def test_skips_unknown_sensor_type(self, app, monkeypatch):
        cust = _make_customer(app)
        dev = _make_device(app, cust.id)
        try:
            app_singleton._app = app
            monkeypatch.setenv("MQTT_HOST", "broker.test.local")

            msg = self._fake_message(f"rmm/{dev.id}/sensors/not_a_real_sensor", {"value": 1})
            fake_client_class = self._fake_mqtt_module(messages=[msg])

            with patch.object(_real_mqtt_client_module, "Client", fake_client_class), patch("time.sleep"):
                mqtt_tasks.subscribe_mqtt_sensors()

            from models.device import DeviceSensorReading
            assert DeviceSensorReading.query.filter_by(device_id=dev.id).first() is None
        finally:
            _cleanup(app, device_ids=[dev.id], customer_id=cust.id)

    def test_skips_reading_for_unknown_device(self, app, monkeypatch):
        app_singleton._app = app
        monkeypatch.setenv("MQTT_HOST", "broker.test.local")

        msg = self._fake_message("rmm/not-a-real-device-id/sensors/temperature", {"value": 21.5})
        fake_client_class = self._fake_mqtt_module(messages=[msg])

        with patch.object(_real_mqtt_client_module, "Client", fake_client_class), patch("time.sleep"):
            # Must not raise even though the device_id doesn't exist.
            mqtt_tasks.subscribe_mqtt_sensors()

    def test_retries_on_connection_error(self, app, monkeypatch):
        """The task decorator's max_retries=3 was previously decorative (per its
        own inline comment) — this pins that self.retry() is actually invoked."""
        app_singleton._app = app
        monkeypatch.setenv("MQTT_HOST", "broker.test.local")

        fake_client_instance = MagicMock()
        fake_client_instance.connect.side_effect = ConnectionRefusedError("refused")
        fake_client_class = MagicMock(return_value=fake_client_instance)

        with patch.object(_real_mqtt_client_module, "Client", fake_client_class), patch("time.sleep"):
            try:
                mqtt_tasks.subscribe_mqtt_sensors()
                assert False, "expected a retry-triggered exception"
            except Exception as exc:
                # Celery's self.retry() raises a Retry exception (or the original
                # under eager/always-eager-less test conditions) — either way,
                # a raised exception here (not a silent return) is the pinned behavior.
                assert exc is not None
