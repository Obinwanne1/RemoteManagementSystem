"""
Task executor — receives tasks from API task queue and dispatches them.
"""
import logging
from script_runner import run_script

logger = logging.getLogger(__name__)


def execute_task(task: dict, api_client) -> None:
    """Dispatch a single task and post result back to API."""
    task_id = task.get("task_id")
    task_type = task.get("type")
    payload = task.get("payload", {})

    logger.info(f"Executing task {task_id} type={task_type}")

    try:
        if task_type == "run_script":
            result = _handle_script(payload)
        elif task_type == "reboot":
            result = _handle_reboot(payload)
        elif task_type == "shutdown":
            result = _handle_shutdown(payload)
        elif task_type == "delete_temp":
            result = _handle_delete_temp()
        else:
            logger.warning(f"Unknown task type: {task_type}")
            result = {"exit_code": 1, "stderr": f"Unknown task type: {task_type}"}

        api_client.post_task_result(task_id, task_type, result)

    except Exception as e:
        logger.error(f"Task {task_id} failed with exception: {e}")
        api_client.post_task_result(task_id, task_type, {
            "exit_code": 1,
            "stderr": str(e),
        })


def _handle_script(payload: dict) -> dict:
    from script_runner import run_script
    content = payload.get("content", "")
    file_type = payload.get("file_type", "ps1")
    timeout = payload.get("timeout_seconds", 300)
    return run_script(content, file_type, timeout)


def _handle_reboot(payload: dict) -> dict:
    import subprocess
    try:
        subprocess.run(
            ["shutdown", "/r", "/t", "30", "/c", "RMM initiated reboot"],
            capture_output=True, creationflags=0x08000000,
        )
        return {"exit_code": 0, "stdout": "Reboot scheduled in 30 seconds"}
    except Exception as e:
        return {"exit_code": 1, "stderr": str(e)}


def _handle_shutdown(payload: dict) -> dict:
    import subprocess
    try:
        subprocess.run(
            ["shutdown", "/s", "/t", "30", "/c", "RMM initiated shutdown"],
            capture_output=True, creationflags=0x08000000,
        )
        return {"exit_code": 0, "stdout": "Shutdown scheduled in 30 seconds"}
    except Exception as e:
        return {"exit_code": 1, "stderr": str(e)}


def _handle_delete_temp() -> dict:
    import tempfile
    import shutil
    from pathlib import Path
    cleaned = 0
    errors = []
    temp_dir = Path(tempfile.gettempdir())
    for item in temp_dir.iterdir():
        try:
            if item.is_file():
                item.unlink()
                cleaned += 1
            elif item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
                cleaned += 1
        except Exception as e:
            errors.append(str(e))
    return {
        "exit_code": 0,
        "stdout": f"Cleaned {cleaned} items from temp directory",
        "stderr": "\n".join(errors[:10]) if errors else "",
    }
