"""
IoT Sensor Agent — lightweight sensor collector for Raspberry Pi / Linux SBC.

Reads from available sensor backends and POSTs readings to the RMM API.
Reuses agent/config.ini and agent/heartbeat.py APIClient for auth.

Sensor backends (each optional — skipped if library not installed):
  - /sys/class/hwmon    — CPU/board temperature (no deps)
  - adafruit-dht        — DHT11/DHT22 temperature + humidity  (pip install adafruit-dht)
  - adafruit-circuitpython-bme680 — temperature, humidity, pressure, gas  (pip install adafruit-circuitpython-bme680)
  - gpiozero            — PIR motion sensor, door reed switch  (pip install gpiozero)

Setup:
  1. python agent/setup_agent.py <server_ip> <org_token>   (run once to register)
  2. python agent/iot_agent.py

Config (agent/config.ini):
  [iot]
  interval = 60          ; seconds between readings
  dht_type = DHT22       ; DHT11 or DHT22
  dht_pin = 4            ; BCM GPIO pin for DHT sensor
  bme680_i2c_addr = 0x77 ; I2C address for BME680
  pir_pin = 17           ; BCM GPIO pin for PIR motion sensor
  door_pin = 27          ; BCM GPIO pin for door reed switch
"""
import configparser
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("iot_agent")

_AGENT_DIR = Path(__file__).parent
sys.path.insert(0, str(_AGENT_DIR))

# ── Config ────────────────────────────────────────────────────────────────────

def _load_config() -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    cfg_path = _AGENT_DIR / "config.ini"
    if cfg_path.exists():
        cfg.read(str(cfg_path), encoding="utf-8")
    return cfg


def _get_connection_info(cfg: configparser.ConfigParser):
    """Return (server_url, device_id, agent_token) from config.ini."""
    server_url = cfg.get("server", "url", fallback="http://localhost:5000")
    device_id = cfg.get("agent", "device_id", fallback="")
    agent_token = cfg.get("agent", "agent_token", fallback="")
    if not device_id or not agent_token:
        logger.error("device_id / agent_token missing from config.ini — run setup_agent.py first")
        sys.exit(1)
    return server_url, device_id, agent_token


# ── Sensor backends ───────────────────────────────────────────────────────────

def _read_hwmon_temperature() -> list:
    """Read CPU/board temperature from /sys/class/hwmon (no extra deps)."""
    readings = []
    hwmon_base = Path("/sys/class/hwmon")
    if not hwmon_base.exists():
        return readings
    for hwmon in sorted(hwmon_base.iterdir()):
        try:
            name_file = hwmon / "name"
            name = name_file.read_text(encoding="utf-8").strip() if name_file.exists() else hwmon.name
            for temp_file in sorted(hwmon.glob("temp*_input")):
                try:
                    raw = int(temp_file.read_text(encoding="utf-8").strip())
                    temp_c = raw / 1000.0
                    channel = f"{name}_{temp_file.stem}"
                    readings.append({
                        "sensor_type": "temperature",
                        "value": temp_c,
                        "unit": "°C",
                        "channel": channel,
                    })
                except (ValueError, OSError):
                    continue
        except OSError:
            continue
    return readings


def _read_dht(dht_type: str, pin: int) -> list:
    """Read DHT11/DHT22 temperature + humidity."""
    readings = []
    try:
        import adafruit_dht
        import board
        dht_cls = adafruit_dht.DHT22 if dht_type.upper() == "DHT22" else adafruit_dht.DHT11
        gpio_pin = getattr(board, f"D{pin}", None)
        if gpio_pin is None:
            logger.warning("DHT: invalid GPIO pin %d", pin)
            return readings
        sensor = dht_cls(gpio_pin)
        temp = sensor.temperature
        hum = sensor.humidity
        if temp is not None:
            readings.append({"sensor_type": "temperature", "value": float(temp), "unit": "°C", "channel": f"dht_{pin}"})
        if hum is not None:
            readings.append({"sensor_type": "humidity", "value": float(hum), "unit": "%", "channel": f"dht_{pin}"})
    except ImportError:
        logger.debug("adafruit-dht not installed — DHT sensor skipped")
    except RuntimeError as exc:
        logger.warning("DHT read error: %s", exc)
    except Exception as exc:
        logger.warning("DHT unexpected error: %s", exc)
    return readings


