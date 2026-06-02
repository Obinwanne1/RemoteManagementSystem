"""
RMM Agent — main entry point.

Flow:
  1. Load config
  2. If no device_id/token: register with API
  3. Loop: heartbeat → poll tasks → execute tasks → sleep
"""
import configparser
import logging
import sys
import time
from pathlib import Path

from collector import get_hardware_info, get_metrics, get_installed_software
from heartbeat import APIClient
from executor import execute_task

CONFIG_PATH = Path(__file__).parent / "config.ini"
LOG_PATH = Path(__file__).parent / "rmm_agent.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(LOG_PATH), encoding="utf-8"),
    ],
)
logger = logging.getLogger("rmm_agent")


def load_config() -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    if not CONFIG_PATH.exists():
        logger.error(f"Config file not found: {CONFIG_PATH}")
        sys.exit(1)
    config.read(str(CONFIG_PATH), encoding="utf-8")
    return config


def save_config(config: configparser.ConfigParser):
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

    # Persist to config (plain text for dev; use DPAPI encryption in production)
    config.set("agent", "device_id", device_id)
    config.set("agent", "agent_token", agent_token)
    save_config(config)

    logger.info(f"Registered as device_id={device_id}")
    return APIClient(api_url, device_id, agent_token)


def main():
    config = load_config()
    api_url = config.get("api", "url")
    device_id = config.get("agent", "device_id", fallback="").strip()
    agent_token = config.get("agent", "agent_token", fallback="").strip()
    heartbeat_interval = config.getint("agent", "heartbeat_interval", fallback=60)
    software_interval = config.getint("agent", "software_interval", fallback=21600)

    # Register if not already
    if not device_id or not agent_token:
        client = register(config)
        device_id = config.get("agent", "device_id")
        agent_token = config.get("agent", "agent_token")
    else:
        client = APIClient(api_url, device_id, agent_token)

    logger.info(f"Agent started. device_id={device_id} api={api_url}")

    last_software_sync = 0
    iteration = 0

    while True:
        try:
            # Collect and send metrics
            metrics = get_metrics()
            result = client.send_heartbeat(metrics)
            if result:
                logger.debug(f"Heartbeat OK — server_time={result.get('server_time')}")
            else:
                logger.warning("Heartbeat failed, will retry next cycle")

            # Poll and execute tasks
            tasks = client.get_tasks()
            for task in tasks:
                logger.info(f"Executing task: {task.get('type')} id={task.get('task_id')}")
                execute_task(task, client)

            # Sync software list periodically
            now = time.time()
            if now - last_software_sync >= software_interval:
                logger.info("Syncing installed software list...")
                sw = get_installed_software()
                client.update_software(sw)
                last_software_sync = now
                logger.info(f"Software sync complete: {len(sw)} packages")

        except KeyboardInterrupt:
            logger.info("Agent stopped by user")
            break
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}", exc_info=True)

        iteration += 1
        time.sleep(heartbeat_interval)


if __name__ == "__main__":
    main()
