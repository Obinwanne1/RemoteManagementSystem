"""
Network scan and agentless device ping-monitoring tasks.
Uses stdlib only (subprocess ping + arp, ipaddress, concurrent.futures).
No nmap or external scanning library required.
"""
import ipaddress
import re
import subprocess
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

# Ensure api/ is in sys.path so Flask app modules are importable from Celery worker
_api_dir = str(Path(__file__).parent.parent)
if _api_dir not in sys.path:
    sys.path.insert(0, _api_dir)

from tasks.celery_app import celery

# Windows: suppress console window for subprocesses (CLAUDE.md rule)
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


# ── Low-level helpers ─────────────────────────────────────────────────────────

def _ping_host(ip: str, timeout_ms: int = 500) -> bool:
    """Return True if host responds to ICMP echo. Works on Windows and Unix."""
    if sys.platform == "win32":
        cmd = ["ping", "-n", "1", "-w", str(timeout_ms), ip]
    else:
        cmd = ["ping", "-c", "1", "-W", "1", ip]
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3,
            creationflags=CREATE_NO_WINDOW,
        )
        return result.returncode == 0
    except Exception:
        return False


def _get_mac_for_ip(ip: str) -> str | None:
    """
    Read MAC from ARP cache after a ping (cache is populated automatically).
    Windows: 'arp -a <ip>' output line looks like:
      '  192.168.1.5          aa-bb-cc-dd-ee-ff     dynamic'
    Unix: 'arp -n <ip>' output looks like:
      '192.168.1.5 ether aa:bb:cc:dd:ee:ff C eth0'
    """
    try:
        if sys.platform == "win32":
            cmd = ["arp", "-a", ip]
        else:
            cmd = ["arp", "-n", ip]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3,
            creationflags=CREATE_NO_WINDOW,
        )
        match = re.search(r"([\da-fA-F]{2}[:\-]){5}[\da-fA-F]{2}", result.stdout)
        if match:
            return match.group(0).replace("-", ":").upper()
    except Exception:
        pass
    return None


def _guess_platform(vendor: str) -> tuple[str, str]:
    """
    Returns (platform, device_type) based on OUI vendor string.
    Conservative: Apple could be Mac or iPhone; mark mobile for common ranges.
    """
    v = vendor.lower()
    if "apple" in v:
        return "ios", "mobile"
    if any(x in v for x in ("samsung", "xiaomi", "huawei", "oppo", "motorola",
                             "oneplus", "realme", "vivo", "zte", "nokia",
                             "google", "pixel")):
        return "android", "mobile"
    if any(x in v for x in ("raspberry pi",)):
        return "linux", "desktop"
    return "unknown", "unknown"


def _upsert_agentless_host(ip: str, mac: str | None, vendor: str,
                           platform: str, device_type: str,
                           customer_id: str | None = None) -> str:
    """
    Persist a discovered host as an agentless Device.
    Returns 'created' or 'updated'.
    Imported inside tasks/routes that run within Flask app context.
    """
    from extensions import db
    from models.device import Device

    now = datetime.now(timezone.utc)
    existing = None

    # Primary key: MAC address (stable across IP changes)
    if mac:
        existing = Device.query.filter_by(mac_address=mac).first()

    # Fallback: match by IP (for hosts with no ARP entry)
    if not existing:
        existing = Device.query.filter_by(ip_address=ip, is_agentless=True).first()

    if existing:
        # Never demote an agent-managed device
        if not existing.is_agentless:
            return "skipped"
        existing.ip_address = ip
        existing.last_seen = now
        existing.is_online = True
        if vendor and vendor != "Unknown":
            existing.vendor = vendor
        db.session.commit()
        return "updated"

    # Create new agentless device
    device = Device(
        hostname=ip,          # use IP as hostname until user renames
        platform=platform,
        device_type=device_type,
        ip_address=ip,
        mac_address=mac,
        vendor=vendor,
        is_agentless=True,
        is_online=True,
        status="unknown",
        last_seen=now,
        customer_id=customer_id,
    )
    db.session.add(device)
    db.session.commit()
    return "created"


