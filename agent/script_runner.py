"""
Script execution sandbox.
Runs .bat, .ps1, .py scripts with timeout and output capture.
"""
import subprocess
import tempfile
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_OUTPUT_BYTES = 65536  # 64KB
CREATE_NO_WINDOW = 0x08000000


def run_script(content: str, file_type: str, timeout_seconds: int = 300) -> dict:
    """
    Write script content to temp file and execute it.
    Returns dict with exit_code, stdout, stderr.
    """
    suffix = f".{file_type}"
    tmp_path = None
    try:
        # Write script to temp file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=suffix, delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            tmp_path = f.name

        cmd = _build_command(tmp_path, file_type)
        if cmd is None:
            return {"exit_code": 1, "stdout": "", "stderr": f"Unsupported file type: {file_type}"}

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            creationflags=CREATE_NO_WINDOW,
        )

        stdout = result.stdout[:MAX_OUTPUT_BYTES]
        stderr = result.stderr[:MAX_OUTPUT_BYTES]

        return {
            "exit_code": result.returncode,
            "stdout": stdout,
            "stderr": stderr,
        }

    except subprocess.TimeoutExpired:
        logger.warning(f"Script timed out after {timeout_seconds}s")
        return {
            "exit_code": 124,
            "stdout": "",
            "stderr": f"Script timed out after {timeout_seconds} seconds",
        }
    except Exception as e:
        logger.error(f"Script execution error: {e}")
        return {"exit_code": 1, "stdout": "", "stderr": str(e)}
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


def _build_command(script_path: str, file_type: str) -> list | None:
    if file_type == "bat":
        return ["cmd.exe", "/c", script_path]
    elif file_type == "ps1":
        return [
            "powershell.exe",
            "-NonInteractive",
            "-ExecutionPolicy", "RemoteSigned",
            "-File", script_path,
        ]
    elif file_type == "py":
        import sys
        return [sys.executable, script_path]
    return None
