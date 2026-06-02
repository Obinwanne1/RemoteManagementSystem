"""
Task executor — receives tasks from API task queue and dispatches them.
"""
import json
import logging
import time
from pathlib import Path

from script_runner import run_script

logger = logging.getLogger(__name__)

QUEUE_PATH = Path(__file__).parent / "pending_results.json"
MAX_QUEUE = 100


def execute_task(task: dict, api_client) -> None:
    """Dispatch a single task and post result back to API."""
    task_id = task.get("task_id")
    task_type = task.get("type")
    payload = task.get("payload", {})

    logger.info("Executing task %s type=%s", task_id, task_type)

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
            logger.warning("Unknown task type: %s", task_type)
            result = {"exit_code": 1, "stderr": f"Unknown task type: {task_type}"}

        ok = api_client.post_task_result(task_id, task_type, result)
        if not ok:
            _enqueue_result(task_id, task_type, result)

    except Exception as e:
        logger.error("Task %s failed with exception: %s", task_id, e)
        error_result = {"exit_code": 1, "stderr": str(e)}
        ok = api_client.post_task_result(task_id, task_type, error_result)
        if not ok:
            _enqueue_result(task_id, task_type, error_result)


def flush_pending_queue(api_client) -> int:
    """Attempt to deliver queued task results. Returns count flushed."""
    if not QUEUE_PATH.exists():
        return 0
    try:
        with open(str(QUEUE_PATH), encoding="utf-8") as f:
            queue = json.load(f)
    except Exception:
        return 0

    if not queue:
        return 0

    remaining = []
    flushed = 0
    for entry in queue:
        ok = api_client.post_task_result(entry["task_id"], entry["type"], entry["result"])
        if ok:
            flushed += 1
        else:
            remaining.append(entry)

    try:
        with open(str(QUEUE_PATH), "w", encoding="utf-8") as f:
            json.dump(remaining, f)
    except Exception as e:
        logger.error("Failed to write pending queue: %s", e)

    return flushed


def _enqueue_result(task_id: str, task_type: str, result: dict) -> None:
    """Persist a failed task result for later delivery."""
    entry = {"task_id": task_id, "type": task_type, "result": result, "queued_at": time.time()}
    try:
        if QUEUE_PATH.exists():
            with open(str(QUEUE_PATH), encoding="utf-8") as f:
                queue = json.load(f)
        else:
            queue = []
        queue.append(entry)
        if len(queue) > MAX_QUEUE:
            queue = queue[-MAX_QUEUE:]  # drop oldest
        with open(str(QUEUE_PATH), "w", encoding="utf-8") as f:
            json.dump(queue, f)
        logger.warning("Task result queued locally (delivery failed): task_id=%s", task_id)
    except Exception as e:
        logger.error("Failed to enqueue result: %s", e)


def _handle_script(payload: dict) -> dict:
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
    import shutil
    import tempfile
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