def _read_bme680(i2c_addr: int) -> list:
    """Read BME680 — temperature, humidity, pressure, gas (air quality proxy)."""
    readings = []
    try:
        import board
        import busio
        import adafruit_bme680
        i2c = busio.I2C(board.SCL, board.SDA)
        sensor = adafruit_bme680.Adafruit_BME680_I2C(i2c, address=i2c_addr)
        channel = f"bme680_{hex(i2c_addr)}"
        readings.append({"sensor_type": "temperature", "value": float(sensor.temperature), "unit": "°C", "channel": channel})
        readings.append({"sensor_type": "humidity", "value": float(sensor.humidity), "unit": "%", "channel": channel})
        # gas resistance as VOC proxy (higher = cleaner air)
        readings.append({"sensor_type": "voc", "value": float(sensor.gas), "unit": "Ω", "channel": channel})
    except ImportError:
        logger.debug("adafruit-circuitpython-bme680 not installed — BME680 skipped")
    except Exception as exc:
        logger.warning("BME680 read error: %s", exc)
    return readings


def _read_gpio_sensors(pir_pin: int, door_pin: int) -> list:
    """Read PIR motion + door reed switch via gpiozero."""
    readings = []
    try:
        from gpiozero import MotionSensor, Button
        if pir_pin > 0:
            pir = MotionSensor(pir_pin)
            readings.append({"sensor_type": "motion", "value": 1.0 if pir.motion_detected else 0.0, "unit": "bool", "channel": f"pir_{pir_pin}"})
        if door_pin > 0:
            door = Button(door_pin, pull_up=True)
            readings.append({"sensor_type": "door", "value": 1.0 if door.is_pressed else 0.0, "unit": "bool", "channel": f"door_{door_pin}"})
    except ImportError:
        logger.debug("gpiozero not installed — GPIO sensors skipped")
    except Exception as exc:
        logger.warning("GPIO sensor read error: %s", exc)
    return readings


# ── Main loop ─────────────────────────────────────────────────────────────────

def collect_readings(cfg: configparser.ConfigParser) -> list:
    readings = []

    # /sys/class/hwmon — always try
    readings.extend(_read_hwmon_temperature())

    iot = cfg["iot"] if cfg.has_section("iot") else {}

    # DHT sensor
    dht_pin = int(iot.get("dht_pin", "0"))
    if dht_pin > 0:
        dht_type = iot.get("dht_type", "DHT22")
        readings.extend(_read_dht(dht_type, dht_pin))

    # BME680
    bme_addr_raw = iot.get("bme680_i2c_addr", "0")
    bme_addr = int(bme_addr_raw, 16) if bme_addr_raw.startswith("0x") else int(bme_addr_raw)
    if bme_addr > 0:
        readings.extend(_read_bme680(bme_addr))

    # GPIO motion / door
    pir_pin = int(iot.get("pir_pin", "0"))
    door_pin = int(iot.get("door_pin", "0"))
    if pir_pin > 0 or door_pin > 0:
        readings.extend(_read_gpio_sensors(pir_pin, door_pin))

    # Stamp collected_at
    now = datetime.now(timezone.utc).isoformat()
    for r in readings:
        r.setdefault("collected_at", now)

    return readings


def push_readings(server_url: str, device_id: str, agent_token: str, readings: list) -> bool:
    """POST batch to /api/sensors/<device_id>/data."""
    import requests
    try:
        resp = requests.post(
            f"{server_url.rstrip('/')}/api/sensors/{device_id}/data",
            json=readings,
            headers={"Authorization": f"Bearer {agent_token}", "Content-Type": "application/json"},
            timeout=15,
        )
        if resp.ok:
            data = resp.json()
            logger.info("Pushed %d readings (inserted=%d)", len(readings), data.get("inserted", 0))
            if data.get("errors"):
                logger.warning("Push errors: %s", data["errors"])
            return True
        logger.warning("Push failed: %d %s", resp.status_code, resp.text[:200])
        return False
    except requests.RequestException as exc:
        logger.warning("Push connection error: %s", exc)
        return False


def main():
    cfg = _load_config()
    server_url, device_id, agent_token = _get_connection_info(cfg)
    interval = int(cfg.get("iot", "interval", fallback="60")) if cfg.has_section("iot") else 60

    logger.info("IoT agent started — device_id=%s, interval=%ds", device_id, interval)

    while True:
        try:
            readings = collect_readings(cfg)
            if readings:
                push_readings(server_url, device_id, agent_token, readings)
            else:
                logger.info("No sensor readings collected this cycle")
        except Exception as exc:
            logger.error("Unexpected error in collection loop: %s", exc, exc_info=True)
        time.sleep(interval)


if __name__ == "__main__":
    main()