# ── Core scan logic (called from Flask thread, runs inside app_context) ────────

def _run_scan(scan_id: str):
    """Pure scan logic — no Celery, no app context. Called from background thread."""
    from extensions import db
    from models.audit import NetworkScan
    from utils.oui import lookup_vendor

    scan = NetworkScan.query.get(scan_id)
    if not scan:
        return

    try:
        net = ipaddress.ip_network(scan.scan_range, strict=False)
    except ValueError as e:
        scan.status = "failed"
        scan.completed_at = datetime.now(timezone.utc)
        scan.discovered_hosts = [{"error": f"Invalid CIDR range: {e}"}]
        db.session.commit()
        return

    hosts_iter = list(net.hosts())
    if len(hosts_iter) > 254:
        scan.status = "failed"
        scan.completed_at = datetime.now(timezone.utc)
        scan.discovered_hosts = [{"error": "Range too large — use /24 or smaller"}]
        db.session.commit()
        return

    discovered = []
    created_count = 0

    with ThreadPoolExecutor(max_workers=50) as pool:
        futures = {pool.submit(_ping_host, str(ip)): str(ip) for ip in hosts_iter}
        for future in as_completed(futures):
            ip = futures[future]
            try:
                alive = future.result()
            except Exception:
                alive = False

            if not alive:
                continue

            mac = _get_mac_for_ip(ip)
            vendor = lookup_vendor(mac) if mac else "Unknown"
            platform, device_type = _guess_platform(vendor)

            discovered.append({
                "ip": ip,
                "mac": mac,
                "vendor": vendor,
                "platform": platform,
                "device_type": device_type,
                "status": "up",
            })

            result = _upsert_agentless_host(
                ip=ip, mac=mac, vendor=vendor,
                platform=platform, device_type=device_type,
                customer_id=scan.customer_id,
            )
            if result == "created":
                created_count += 1

    scan.status = "completed"
    scan.completed_at = datetime.now(timezone.utc)
    scan.discovered_hosts = discovered
    scan.new_devices_count = created_count
    db.session.commit()


# ── Celery tasks (kept for beat schedule / future use) ─────────────────────────

@celery.task(name="tasks.network_tasks.run_network_scan", bind=True, max_retries=2)
def run_network_scan(self, scan_id: str):
    """Celery wrapper — delegates to _run_scan inside a Flask app context."""
    import os, sys
    from pathlib import Path
    _api = str(Path(__file__).resolve().parent.parent)
    sys.path.insert(0, _api)
    os.chdir(_api)
    from app import create_app
    with create_app().app_context():
        _run_scan(scan_id)


@celery.task(name="tasks.network_tasks.ping_agentless_devices", bind=True)
def ping_agentless_devices(self):
    """
    Ping all known agentless devices and update online/offline status.
    Runs every 5 minutes via Celery beat.
    """
    import os, sys
    from pathlib import Path
    _api = str(Path(__file__).resolve().parent.parent)
    sys.path.insert(0, _api)
    os.chdir(_api)

    from app import create_app
    from extensions import db
    from models.device import Device

    app = create_app()
    with app.app_context():
        now = datetime.now(timezone.utc)
        devices = Device.query.filter_by(is_agentless=True).filter(
            Device.ip_address.isnot(None)
        ).all()

        for device in devices:
            alive = _ping_host(device.ip_address)
            if alive:
                device.is_online = True
                device.last_seen = now
            else:
                if device.last_seen:
                    age_seconds = (now - device.last_seen.replace(tzinfo=timezone.utc)
                                   if device.last_seen.tzinfo is None
                                   else (now - device.last_seen)).total_seconds()
                    if age_seconds > 600:
                        device.is_online = False
                else:
                    device.is_online = False

        db.session.commit()
