"""Thin REST client over Google's Android Management API.

No custom agent code runs on managed phones — enrollment provisions Google's
own signed "Android Device Policy" app via a QR code / enrollment token.
This module only talks to Google's REST API on the server side.

Requires the `google-auth` package (service-account JWT signing).
Reference: https://developers.google.com/android/management/reference/rest
"""
import json
import logging
import time

import requests

logger = logging.getLogger(__name__)

_BASE = "https://androidmanagement.googleapis.com/v1"
_SCOPES = ["https://www.googleapis.com/auth/androidmanagement"]


class AndroidManagementClient:
    def __init__(self, project_id: str, enterprise_id: str = None, service_account_json: str = ""):
        self.project_id = project_id
        self.enterprise_id = enterprise_id
        self._sa_info = json.loads(service_account_json) if service_account_json else None
        self._credentials = None

    def _auth_headers(self) -> dict:
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request

        if self._credentials is None:
            if not self._sa_info:
                raise ValueError("No service account credentials configured for this integration")
            self._credentials = service_account.Credentials.from_service_account_info(
                self._sa_info, scopes=_SCOPES,
            )
        if not self._credentials.valid:
            self._credentials.refresh(Request())
        return {"Authorization": f"Bearer {self._credentials.token}"}

    def _request(self, method: str, path: str, params: dict = None, body: dict = None) -> dict:
        from utils.usage_tracker import record_event
        url = f"{_BASE}/{path}"
        _t0 = time.perf_counter()
        try:
            resp = requests.request(
                method, url,
                headers={**self._auth_headers(), "Content-Type": "application/json"},
                params=params, json=body, timeout=30,
            )
            resp.raise_for_status()
            record_event(service="android_mdm", feature=path, status="success",
                         status_code=resp.status_code, latency_ms=int((time.perf_counter() - _t0) * 1000))
            return resp.json() if resp.content else {}
        except Exception as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            record_event(service="android_mdm", feature=path, status="error", status_code=status_code,
                         latency_ms=int((time.perf_counter() - _t0) * 1000), error=type(exc).__name__)
            raise

    # --- Enterprise binding (one-time setup) ---

    def create_signup_url(self, callback_url: str) -> dict:
        """Step 1 of binding: returns {url, name} — admin opens `url` in a browser."""
        return self._request(
            "POST", "signupUrls",
            params={"projectId": self.project_id, "callbackUrl": callback_url},
        )

    def create_enterprise(self, signup_url_name: str, enterprise_token: str,
                          display_name: str, pubsub_topic: str = None) -> dict:
        """Step 2, called from the bind_callback route once Google redirects back."""
        body = {"enterpriseDisplayName": display_name}
        if pubsub_topic:
            body["pubsubTopic"] = pubsub_topic
        return self._request(
            "POST", "enterprises",
            params={
                "projectId": self.project_id,
                "signupUrlName": signup_url_name,
                "enterpriseToken": enterprise_token,
            },
            body=body,
        )

    # --- Policy ---

    def patch_policy(self, policy_name: str, policy: dict) -> dict:
        """policy_name like 'default'. Full resource name is enterprises/{id}/policies/{policy_name}."""
        return self._request(
            "PATCH", f"enterprises/{self.enterprise_id}/policies/{policy_name}",
            body=policy,
        )

    # --- Enrollment ---

    def create_enrollment_token(self, policy_name: str, ttl_hours: int = 1,
                                allow_personal_usage: bool = True) -> dict:
        """Returns {name, value, qrCode, expirationTimestamp, ...}. `qrCode` is a
        JSON string meant to be rendered as a QR image; `value` is the plain enrollment
        token usable in an https://enterprise.google.com/android/enroll?et=<value> link."""
        body = {
            "policyName": f"enterprises/{self.enterprise_id}/policies/{policy_name}",
            "duration": f"{ttl_hours * 3600}s",
            "allowPersonalUsage": "PERSONAL_USAGE_ALLOWED" if allow_personal_usage else "PERSONAL_USAGE_DISALLOWED",
        }
        return self._request(
            "POST", f"enterprises/{self.enterprise_id}/enrollmentTokens", body=body,
        )

    # --- Devices ---

    def list_devices(self) -> list:
        result = self._request("GET", f"enterprises/{self.enterprise_id}/devices")
        return result.get("devices", [])

    def get_device(self, device_name: str) -> dict:
        """device_name is the full resource name: enterprises/{e}/devices/{id}."""
        return self._request("GET", device_name.lstrip("/"))

    def issue_command(self, device_name: str, command_type: str, **extra) -> dict:
        """command_type: LOCK | RESET_PASSWORD | REBOOT | WIPE | START_LOST_MODE |
        STOP_LOST_MODE | CLEAR_APP_DATA | REQUEST_DEVICE_INFO | RELINQUISH_OWNERSHIP.
        Returns immediately with an Operation — the command applies on next device check-in."""
        body = {"type": command_type, **extra}
        return self._request(
            "POST", f"{device_name.lstrip('/')}:issueCommand", body=body,
        )

    def delete_device(self, device_name: str, wipe_data_flags: list = None) -> None:
        params = {}
        if wipe_data_flags:
            params["wipeDataFlags"] = ",".join(wipe_data_flags)
        self._request("DELETE", device_name.lstrip("/"), params=params)
