"""
Heartbeat — sends metrics to API and polls for tasks.
"""
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)


class APIClient:
    def __init__(self, base_url: str, device_id: str, agent_token: str):
        self.base_url = base_url.rstrip("/")
        self.device_id = device_id
        self.headers = {
            "Authorization": f"Bearer {agent_token}",
            "Content-Type": "application/json",
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def send_heartbeat(self, metrics: dict) -> tuple:
        """Returns (data_or_None, http_status_code). Status 0 = connection error."""
        url = f"{self.base_url}/api/agents/{self.device_id}/heartbeat"
        try:
            resp = self.session.post(url, json=metrics, timeout=30)
            if resp.status_code == 401:
                return None, 401
            resp.raise_for_status()
            return resp.json(), resp.status_code
        except requests.exceptions.HTTPError as e:
            logger.warning("Heartbeat HTTP error: %s", e)
            status = e.response.status_code if e.response is not None else 0
            return None, status
        except requests.RequestException as e:
            logger.warning("Heartbeat failed: %s", e)
            return None, 0

    def get_tasks(self) -> list:
        url = f"{self.base_url}/api/agents/{self.device_id}/tasks"
        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            return resp.json().get("tasks", [])
        except requests.RequestException as e:
            logger.warning(f"Task poll failed: {e}")
            return []

    def post_task_result(self, task_id: str, task_type: str, result: dict) -> bool:
        url = f"{self.base_url}/api/agents/{self.device_id}/task_result"
        payload = {"task_id": task_id, "type": task_type, **result}
        try:
            resp = self.session.post(url, json=payload, timeout=30)
            resp.raise_for_status()
            return True
        except requests.RequestException as e:
            logger.warning(f"Task result post failed: {e}")
            return False

    def update_software(self, software: list) -> bool:
        url = f"{self.base_url}/api/agents/{self.device_id}/software"
        try:
            resp = self.session.put(url, json={"software": software}, timeout=60)
            resp.raise_for_status()
            return True
        except requests.RequestException as e:
            logger.warning(f"Software update failed: {e}")
            return False

    @staticmethod
    def register(base_url: str, org_token: str, hardware_info: dict) -> Optional[dict]:
        """Register agent with API. Returns {device_id, agent_token} or None."""
        url = f"{base_url.rstrip('/')}/api/agents/register"
        payload = {"org_token": org_token, **hardware_info}
        try:
            resp = requests.post(url, json=payload, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.error(f"Registration failed: {e}")
            return None
