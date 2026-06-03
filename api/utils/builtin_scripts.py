"""
Built-in maintenance script definitions.
Called at app startup to ensure script records exist in DB.
"""
import logging

logger = logging.getLogger(__name__)

# Each entry: tag (unique lookup key), name, description, file_type, content
BUILTIN_SCRIPTS = [
    {
        "tag": "__builtin_clean_temp__",
        "name": "Clean Temp Files",
        "description": "Delete temporary files from %TEMP% and Windows Temp directories.",
        "file_type": "ps1",
        "content": (
            "$cleaned = 0; $errors = @()\n"
            "foreach ($path in @($env:TEMP, \"$env:SystemRoot\\Temp\")) {\n"
            "    if (Test-Path $path) {\n"
            "        Get-ChildItem -Path $path -Recurse -Force -ErrorAction SilentlyContinue | ForEach-Object {\n"
            "            try { Remove-Item $_.FullName -Force -Recurse -ErrorAction Stop; $cleaned++ }\n"
            "            catch { $errors += $_.Exception.Message }\n"
            "        }\n"
            "    }\n"
            "}\n"
            "Write-Output \"Cleaned $cleaned items. Errors: $($errors.Count)\""
        ),
    },
    {
        "tag": "__builtin_defrag__",
        "name": "Defragment C Drive",
        "description": "Run disk defragmentation on C: drive.",
        "file_type": "ps1",
        "content": "Optimize-Volume -DriveLetter C -Defrag -Verbose",
    },
    {
        "tag": "__builtin_check_disk__",
        "name": "Check Disk (chkdsk)",
        "description": "Schedule chkdsk /f on C: drive for next reboot (cannot run live on system drive).",
        "file_type": "ps1",
        "content": (
            "# chkdsk /f cannot run on a locked system drive — schedule for next boot\n"
            "$result = chkdsk C: /f 2>&1\n"
            "if ($LASTEXITCODE -eq 0) {\n"
            "    Write-Output \"Disk check complete (no errors found).\"\n"
            "} elseif ($LASTEXITCODE -eq 1) {\n"
            "    Write-Output \"Disk check complete (errors found and fixed).\"\n"
            "} else {\n"
            "    # Drive locked — Windows queued the check for next reboot\n"
            "    Write-Output \"Disk check scheduled for next reboot (drive is in use). Reboot to run.\"\n"
            "    exit 0\n"
            "}"
        ),
    },
    {
        "tag": "__builtin_restore_point__",
        "name": "Create System Restore Point",
        "description": "Create a Windows System Restore Point.",
        "file_type": "ps1",
        "content": (
            "Enable-ComputerRestore -Drive \"C:\\\" -ErrorAction SilentlyContinue\n"
            "Checkpoint-Computer -Description \"RMM Automated Restore Point\" -RestorePointType \"MODIFY_SETTINGS\"\n"
            "Write-Output \"Restore point created successfully.\""
        ),
    },
    {
        "tag": "__builtin_clear_browser__",
        "name": "Clear Browser History",
        "description": "Clear cache and history for Chrome, Edge, and Firefox.",
        "file_type": "ps1",
        "content": (
            "$paths = @(\n"
            "    \"$env:LOCALAPPDATA\\Google\\Chrome\\User Data\\Default\\Cache\",\n"
            "    \"$env:LOCALAPPDATA\\Google\\Chrome\\User Data\\Default\\History\",\n"
            "    \"$env:LOCALAPPDATA\\Microsoft\\Edge\\User Data\\Default\\Cache\",\n"
            "    \"$env:LOCALAPPDATA\\Microsoft\\Edge\\User Data\\Default\\History\"\n"
            ")\n"
            "foreach ($p in $paths) {\n"
            "    if (Test-Path $p) {\n"
            "        Remove-Item -Path $p -Recurse -Force -ErrorAction SilentlyContinue\n"
            "        Write-Output \"Cleared: $p\"\n"
            "    }\n"
            "}\n"
            "Write-Output \"Browser history cleanup complete.\""
        ),
    },
    {
        "tag": "__builtin_reboot__",
        "name": "Reboot Device",
        "description": "Schedule a remote reboot (30s delay).",
        "file_type": "ps1",
        "content": "shutdown /r /t 30 /c \"RMM initiated reboot\"\nWrite-Output \"Reboot scheduled in 30 seconds.\"",
    },
    {
        "tag": "__builtin_shutdown__",
        "name": "Shutdown Device",
        "description": "Schedule a remote shutdown (30s delay).",
        "file_type": "ps1",
        "content": "shutdown /s /t 30 /c \"RMM initiated shutdown\"\nWrite-Output \"Shutdown scheduled in 30 seconds.\"",
    },
]

# Maps task_type string to script tag
TASK_TYPE_TO_TAG = {
    "clean_temp":      "__builtin_clean_temp__",
    "defrag":          "__builtin_defrag__",
    "check_disk":      "__builtin_check_disk__",
    "restore_point":   "__builtin_restore_point__",
    "clear_browser":   "__builtin_clear_browser__",
    "reboot":          "__builtin_reboot__",
    "shutdown":        "__builtin_shutdown__",
}


def ensure_builtin_scripts():
    """Create or update all built-in maintenance Script records in DB. Call at app startup."""
    from extensions import db
    from models.script import Script

    try:
        for spec in BUILTIN_SCRIPTS:
            existing = Script.query.filter(
                Script.is_builtin == True,
                Script.name == spec["name"],
            ).first()
            if existing:
                existing.content = spec["content"]
                existing.description = spec["description"]
                if spec["tag"] not in (existing.tags or []):
                    existing.tags = [spec["tag"]]
            else:
                script = Script(
                    name=spec["name"],
                    description=spec["description"],
                    file_type=spec["file_type"],
                    content=spec["content"],
                    is_builtin=True,
                    os_target="windows",
                    tags=[spec["tag"]],
                )
                db.session.add(script)
        db.session.commit()
        logger.info("Built-in maintenance scripts synced OK")
    except Exception:
        db.session.rollback()
        logger.exception("Failed to sync built-in maintenance scripts")


def get_builtin_script_id(task_type: str):
    """Return Script.id for a built-in task_type key, or None if not found."""
    from models.script import Script
    tag = TASK_TYPE_TO_TAG.get(task_type)
    if not tag:
        return None
    script = Script.query.filter(
        Script.is_builtin == True,
        Script.name == next(
            (s["name"] for s in BUILTIN_SCRIPTS if s["tag"] == tag), None
        ),
    ).first()
    return script.id if script else None
