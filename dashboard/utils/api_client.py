"""
Centralized HTTP client for all dashboard → API calls.
All methods return (data, error) tuples.
Includes: session reuse, retry with backoff, 401 auto-refresh.
"""
import os
import time
import streamlit as st
import requests
from typing import Optional, Tuple, Any

import logging as _logging
_log = _logging.getLogger(__name__)

API_BASE = os.getenv("API_BASE_URL", "http://localhost:5000")

# Warn if connecting to non-HTTPS API in a non-localhost environment
_host = API_BASE.split("//")[-1].split("/")[0].split(":")[0]
if API_BASE.startswith("http://") and _host not in ("localhost", "127.0.0.1", "0.0.0.0"):
    _log.warning(
        "API_BASE_URL uses plain HTTP (%s). Tokens and data will be transmitted "
        "unencrypted. Use HTTPS in any non-local deployment.",
        API_BASE,
    )

_RETRY_ON = (requests.ConnectionError, requests.Timeout)
_BACKOFF = [0.5, 1.0, 2.0]  # seconds between retries


class RMMClient:
    def __init__(self, access_token: str, refresh_token: str = ""):
        self._token = access_token
        self._refresh_token = refresh_token
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        })
        self.base = API_BASE

    def _try_refresh(self) -> bool:
        """Attempt silent token refresh using stored refresh_token. Returns True on success."""
        if not self._refresh_token:
            return False
        try:
            resp = requests.post(
                f"{self.base}/api/auth/refresh",
                headers={"Authorization": f"Bearer {self._refresh_token}"},
                timeout=10,
            )
            if resp.ok:
                new_token = resp.json().get("access_token", "")
                if new_token:
                    self._token = new_token
                    self.session.headers["Authorization"] = f"Bearer {new_token}"
                    st.session_state["access_token"] = new_token
                    return True
        except Exception:
            pass
        return False

    def _request(self, method: str, path: str, **kwargs) -> Tuple[Any, Optional[str]]:
        """Single entry point: retry on transient errors, auto-refresh on 401."""
        url = f"{self.base}{path}"
        last_err = None

        for attempt, wait in enumerate(_BACKOFF):
            try:
                resp = self.session.request(method, url, timeout=15, **kwargs)

                if resp.status_code == 401:
                    if self._try_refresh():
                        # One retry with refreshed token
                        retry = self.session.request(method, url, timeout=15, **kwargs)
                        if retry.ok:
                            return retry.json(), None
                    return None, "SESSION_EXPIRED"

                resp.raise_for_status()
                return resp.json(), None

            except requests.HTTPError as e:
                # HTTP errors (4xx except 401, 5xx) are not retried
                return None, f"HTTP {e.response.status_code}: {e.response.text}"
            except _RETRY_ON as e:
                last_err = e
                if attempt < len(_BACKOFF) - 1:
                    time.sleep(wait)

        return None, f"Connection failed after {len(_BACKOFF)} attempts: {last_err}"

    def _get(self, path: str, params: dict = None) -> Tuple[Any, Optional[str]]:
        return self._request("GET", path, params=params)

    def _post(self, path: str, data: dict = None) -> Tuple[Any, Optional[str]]:
        return self._request("POST", path, json=data)

    def _put(self, path: str, data: dict = None) -> Tuple[Any, Optional[str]]:
        return self._request("PUT", path, json=data)

    def _delete(self, path: str) -> Tuple[Any, Optional[str]]:
        return self._request("DELETE", path)

    # --- Auth ---
    @staticmethod
    def login(email: str, password: str) -> Tuple[Any, Optional[str]]:
        try:
            resp = requests.post(
                f"{API_BASE}/api/auth/login",
                json={"email": email, "password": password},
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json(), None
        except requests.HTTPError as e:
            return None, f"Login failed: {e.response.text}"
        except requests.RequestException as e:
            return None, str(e)

    def get_me(self):
        return self._get("/api/auth/me")

    def force_change_password(self, new_password: str):
        return self._post("/api/auth/me/force-change-password", {"new_password": new_password})

    def change_password(self, current_password: str, new_password: str):
        return self._put("/api/auth/me/password", {"current_password": current_password, "new_password": new_password})

    def upload_avatar(self, file_bytes: bytes, content_type: str) -> Tuple[Any, Optional[str]]:
        """Upload profile avatar image. Bypasses JSON session headers for multipart."""
        url = f"{self.base}/api/auth/me/avatar"
        try:
            resp = requests.put(
                url,
                files={"file": ("avatar", file_bytes, content_type)},
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json(), None
        except requests.HTTPError as e:
            return None, f"HTTP {e.response.status_code}: {e.response.text}"
        except requests.RequestException as e:
            return None, str(e)

    def delete_avatar(self) -> Tuple[Any, Optional[str]]:
        return self._request("DELETE", "/api/auth/me/avatar")

    # --- MFA ---
    def mfa_setup(self):
        """Generate provisional TOTP secret. Returns {secret, provisioning_uri}."""
        return self._post("/api/auth/mfa/setup")

    def mfa_enable(self, code: str):
        """Activate MFA after scanning QR. Requires valid TOTP code."""
        return self._post("/api/auth/mfa/enable", {"code": code})

    def mfa_disable(self, password: str):
        """Disable MFA. Requires current password for confirmation."""
        return self._post("/api/auth/mfa/disable", {"password": password})

    @staticmethod
    def mfa_login(mfa_token: str, code: str) -> Tuple[Any, Optional[str]]:
        """Second MFA login step. Posts mfa_token + TOTP code, returns full JWT."""
        try:
            resp = requests.post(
                f"{API_BASE}/api/auth/mfa/login",
                json={"mfa_token": mfa_token, "code": code},
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json(), None
        except requests.HTTPError as e:
            return None, f"HTTP {e.response.status_code}: {e.response.text}"
        except requests.RequestException as e:
            return None, str(e)

    # --- Dashboard ---
    def get_summary(self):
        return self._get("/api/dashboard/summary")

    def get_health_map(self):
        return self._get("/api/dashboard/health_map")

    def get_recent_alerts(self):
        return self._get("/api/dashboard/recent_alerts")

    def get_activity_feed(self):
        return self._get("/api/dashboard/activity_feed")

    # --- Customers ---
    def list_customers(self, page=1, per_page=50, q=""):
        return self._get("/api/customers/", params={"page": page, "per_page": per_page, "q": q})

    def create_customer(self, data: dict):
        return self._post("/api/customers/", data)

    def get_customer(self, customer_id: str):
        return self._get(f"/api/customers/{customer_id}")

    def update_customer(self, customer_id: str, data: dict):
        return self._put(f"/api/customers/{customer_id}", data)

    # --- Devices ---
    def list_devices(self, page=1, per_page=100, **filters):
        params = {"page": page, "per_page": per_page, **filters}
        return self._get("/api/devices/", params=params)

    def get_device(self, device_id: str):
        return self._get(f"/api/devices/{device_id}")

    def get_device_metrics(self, device_id: str, hours: int = 24):
        return self._get(f"/api/devices/{device_id}/metrics", params={"hours": hours})

    def get_device_software(self, device_id: str, q=""):
        return self._get(f"/api/devices/{device_id}/software", params={"q": q})

    def reboot_device(self, device_id: str):
        return self._post(f"/api/devices/{device_id}/reboot")

    def shutdown_device(self, device_id: str):
        return self._post(f"/api/devices/{device_id}/shutdown")

    def update_device(self, device_id: str, data: dict):
        return self._put(f"/api/devices/{device_id}", data)

    def get_platform_counts(self):
        return self._get("/api/devices/platform_counts")

    def ping_check_device(self, device_id: str):
        return self._post(f"/api/devices/{device_id}/ping_check")

    def upsert_agentless_devices(self, hosts: list, customer_id: str = None):
        payload = {"hosts": hosts}
        if customer_id:
            payload["customer_id"] = customer_id
        return self._post("/api/network/agentless_devices", payload)

    def trigger_network_scan(self, customer_id: str, scan_range: str):
        return self._post("/api/network/scan", {"customer_id": customer_id, "scan_range": scan_range})

    def get_server_ips(self):
        return self._get("/api/admin/server_ips")

    # --- Alerts ---
    def list_alert_rules(self):
        return self._get("/api/alert_rules")

    def create_alert_rule(self, data: dict):
        return self._post("/api/alert_rules", data)

    def update_alert_rule(self, rule_id: str, data: dict):
        return self._put(f"/api/alert_rules/{rule_id}", data)

    def delete_alert_rule(self, rule_id: str):
        return self._delete(f"/api/alert_rules/{rule_id}")

    def list_alerts(self, **filters):
        return self._get("/api/alerts", params=filters)

    def acknowledge_alert(self, alert_id: str):
        return self._post(f"/api/alerts/{alert_id}/acknowledge")

    def resolve_alert(self, alert_id: str):
        return self._post(f"/api/alerts/{alert_id}/resolve")

    # --- Tickets ---
    def list_tickets(self, **filters):
        return self._get("/api/tickets/", params=filters)

    def create_ticket(self, data: dict):
        return self._post("/api/tickets/", data)

    def get_ticket(self, ticket_id: str):
        return self._get(f"/api/tickets/{ticket_id}")

    def update_ticket(self, ticket_id: str, data: dict):
        return self._put(f"/api/tickets/{ticket_id}", data)

    def add_comment(self, ticket_id: str, body: str, is_internal=False):
        return self._post(f"/api/tickets/{ticket_id}/comments",
                          {"body": body, "is_internal": is_internal})

    # --- Scripts ---
    def list_scripts(self, **filters):
        return self._get("/api/scripts/", params=filters)

    def create_script(self, data: dict):
        return self._post("/api/scripts/", data)

    def get_script(self, script_id: str):
        return self._get(f"/api/scripts/{script_id}")

    def run_script(self, script_id: str, device_ids: list, timeout: int = 300):
        return self._post(f"/api/scripts/{script_id}/run",
                          {"device_ids": device_ids, "timeout_seconds": timeout})

    def list_script_runs(self, **filters):
        return self._get("/api/scripts/runs", params=filters)

    def get_script_run(self, run_id: str):
        return self._get(f"/api/scripts/runs/{run_id}")

    # --- Automation ---
    def list_profiles(self, **filters):
        return self._get("/api/automation/profiles", params=filters)

    def create_profile(self, data: dict):
        return self._post("/api/automation/profiles", data)

    def get_profile(self, profile_id: str):
        return self._get(f"/api/automation/profiles/{profile_id}")

    def update_profile(self, profile_id: str, data: dict):
        return self._put(f"/api/automation/profiles/{profile_id}", data)

    def run_profile_now(self, profile_id: str):
        return self._post(f"/api/automation/profiles/{profile_id}/run")

    def delete_run(self, run_id: str):
        return self._delete(f"/api/automation/runs/{run_id}")

    def clear_queued_runs(self, profile_id: str = None):
        params = f"?profile_id={profile_id}" if profile_id else ""
        return self._request("DELETE", f"/api/automation/runs/clear-queued{params}")

    # --- Patches ---
    def list_patches(self, **filters):
        return self._get("/api/patches/", params=filters)

    def get_pending_patches(self):
        return self._get("/api/patches/pending")

    def approve_patches(self, patch_ids: list):
        return self._post("/api/patches/approve", {"patch_ids": patch_ids})

    def get_patch_summary(self):
        return self._get("/api/patches/summary")

    # --- Admin / Users ---
    def list_users(self):
        return self._get("/api/admin/users")

    def create_user(self, data: dict):
        return self._post("/api/admin/users", data)

    def update_user(self, user_id: str, data: dict):
        return self._put(f"/api/admin/users/{user_id}", data)

    def delete_user(self, user_id: str):
        return self._delete(f"/api/admin/users/{user_id}")

    def get_org_token(self):
        return self._get("/api/admin/org-token")

    # --- Device tasks ---
    def queue_device_task(self, device_id: str, task_type: str, timeout: int = 300):
        return self._post(f"/api/devices/{device_id}/queue_task",
                          {"task_type": task_type, "timeout_seconds": timeout})

    def deploy_patches(self, device_id: str, patch_ids: list):
        return self._post(f"/api/devices/{device_id}/deploy_patches", {"patch_ids": patch_ids})

    # --- Reports ---
    def list_reports(self):
        return self._get("/api/reports/")

    def generate_report(self, data: dict):
        return self._post("/api/reports/generate", data)

    # --- Billing ---
    def list_invoices(self, customer_id=None):
        params = {"customer_id": customer_id} if customer_id else {}
        return self._get("/api/billing/invoices", params=params)

    def generate_invoice(self, data: dict):
        return self._post("/api/billing/invoices/generate", data)

    # --- Network / Agentless ---
    def get_platform_counts(self):
        return self._get("/api/devices/platform_counts")

    def ping_check_device(self, device_id: str):
        return self._post(f"/api/devices/{device_id}/ping_check")

    def upsert_agentless_devices(self, hosts: list, customer_id=None):
        payload = {"hosts": hosts}
        if customer_id:
            payload["customer_id"] = customer_id
        return self._post("/api/network/agentless_devices", payload)

    def trigger_network_scan(self, customer_id, scan_range: str):
        payload = {"scan_range": scan_range}
        if customer_id:
            payload["customer_id"] = customer_id
        return self._post("/api/network/scan", payload)

    def get_server_ips(self):
        return self._get("/api/admin/server_ips")

    def update_device(self, device_id: str, data: dict):
        return self._put(f"/api/devices/{device_id}", data)

    def delete_device(self, device_id: str):
        return self._delete(f"/api/devices/{device_id}")
