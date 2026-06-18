"""
Agent auto-updater.

Flow:
  1. Call check_for_update(client) — returns (latest_version, download_url, checksum) or None
  2. If update available: call download_and_apply(download_url, checksum, agent_dir)
  3. If apply succeeds: call restart_agent() — replaces process in-place via os.execv

Safe practices:
  - Download to temp file, verify SHA256 before touching agent files
  - Extract to temp dir, then copy over existing files
  - Restart only after all files are replaced
"""
import hashlib
import logging
import os
import shutil
import sys
import tempfile
import zipfile

import requests

logger = logging.getLogger(__name__)

_AGENT_DIR = os.path.dirname(os.path.abspath(__file__))


def check_for_update(session: requests.Session, base_url: str, current_version: str) -> dict | None:
    """
    Returns update dict if update is available and download_url is set, else None.
    dict keys: latest_version, download_url, checksum_sha256, changelog
    """
    try:
        url = f"{base_url.rstrip('/')}/api/agents/update/check"
        resp = session.get(url, params={"version": current_version}, timeout=15)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if data.get("update_available") and data.get("download_url"):
            return data
    except Exception as exc:
        logger.debug("Update check failed: %s", exc)
    return None


def download_and_apply(download_url: str, expected_sha256: str, session: requests.Session) -> bool:
    """
    Download zip, verify checksum, extract .py files over agent directory.
    Returns True on success.
    """
    tmp_zip = None
    tmp_dir = None
    try:
        # Download to temp file
        logger.info("Downloading update from %s", download_url)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as f:
            tmp_zip = f.name
            resp = session.get(download_url, stream=True, timeout=120)
            resp.raise_for_status()
            for chunk in resp.iter_content(65536):
                f.write(chunk)

        # Verify checksum
        if expected_sha256:
            actual = _sha256(tmp_zip)
            if actual != expected_sha256:
                logger.error("Update checksum mismatch: expected %s got %s", expected_sha256, actual)
                return False
            logger.info("Checksum verified: %s", actual)

        # Extract to temp dir
        tmp_dir = tempfile.mkdtemp()
        with zipfile.ZipFile(tmp_zip, "r") as zf:
            zf.extractall(tmp_dir)

        # Copy .py files over agent directory
        _copy_update_files(tmp_dir, _AGENT_DIR)
        logger.info("Update applied successfully to %s", _AGENT_DIR)
        return True

    except Exception as exc:
        logger.error("Update failed: %s", exc)
        return False
    finally:
        if tmp_zip and os.path.exists(tmp_zip):
            try:
                os.unlink(tmp_zip)
            except Exception:
                pass
        if tmp_dir and os.path.exists(tmp_dir):
            try:
                shutil.rmtree(tmp_dir)
            except Exception:
                pass


def restart_agent():
    """Replace current process with a fresh copy of itself. Inherited by OS."""
    logger.info("Restarting agent to apply update...")
    try:
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as exc:
        logger.error("os.execv restart failed: %s — spawning subprocess instead", exc)
        import subprocess
        subprocess.Popen([sys.executable] + sys.argv, creationflags=0x00000008)  # DETACHED_PROCESS
        sys.exit(0)


# ── helpers ───────────────────────────────────────────────────────────────────

def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _copy_update_files(src_dir: str, dest_dir: str):
    """
    Recursively copy .py files from src_dir into dest_dir.
    Skips config.ini, rmm_agent.log, and any non-.py files to preserve agent state.
    """
    skip = {"config.ini", "rmm_agent.log", "device_id", "agent_token"}
    for root, dirs, files in os.walk(src_dir):
        # Mirror subdirectory structure
        rel = os.path.relpath(root, src_dir)
        dest_subdir = os.path.join(dest_dir, rel) if rel != "." else dest_dir
        os.makedirs(dest_subdir, exist_ok=True)

        for fname in files:
            if fname in skip:
                continue
            if not fname.endswith(".py") and not fname.endswith(".txt"):
                continue
            src_file = os.path.join(root, fname)
            dst_file = os.path.join(dest_subdir, fname)
            shutil.copy2(src_file, dst_file)
            logger.debug("Updated: %s", dst_file)
