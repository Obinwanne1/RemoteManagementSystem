"""System information report."""
import platform
import socket
import psutil
from datetime import datetime

print("=" * 50)
print("SYSTEM INFORMATION REPORT")
print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 50)

print(f"\nHostname:     {socket.gethostname()}")
print(f"OS:           {platform.system()} {platform.version()}")
print(f"Architecture: {platform.machine()}")
print(f"Python:       {platform.python_version()}")

cpu = psutil.cpu_percent(interval=1)
mem = psutil.virtual_memory()
print(f"\nCPU Usage:    {cpu}%")
print(f"CPU Cores:    {psutil.cpu_count(logical=True)}")
print(f"RAM Total:    {mem.total / (1024**3):.2f} GB")
print(f"RAM Used:     {mem.used / (1024**3):.2f} GB ({mem.percent}%)")

print("\nDisk Usage:")
for part in psutil.disk_partitions(all=False):
    try:
        usage = psutil.disk_usage(part.mountpoint)
        print(f"  {part.mountpoint}: {usage.used/(1024**3):.1f}/{usage.total/(1024**3):.1f} GB ({usage.percent}%)")
    except Exception:
        pass

uptime_s = int(psutil.time.time() - psutil.boot_time())
d, r = divmod(uptime_s, 86400)
h, r = divmod(r, 3600)
m, _ = divmod(r, 60)
print(f"\nUptime:       {d}d {h}h {m}m")
print("=" * 50)
