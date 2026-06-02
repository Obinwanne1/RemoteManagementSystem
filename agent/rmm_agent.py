"""
RMM Agent — main entry point.

Flow:
  1. Load config
  2. If no device_id/token: register with API
  3. Loop: flush queue → heartbeat → poll tasks → execute tasks → sleep
"""
import configparser
import logging
import sys
import time
from pathlib import Path

import psutil

from collector import get_hardware_info, get_metrics, get_installed_software
from heartbeat import APIClient
from executor import execute_task, flush_pending_queue

CONFIG_PATH = Path(__file__).parent / "config.ini"
LOG_PATH = Path(__file__).parent / "rmm_agent.log"


# ── C-7: structured logging with device_id stamp ─────────────────────────────

class DeviceFilter(logging.Filter):
    """Stamps device_id on every log record so all lines are traceable."""
    def __init__(self, device_id: str = "unregistered"):
        super().__init__()
        self.device_id = device_id

    def filter(self, record: logging.LogRecord) -> bool:
        record.device_id = self.device_id
        return True


_device_filter = DeviceFilter()


def _setup_logging() -> None:
    fmt = "%(asctime)s %(levelname)-8s %(name)-20s [device=%(device_id)s] %(message)s"
    formatter = logging.Formatter(fmt)
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(LOG_PATH), encoding="utf-8"),
    ]
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for h in handlers:
        h.setFormatter(formatter)
        h.addFilter(_device_filter)
        root.addHandler(h)


_setup_logging()
logger = logging.getLogger("rmm_agent")


# ── Config helpers ────────────────────────────────────────────────────────────

def load_config() -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    if not CONFIG_PATH.exists():
        logger.error("Config file not found: %s", CONFIG_PATH)
        sys.exit(1)
    config.read(str(CONFIG_PATH), encoding="utf-8")
    return config


def save_config(config: configparser.ConfigParser) -> None:
    with open(str(CONFIG_PATH), "w", encoding="utf-8") as f:
        config.write(f)


def register(config: configparser.ConfigParser) -> APIClient:
    """Register with API and save credentials to config."""
    api_url = config.get("api", "url")
    org_token = config.get("api", "org_token")

    logger.info("Registering agent with API...")
    hw = get_hardware_info()

    result = APIClient.register(api_url, org_token, hw)
    if not result:
        logger.error("Registration failed. Check API URL and org_token in config.ini")
        sys.exit(1)

    device_id = result["device_id"]
    agent_token = result["agent_token"]

    config.set("agent", "device_id", device_id)
    config.set("agent", "agent_token", agent_token)
    save_config(config)

    logger.info("Registered as device_id=%s", device_id)
    return APIClient(api_url, device_id, agent_token)


# ── Main loop ─────────────────────────────────────────────────────────────────

def main():
    config = load_config()
    api_url = config.get("api", "url")
    device_id = config.get("agent", "device_id", fallback="").strip()
    agent_token = config.get("agent", "agent_token", fallback="").strip()
    heartbeat_interval = config.getint("agent", "heartbeat_interval", fallback=60)
    software_interval = config.getint("agent", "software_interval", fallback=21600)

    if not device_id or not agent_token:
        client = register(config)
        device_id = config.get("agent", "device_id")
    else:
        client = APIClient(api_url, device_id, agent_token)

    # C-7: stamp device_id on all log records after identity is known
    _device_filter.device_id = device_id
    logger.info("Agent started. device_id=%s api=%s", device_id, api_url)

    # C-1: prime CPU counter; first non-blocking sample is always 0.0 otherwise
    psutil.cpu_percent(interval=None)

    last_software_sync = 0.0
    _consecutive_failures = 0  # C-4

    while True:
        try:
            # C-6: flush any locally queued task results before new cycle
            flushed = flush_pending_queue(client)
            if flushed:
                logger.info("Flushed %d pending task result(s)", flushed)

            # Collect and send metrics
            metrics = get_metrics()
            data, status = client.send_heartbeat(metrics)  # C-5: returns (data, status_code)

            # C-5: re-register on 401
            if status == 401:
                logger.warning("Heartbeat returned 401 — re-registering agent")
                client = register(config)
                device_id = config.get("agent", "device_id")
                _device_filter.device_id = device_id
                _consecutive_failures = 0
                time.sleep(heartbeat_interval)
                continue

            # C-4: exponential backoff on consecutive failures
            if data is None:
                _consecutive_failures += 1
                backoff = min(15 * (2 ** (_consecutive_failures - 1)), 300)
                logger.warning(
                    "Heartbeat failed (failure #%d) — backing off %ds",
                    _consecutive_failures, backoff,
                )
                time.sleep(backoff)
                continue

            _consecutive_failures = 0
            logger.debug("Heartbeat OK — server_time=%s", data.get("server_time"))

            # Poll and execute tasks
            tasks = client.get_tasks()
            for task in tasks:
                logger.info(
                    "Executing task: %s id=%s", task.get("type"), task.get("task_id")
                )
                execute_task(task, client)

            # Sync software list periodically
            now = time.time()
            if now - last_software_sync >= software_interval:
                logger.info("Syncing installed software list...")
                sw = get_installed_software()
                client.update_software(sw)
                last_software_sync = now
                logger.info("Software sync complete: %d packages", len(sw))

        except KeyboardInterrupt:
            logger.info("Agent stopped by user")
            break
        except ConnectionError as e:
            # C-7: classified network errors
            _consecutive_failures += 1
            backoff = min(15 * (2 ** (_consecutive_failures - 1)), 300)
            logger.warning("NETWORK_FAILURE: %s — backing off %ds", e, backoff)
            time.sleep(backoff)
            continue
        except TimeoutError as e:
            _consecutive_failures += 1
            backoff = min(15 * (2 ** (_consecutive_failures - 1)), 300)
            logger.warning("NETWORK_TIMEOUT: %s — backing off %ds", e, backoff)
            time.sleep(backoff)
            continue
        except Exception as e:
            logger.error("UNEXPECTED_ERROR: %s", e, exc_info=True)

        time.sleep(heartbeat_interval)


if __name__ == "__main__":
    main()
