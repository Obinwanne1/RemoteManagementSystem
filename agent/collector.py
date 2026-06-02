"""
System metrics and hardware info collector.
Uses psutil for cross-platform metrics; WMI for Windows-specific hardware data.
"""
import platform
import socket
import time
import uuid as uuid_lib
import logging
from pathlib import Path

import psutil

logger = logging.getLogger(__name__)


def get_hardware_info() -> dict:
    """Collect static hardware/OS info for device registration."""
    info = {
        "hostname": socket.gethostname(),
        "platform": "windows",
        "os_name": platform.system(),
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "cpu_cores": psutil.cpu_count(logical=True),
        "ram_gb": round(psutil.virtual_memory().total / (1024 ** 3), 2),
        "mac_address": _get_primary_mac(),
        "ip_address": _get_local_ip(),
        "agent_version": "1.0.0",
    }

    # Windows-specific via WMI
    try:
        import wmi
        c = wmi.WMI()
        cpus = c.Win32_Processor()
        if cpus:
            info["cpu_model"] = cpus[0].Name.strip()

        bios = c.Win32_BIOS()
        if bios:
            info["serial_number"] = bios[0].SerialNumber.strip()

        os_info = c.Win32_OperatingSystem()
        if os_info:
            info["os_build"] = os_info[0].BuildNumber
            info["os_name"] = os_info[0].Caption.strip()
            info["os_version"] = os_info[0].Version
    except Exception as e:
        logger.warning(f"WMI collection failed (non-fatal): {e}")

    return info


def get_metrics() -> dict:
    """Collect current system metrics for heartbeat payload."""
    cpu_pct = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()
    boot_time = psutil.boot_time()
    uptime = psutil.time.time() - boot_time

    # Primary disk (C: on Windows, / on Linux)
    primary_disk = _get_primary_disk()

    # Network delta (since process start — cumulative counters)
    net = psutil.net_io_counters()

    # Per-drive disk usage
    disks = _get_all_disks()

    # Battery
    battery = _get_battery()

    # Top processes by CPU
    top_procs = _get_top_processes()

    return {
        "cpu_pct": round(cpu_pct, 1),
        "ram_pct": round(mem.percent, 1),
        "ram_used_gb": round(mem.used / (1024 ** 3), 2),
        "disk_pct": primary_disk.get("percent", 0),
        "disk_used_gb": primary_disk.get("used_gb", 0),
        "disk_total_gb": primary_disk.get("total_gb", 0),
        "network_bytes_sent": net.bytes_sent,
        "network_bytes_recv": net.bytes_recv,
        "uptime_seconds": int(uptime),
        "disks": disks,
        "top_processes": top_procs,
        **battery,
    }


def get_installed_software() -> list:
    """Get list of installed software from Windows registry and winget."""
    software = []

    # Registry-based (most reliable)
    try:
        software.extend(_get_registry_software())
    except Exception as e:
        logger.warning(f"Registry software collection failed: {e}")

    # Winget
    try:
        software.extend(_get_winget_software())
    except Exception as e:
        logger.debug(f"Winget not available: {e}")

    # Deduplicate by name
    seen = set()
    unique = []
    for item in software:
        key = item["name"].lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)

    return unique


def _get_primary_mac() -> str:
    try:
        mac = hex(uuid_lib.getnode())[2:].upper().zfill(12)
        return ":".join(mac[i:i+2] for i in range(0, 12, 2))
    except Exception:
        return "00:00:00:00:00:00"


def _get_local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def _get_primary_disk() -> dict:
    try:
        usage = psutil.disk_usage("C:\\")
        return {
            "percent": round(usage.percent, 1),
            "used_gb": round(usage.used / (1024 ** 3), 2),
            "total_gb": round(usage.total / (1024 ** 3), 2),
        }
    except Exception:
        try:
            usage = psutil.disk_usage("/")
            return {
                "percent": round(usage.percent, 1),
                "used_gb": round(usage.used / (1024 ** 3), 2),
                "total_gb": round(usage.total / (1024 ** 3), 2),
            }
        except Exception:
            return {}


def _get_all_disks() -> list:
    disks = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disks.append({
                "device": part.device,
                "mountpoint": part.mountpoint,
                "fstype": part.fstype,
                "total_gb": round(usage.total / (1024 ** 3), 2),
                "used_gb": round(usage.used / (1024 ** 3), 2),
                "free_gb": round(usage.free / (1024 ** 3), 2),
                "percent": round(usage.percent, 1),
            })
        except Exception:
            continue
    return disks


def _get_battery() -> dict:
    try:
        batt = psutil.sensors_battery()
        if batt:
            return {
                "battery_pct": round(batt.percent, 1),
                "battery_plugged": batt.power_plugged,
            }
    except Exception:
        pass
    return {"battery_pct": None, "battery_plugged": None}


def _get_top_processes(n=5) -> list:
    try:
        procs = []
        deadline = time.monotonic() + 3.0
        max_scan = 200
        scanned = 0
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            if time.monotonic() > deadline or scanned >= max_scan:
                break
            scanned += 1
            try:
                info = proc.info
                procs.append({
                    "pid": info["pid"],
                    "name": info["name"],
                    "cpu_pct": round(info["cpu_percent"] or 0, 1),
                    "mem_pct": round(info["memory_percent"] or 0, 1),
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return sorted(procs, key=lambda x: x["cpu_pct"], reverse=True)[:n]
    except Exception:
        return []


def _get_registry_software() -> list:
    import winreg
    software = []
    deadline = time.monotonic() + 20.0
    keys = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    for hive, key_path in keys:
        if time.monotonic() > deadline:
            logger.warning("Registry enumeration deadline reached — results may be partial")
            break
        try:
            with winreg.OpenKey(hive, key_path) as key:
                for i in range(winreg.QueryInfoKey(key)[0]):
                    if time.monotonic() > deadline:
                        logger.warning("Registry enumeration deadline reached — results may be partial")
                        break
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        with winreg.OpenKey(key, subkey_name) as subkey:
                            name = _reg_val(subkey, "DisplayName")
                            if not name:
                                continue
                            software.append({
                                "name": name,
                                "version": _reg_val(subkey, "DisplayVersion"),
                                "publisher": _reg_val(subkey, "Publisher"),
                                "install_date": _reg_val(subkey, "InstallDate"),
                                "source": "registry",
                            })
                    except Exception:
                        continue
        except Exception:
            continue
    return software


def _reg_val(key, name: str):
    try:
        import winreg
        val, _ = winreg.QueryValueEx(key, name)
        return str(val).strip() if val else None
    except Exception:
        return None


def _get_winget_software() -> list:
    import subprocess
    result = subprocess.run(
        ["winget", "list", "--accept-source-agreements"],
        capture_output=True, text=True, encoding="utf-8",
        timeout=30, creationflags=0x08000000,  # CREATE_NO_WINDOW
    )
    if result.returncode != 0:
        return []
    lines = result.stdout.strip().splitlines()
    software = []
    for line in lines[3:]:  # Skip header rows
        parts = line.split()
        if len(parts) >= 2:
            software.append({
                "name": " ".join(parts[:-2]) if len(parts) > 2 else parts[0],
                "version": parts[-2] if len(parts) > 1 else None,
                "source": "winget",
            })
    return software
