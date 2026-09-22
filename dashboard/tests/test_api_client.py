"""
Starter tests for dashboard/utils/api_client.py's RMMClient.

Covers the (data, error) tuple contract, the 401 -> refresh-token retry
behavior in RMMClient._request(), and HTTP-error formatting. Network calls
are mocked with unittest.mock — no live API/streamlit runtime required.
"""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.api_client import RMMClient  # noqa: E402


def _make_response(status_code=200, json_data=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = 200 <= status_code < 400
    resp.text = text or str(json_data)
    resp.json.return_value = json_data if json_data is not None else {}
    if resp.ok:
        resp.raise_for_status.side_effect = None
    else:
        http_err = requests.HTTPError(response=resp)
        resp.raise_for_status.side_effect = http_err
    return resp


class TestSuccessfulRequest:
    def test_get_returns_data_and_none_error(self):
        client = RMMClient(access_token="tok123")
        ok_resp = _make_response(200, {"hello": "world"})
        with patch.object(requests.Session, "request", return_value=ok_resp):
            data, error = client._get("/api/dashboard/summary")

        assert data == {"hello": "world"}
        assert error is None

    def test_post_returns_data_and_none_error(self):
        client = RMMClient(access_token="tok123")
        ok_resp = _make_response(201, {"id": "abc"})
        with patch.object(requests.Session, "request", return_value=ok_resp):
            data, error = client._post("/api/tickets/", {"title": "test"})

        assert data == {"id": "abc"}
        assert error is None


class TestHttpErrors:
    def test_http_error_returns_none_data_and_formatted_error(self):
        client = RMMClient(access_token="tok123")
        err_resp = _make_response(404, text="Not Found")
        with patch.object(requests.Session, "request", return_value=err_resp):
            data, error = client._get("/api/devices/missing")

        assert data is None
        assert error == "HTTP 404: Not Found"

    def test_500_error_is_not_retried(self):
        """Non-401 HTTP errors should return immediately, not retry 3x."""
        client = RMMClient(access_token="tok123")
        err_resp = _make_response(500, text="boom")
        with patch.object(requests.Session, "request", return_value=err_resp) as mocked:
            data, error = client._get("/api/devices/")

        assert data is None
        assert error == "HTTP 500: boom"
        assert mocked.call_count == 1


class TestUnauthorizedRefreshFlow:
    def test_401_triggers_refresh_and_retries_successfully(self):
        client = RMMClient(access_token="expired-tok", refresh_token="valid-refresh-tok")

        unauthorized_resp = _make_response(401)
        retried_resp = _make_response(200, {"ok": True})
        refresh_resp = _make_response(200, {"access_token": "new-tok"})

        with patch.object(requests.Session, "request", side_effect=[unauthorized_resp, retried_resp]), \
             patch("requests.post", return_value=refresh_resp), \
             patch("streamlit.session_state", {}):
            data, error = client._get("/api/devices/")

        assert data == {"ok": True}
        assert error is None
        assert client._token == "new-tok"

    def test_401_without_refresh_token_returns_session_expired(self):
        client = RMMClient(access_token="expired-tok")  # no refresh_token
        unauthorized_resp = _make_response(401)

        with patch.object(requests.Session, "request", return_value=unauthorized_resp):
            data, error = client._get("/api/devices/")

        assert data is None
        assert error == "SESSION_EXPIRED"

    def test_401_with_failed_refresh_returns_session_expired(self):
        client = RMMClient(access_token="expired-tok", refresh_token="bad-refresh-tok")
        unauthorized_resp = _make_response(401)
        refresh_failure_resp = _make_response(401)

        with patch.object(requests.Session, "request", return_value=unauthorized_resp), \
             patch("requests.post", return_value=refresh_failure_resp):
            data, error = client._get("/api/devices/")

        assert data is None
        assert error == "SESSION_EXPIRED"


class TestConnectionRetry:
    def test_connection_error_retries_then_fails(self):
        client = RMMClient(access_token="tok123")
        with patch.object(requests.Session, "request", side_effect=requests.ConnectionError("refused")) as mocked, \
             patch("time.sleep"):  # skip real backoff delay
            data, error = client._get("/api/dashboard/summary")

        assert data is None
        assert "Connection failed after" in error
        assert mocked.call_count == 3  # len(_BACKOFF)
