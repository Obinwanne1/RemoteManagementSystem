"""Display formatting utilities."""
from datetime import datetime


STATUS_COLORS = {
    "healthy": "#22C55E",
    "warning": "#F59E0B",
    "critical": "#EF4444",
    "offline": "#8492A6",
    "unknown": "#8492A6",
    "online":  "#22C55E",
}

SEVERITY_COLORS = {
    "info":     "#3B82F6",
    "warning":  "#F59E0B",
    "critical": "#EF4444",
}

PRIORITY_COLORS = {
    "low":      "#8492A6",
    "medium":   "#3B82F6",
    "high":     "#F59E0B",
    "critical": "#EF4444",
}


def fmt_bytes(n: int) -> str:
    if n is None:
        return "—"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def fmt_uptime(seconds: int) -> str:
    if seconds is None:
        return "—"
    d, rem = divmod(int(seconds), 86400)
    h, rem = divmod(rem, 3600)
    m, _ = divmod(rem, 60)
    parts = []
    if d:
        parts.append(f"{d}d")
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    return " ".join(parts) or "< 1m"


def fmt_datetime(iso_str: str) -> str:
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return iso_str


def status_badge(status: str) -> str:
    color = STATUS_COLORS.get(status, "#ADB5BD")
    return f'<span style="background:{color};color:white;padding:2px 8px;border-radius:12px;font-size:0.8em">{status.upper()}</span>'


def pct_color(pct: float) -> str:
    if pct is None:
        return "#8492A6"
    if pct >= 90:
        return "#EF4444"
    if pct >= 75:
        return "#F59E0B"
    return "#22C55E"
