"""Autotask (Datto) PSA REST client (V1.0)."""
import logging
from datetime import datetime, timezone

import requests

from .base import PSAClient

logger = logging.getLogger(__name__)

# Autotask status IDs (standard defaults — may vary per instance)
_AT_STATUS = {"open": 1, "in_progress": 8, "resolved": 5, "closed": 5}
_AT_STATUS_REVERSE = {1: "open", 8: "in_progress", 5: "resolved"}
# Priority: 1=Critical 2=High 3=Medium 4=Low
_AT_PRIORITY = {"critical": 1, "high": 2, "medium": 3, "low": 4}
_AT_PRIORITY_REVERSE = {1: "critical", 2: "high", 3: "medium", 4: "low"}

TIMEOUT = 15


class AutotaskClient(PSAClient):
    """
    Autotask PSA REST API V1.0.

    api_url      — zone base URL, e.g. https://webservices1.autotask.net/ATServicesRest/V1.0
    client_id    — API integration code (from Admin → API Security)
    client_secret — not used by Autotask; username goes here
    username     — stored in site_name field for convenience
    secret       — user API secret
    """

    def __init__(self, api_url: str, client_id: str, username: str, secret: str):
        self._base = api_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers.update({
            "ApiIntegrationCode": client_id,
            "UserName": username,
            "Secret": secret,
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    def _get(self, path: str, params: dict = None) -> dict:
        resp = self._session.get(f"{self._base}{path}", params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, body: dict) -> dict:
        resp = self._session.post(f"{self._base}{path}", json=body, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def _put(self, path: str, body: dict) -> dict:
        resp = self._session.put(f"{self._base}{path}", json=body, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def test_connection(self) -> tuple[bool, str]:
        try:
            self._get("/zoneInformation", params={"user": ""})
            return True, "Connected"
        except Exception as exc:
            return False, str(exc)

    def get_companies(self) -> list[dict]:
        try:
            data = self._get("/Companies", params={"search": '{"filter":[{"field":"isActive","op":"eq","value":true}]}'})
            items = data.get("items", [])
            return [{"id": str(c["id"]), "name": c.get("companyName", ""), "identifier": str(c["id"])}
                    for c in items]
        except Exception as exc:
            logger.warning("AT get_companies failed: %s", exc)
            return []

    def push_ticket(self, ticket, psa_company_id: str) -> str | None:
        body = {
            "Title": ticket.title[:255],
            "Description": ticket.description or ticket.title or "",
            "Status": _AT_STATUS.get(ticket.status, 1),
            "Priority": _AT_PRIORITY.get(ticket.priority, 3),
            "CompanyID": int(psa_company_id),
            "QueueID": 29682249,  # default "Client Portal" queue — admin can change per-instance
            "TicketType": 1,  # Service Request
        }
        try:
            result = self._post("/Tickets", body)
            item_id = result.get("itemId") or (result.get("item") or {}).get("id")
            return str(item_id) if item_id else None
        except Exception as exc:
            logger.warning("AT push_ticket failed for ticket %s: %s", ticket.id, exc)
            return None

    def update_ticket(self, psa_ticket_id: str, ticket) -> bool:
        body = {
            "id": int(psa_ticket_id),
            "Title": ticket.title[:255],
            "Status": _AT_STATUS.get(ticket.status, 8),
            "Priority": _AT_PRIORITY.get(ticket.priority, 3),
        }
        try:
            self._put(f"/Tickets/{psa_ticket_id}", body)
            return True
        except Exception as exc:
            logger.warning("AT update_ticket failed for psa_id %s: %s", psa_ticket_id, exc)
            return False

    def pull_tickets(self, since: datetime) -> list[dict]:
        iso = since.strftime("%Y-%m-%dT%H:%M:%SZ")
        search = (
            '{"filter":['
            f'{{"field":"lastActivityDate","op":"gte","value":"{iso}"}},'
            '{"field":"status","op":"noteq","value":5}'
            ']}'
        )
        try:
            data = self._get("/Tickets", params={"search": search})
            items = data.get("items", [])
            return [
                {
                    "psa_ticket_id": str(t["id"]),
                    "title": t.get("title", ""),
                    "description": t.get("description", ""),
                    "status": _AT_STATUS_REVERSE.get(t.get("status"), "open"),
                    "priority": _AT_PRIORITY_REVERSE.get(t.get("priority"), "medium"),
                    "psa_company_id": str(t.get("companyID", "")),
                    "updated_at": t.get("lastActivityDate"),
                }
                for t in items
            ]
        except Exception as exc:
            logger.warning("AT pull_tickets failed: %s", exc)
            return []

    def push_config_item(self, device, psa_company_id: str) -> str | None:
        body = {
            "CompanyID": int(psa_company_id),
            "ProductID": 0,
            "SerialNumber": device.id[:50],
            "ReferenceTitle": device.hostname or device.ip_address or "Unknown",
            "Notes": f"Platform: {device.platform or 'Unknown'} | OS: {device.os_version or 'Unknown'}",
            "Active": device.is_online,
        }
        try:
            result = self._post("/ConfigurationItems", body)
            item_id = result.get("itemId") or (result.get("item") or {}).get("id")
            return str(item_id) if item_id else None
        except Exception as exc:
            logger.warning("AT push_config_item failed for device %s: %s", device.id, exc)
            return None
