"""
Terminal worker — polls API for pending remote terminal commands, executes them,
streams output back. Runs as a background daemon thread inside the agent process.
"""
import logging
import subprocess
import threading
import time

import requests

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 3       # seconds between polls when no active session
_ACTIVE_POLL  = 1        # seconds between polls when session is active
_CMD_TIMEOUT  = 120      # max seconds a single command may run


class TerminalWorker:
    def __init__(self, base_url: str, device_id: str, agent_token: str):
        self._base = base_url.rstrip("/")
        self._device_id = device_id
        self._headers = {
            "Authorization": f"Bearer {agent_token}",
            "Content-Type": "application/json",
        }
        self._session = requests.Session()
        self._session.headers.update(self._headers)
        self._stop = threading.Event()

    def start(self):
        t = threading.Thread(target=self._loop, name="terminal-worker", daemon=True)
        t.start()
        logger.info("Terminal worker started")

    def stop(self):
        self._stop.set()

    # ── internal ──────────────────────────────────────────────────────────────

    def _loop(self):
        while not self._stop.is_set():
            try:
                sessions = self._get_sessions()
                had_work = False
                for s in sessions:
                    pending = s.get("pending_command")
                    if pending:
                        had_work = True
                        self._run_command(s["session_id"], pending)
                interval = _ACTIVE_POLL if had_work else _POLL_INTERVAL
            except Exception as exc:
                logger.warning("Terminal worker error: %s", exc)
                interval = _POLL_INTERVAL
            self._stop.wait(interval)

    def _get_sessions(self) -> list:
        url = f"{self._base}/api/terminal/agent/{self._device_id}/sessions"
        try:
            resp = self._session.get(url, timeout=10)
            if resp.status_code == 200:
                return resp.json().get("sessions", [])
        except requests.RequestException as e:
            logger.debug("Terminal poll failed: %s", e)
        return []

    def _mark_running(self, command_id: str) -> bool:
        url = f"{self._base}/api/terminal/agent/{self._device_id}/commands/{command_id}/running"
        try:
            resp = self._session.put(url, timeout=10)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def _post_output(self, command_id: str, content: str, stream: str = "stdout"):
        if not content:
            return
        url = f"{self._base}/api/terminal/agent/{self._device_id}/commands/{command_id}/output"
        try:
            self._session.post(url, json={"content": content, "stream": stream}, timeout=10)
        except requests.RequestException as e:
            logger.debug("Terminal output post failed: %s", e)

    def _mark_done(self, command_id: str, exit_code: int):
        url = f"{self._base}/api/terminal/agent/{self._device_id}/commands/{command_id}/done"
        try:
            self._session.put(url, json={"exit_code": exit_code}, timeout=10)
        except requests.RequestException as e:
            logger.debug("Terminal done failed: %s", e)

    def _run_command(self, session_id: str, cmd_dict: dict):
        command_id = cmd_dict["id"]
        command_text = cmd_dict["command"]

        if not self._mark_running(command_id):
            return  # another worker or stale — skip

        logger.info("Terminal executing cmd=%s: %r", command_id[:8], command_text[:80])

        try:
            proc = subprocess.Popen(
                command_text,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=0x08000000,  # CREATE_NO_WINDOW on Windows
            )

            # Stream stdout line by line with timeout guard
            deadline = time.time() + _CMD_TIMEOUT
            stdout_buf = []
            try:
                for line in proc.stdout:
                    stdout_buf.append(line)
                    if time.time() > deadline:
                        proc.kill()
                        self._post_output(command_id, "\r\n[Killed: command exceeded timeout]\r\n", "system")
                        break
                    # Batch flush every 20 lines to reduce API calls
                    if len(stdout_buf) >= 20:
                        self._post_output(command_id, "".join(stdout_buf), "stdout")
                        stdout_buf = []
            except Exception:
                pass

            if stdout_buf:
                self._post_output(command_id, "".join(stdout_buf), "stdout")

            stderr_out = ""
            try:
                stderr_out = proc.stderr.read()
            except Exception:
                pass

            if stderr_out:
                self._post_output(command_id, stderr_out, "stderr")

            try:
                exit_code = proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                exit_code = -1

        except Exception as exc:
            logger.warning("Terminal command error: %s", exc)
            self._post_output(command_id, f"\r\n[Error: {exc}]\r\n", "system")
            exit_code = -1

        self._mark_done(command_id, exit_code)
