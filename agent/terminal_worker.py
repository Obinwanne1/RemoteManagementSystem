"""
Terminal worker — polls API for pending remote terminal commands, executes them,
streams output back. Runs as a background daemon thread inside the agent process.
"""
import locale
import logging
import platform
import subprocess
import threading
import time

import requests


def _decode_output(raw: bytes) -> str:
    """Decode subprocess bytes: UTF-8 first, fall back to system code page."""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        enc = locale.getpreferredencoding(False) or "cp1252"
        return raw.decode(enc, errors="replace")

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 3       # seconds between polls when no active session

_IS_WINDOWS = platform.system() == "Windows"


def _build_argv(command_text: str) -> list:
    """Return explicit shell argv instead of relying on shell=True (cmd.exe)."""
    if _IS_WINDOWS:
        return ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command_text]
    return ["bash", "-c", command_text]


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

        proc = None
        exit_code = -1
        try:
            proc = subprocess.Popen(
                _build_argv(command_text),
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=0x08000000 if _IS_WINDOWS else 0,
            )

            # Thread-level kill timer — guarantees proc dies even if stdout loop hangs
            def _kill_on_timeout():
                try:
                    proc.kill()
                    self._post_output(command_id, "\r\n[Killed: command exceeded timeout]\r\n", "system")
                except Exception:
                    pass

            kill_timer = threading.Timer(_CMD_TIMEOUT, _kill_on_timeout)
            kill_timer.daemon = True
            kill_timer.start()

            try:
                stdout_buf = []
                for raw_line in proc.stdout:
                    line = _decode_output(raw_line)
                    stdout_buf.append(line)
                    if len(stdout_buf) >= 20:
                        self._post_output(command_id, "".join(stdout_buf), "stdout")
                        stdout_buf = []
                if stdout_buf:
                    self._post_output(command_id, "".join(stdout_buf), "stdout")
            except Exception:
                pass
            finally:
                kill_timer.cancel()

            stderr_out = ""
            try:
                stderr_out = _decode_output(proc.stderr.read())
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
            if proc:
                try:
                    proc.kill()
                except Exception:
                    pass

        self._mark_done(command_id, exit_code)
