"""ConnectWise Manage REST client (API v3)."""
import base64
import logging
from datetime import datetime, timezone

import requests

from .base import PSAClient

logger = logging.getLogger(__name__)

_CW_PRIORITY = {"critical": "Priority 1 - Critical", "high": "Priority 2 - High",
                "medium": "Priority 3 - Medium", "low": "Priority 4 - Low"}
_CW_STATUS_MAP = {"open": "New", "in_progress": "In Progress",
                  "resolved": "Completed", "closed": "Closed"}
_CW_STATUS_REVERSE = {v: k for k, v in _CW_STATUS_MAP.items()}

TIMEOUT = 15


class ConnectWiseClient(PSAClient):
    """
    ConnectWise Manage REST API v3.

    api_url  — base URL including version path, e.g.
                https://yourserver/v4_6_release/apis/3.0
    company_id  — CW company identifier (short name, e.g. "mycompany")
    client_id   — CW public API key / client ID (also sent as clientId header)
    client_secret — CW private API key
    """

    def __init__(self, api_url: str, company_id: str, client_id: str, client_secret: str):
        self._base = api_url.rstrip("/")
        self._session = requests.Session()
        creds = base64.b64encode(f"{company_id}+{client_id}:{client_secret}".encode()).decode()
        self._session.headers.update({
            "Authorization": f"Basic {creds}",
            "clientId": client_id,
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    def _get(self, path: str, params: dict = None) -> list | dict:
        resp = self._session.get(f"{self._base}{path}", params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, body: dict) -> dict:
        resp = self._session.post(f"{self._base}{path}", json=body, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def _patch(self, path: str, ops: list) -> dict:
        resp = self._session.patch(f"{self._base}{path}", json=ops, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def test_connection(self) -> tuple[bool, str]:
        try:
            self._get("/system/info")
            return True, "Connected"
        except Exception as exc:
            return False, str(exc)

    def get_companies(self) -> list[dict]:
        try:
            rows = self._get("/company/companies", params={"conditions": "status/id=1", "pageSize": 1000})
            return [{"id": str(r["id"]), "name": r.get("name", ""), "identifier": r.get("identifier", "")}
                    for r in (rows if isinstance(rows, list) else [])]
        except Exception as exc:
            logger.warning("CW get_companies failed: %s", exc)
            return []

    def push_ticket(self, ticket, psa_company_id: str) -> str | None:
        body = {
            "summary": ticket.title[:255],
            "initialDescription": ticket.description or ticket.title,
            "board": {"name": "Service Board"},
            "status": {"name": _CW_STATUS_MAP.get(ticket.status, "New")},
            "priority": {"name": _CW_PRIORITY.get(ticket.priority, "Priority 3 - Medium")},
            "company": {"id": int(psa_company_id)},
            "type": {"name": "Service Request"},
            "sourceList": {"name": "Web"},
        }
        try:
            result = self._post("/service/tickets", body)
            return str(result["id"])
        except Exception as exc:
            logger.warning("CW push_ticket failed for ticket %s: %s", ticket.id, exc)
            return None

    def update_ticket(self, psa_ticket_id: str, ticket) -> bool:
        ops = [
            {"op": "replace", "path": "summary", "value": ticket.title[:255]},
            {"op": "replace", "path": "status/name",
             "value": _CW_STATUS_MAP.get(ticket.status, "In Progress")},
            {"op": "replace", "path": "priority/name",
             "value": _CW_PRIORITY.get(ticket.priority, "Priority 3 - Medium")},
        ]
        try:
            self._patch(f"/service/tickets/{psa_ticket_id}", ops)
            return True
        except Exception as exc:
            logger.warning("CW update_ticket failed for psa_id %s: %s", psa_ticket_id, exc)
            return False

    def pull_tickets(self, since: datetime) -> list[dict]:
        iso = since.strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            rows = self._get("/service/tickets", params={
                "conditions": f"lastUpdated>[{iso}]",
                "pageSize": 500,
                "orderBy": "lastUpdated asc",
            })
            return [
                {
                    "psa_ticket_id": str(r["id"]),
                    "title": r.get("summary", ""),
                    "description": r.get("initialDescription", ""),
                    "status": _CW_STATUS_REVERSE.get(r.get("status", {}).get("name", ""), "open"),
                    "priority": _cw_priority_reverse(r.get("priority", {}).get("name", "")),
                    "psa_company_id": str(r.get("company", {}).get("id", "")),
                    "updated_at": r.get("lastUpdated"),
                }
                for r in (rows if isinstance(rows, list) else [])
            ]
        except Exception as exc:
            logger.warning("CW pull_tickets failed: %s", exc)
            return []

    def push_config_item(self, device, psa_company_id: str) -> str | None:
        body = {
            "name": device.hostname or device.ip_address,
            "type": {"name": _cw_config_type(device.platform)},
            "status": {"name": "Active" if device.is_online else "Inactive"},
            "company": {"id": int(psa_company_id)},
            "ipAddress": device.ip_address or "",
            "macAddress": device.mac_address or "",
            "osType": device.platform or "",
            "osInfo": device.os_version or "",
        }
        try:
            result = self._post("/company/configurations", body)
            return str(result["id"])
        except Exception as exc:
            logger.warning("CW push_config_item failed for device %s: %s", device.id, exc)
            return None


def _cw_priority_reverse(name: str) -> str:
    if "1" in name or "critical" in name.lower():
        return "critical"
    if "2" in name or "high" in name.lower():
        return "high"
    if "4" in name or "low" in name.lower():
        return "low"
    return "medium"


def _cw_config_type(platform: str) -> str:
    p = (platform or "").lower()
    if "windows" in p:
        return "Workstation"
    if "server" in p:
        return "Server"
    if "mac" in p or "darwin" in p:
        return "Laptop"
    if "linux" in p:
        return "Server"
    return "Workstation"
