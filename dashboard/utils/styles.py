"""Centralized CSS and reusable HTML components for RMM Dashboard."""
import streamlit as st

# ── Color tokens ──────────────────────────────────────────────────────────────
BRAND = {
    "primary":       "#407E3C",
    "primary_dark":  "#2D5C29",
    "primary_light": "#5DB85A",
    "sidebar_bg":    "#0F1B10",
    "bg":            "#F4F6F4",
    "card":          "#FFFFFF",
    "border":        "#DDE8DD",
    "text":          "#1A1A1A",
    "muted":         "#6B7B6B",
    "success":       "#22C55E",
    "warning":       "#F59E0B",
    "danger":        "#EF4444",
    "info":          "#3B82F6",
    "offline":       "#8492A6",
}

STATUS_COLORS = {
    "healthy":  "#22C55E",
    "warning":  "#F59E0B",
    "critical": "#EF4444",
    "offline":  "#8492A6",
    "online":   "#22C55E",
    "unknown":  "#8492A6",
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

# ── Global CSS ────────────────────────────────────────────────────────────────
_GLOBAL_CSS = """
<style>
/* Streamlit chrome removal */
#MainMenu,
footer,
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
button[data-testid="manage-app-button"],
[data-testid="collapsedControl"] {
    display: none !important;
}

header[data-testid="stHeader"] {
    background: transparent;
    height: 0 !important;
}

/* App layout */
.appview-container > section:first-child { padding-top: 0; }
.main .block-container {
    padding-top: 1.75rem;
    padding-bottom: 2rem;
    padding-left: 2.25rem;
    padding-right: 2.25rem;
    max-width: 1600px;
}

/* ── Sidebar ─────────────────────── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0A1409 0%, #0F1B10 40%, #0A1409 100%) !important;
    border-right: 1px solid #1A2E1A !important;
}
[data-testid="stSidebar"] > div {
    background: transparent !important;
    overflow-y: auto !important;
    max-height: 100vh !important;
}
[data-testid="stSidebar"] section { background: transparent !important; }

/* All text inside sidebar: default light green */
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] li,
[data-testid="stSidebar"] a,
[data-testid="stSidebar"] div,
[data-testid="stSidebar"] label {
    color: #C8DCC8 !important;
}

/* Hide default Streamlit auto-generated page nav — we use custom HTML nav */
[data-testid="stSidebarNav"],
[data-testid="stSidebarNavItems"],
section[data-testid="stSidebar"] > div > div > div > ul,
nav[data-testid="stSidebarNav"] { display: none !important; }

/* Nav link container */
[data-testid="stSidebarNavLink"] {
    border-radius: 6px;
    margin: 1px 6px;
    padding: 0.4rem 0.75rem;
    transition: background 0.15s ease;
}
[data-testid="stSidebarNavLink"]:hover {
    background: rgba(64,126,60,0.22) !important;
}
[data-testid="stSidebarNavLink"]:hover p,
[data-testid="stSidebarNavLink"]:hover span,
[data-testid="stSidebarNavLink"]:hover div {
    color: #FFFFFF !important;
}
[data-testid="stSidebarNavLink"][aria-selected="true"] {
    background: rgba(64,126,60,0.32) !important;
    border-left: 3px solid #5DB85A !important;
}
[data-testid="stSidebarNavLink"][aria-selected="true"] p,
[data-testid="stSidebarNavLink"][aria-selected="true"] span,
[data-testid="stSidebarNavLink"][aria-selected="true"] div {
    color: #FFFFFF !important;
}

/* ── Buttons ─────────────────────── */
.stButton > button {
    background: #407E3C;
    color: #FFFFFF;
    border: none;
    border-radius: 7px;
    padding: 0.45rem 1.1rem;
    font-weight: 600;
    font-size: 0.875rem;
    transition: background 0.15s, transform 0.1s, box-shadow 0.15s;
    box-shadow: 0 1px 3px rgba(64,126,60,0.25);
}
.stButton > button:hover {
    background: #4E9848;
    color: #FFFFFF;
    transform: translateY(-1px);
    box-shadow: 0 4px 10px rgba(64,126,60,0.3);
}
.stButton > button:active { transform: translateY(0); }

[data-testid="stSidebar"] .stButton > button {
    background: transparent;
    border: 1px solid #1E3320;
    color: #7A9E7A;
    box-shadow: none;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(64,126,60,0.18);
    color: #D4EED4;
    border-color: #3A6636;
}

/* ── Inputs ──────────────────────── */
.stTextInput > div > div > input {
    border-radius: 7px;
    border: 1.5px solid #DDE8DD;
    padding: 0.5rem 0.75rem;
    font-size: 0.9rem;
    transition: border-color 0.15s, box-shadow 0.15s;
}
.stTextInput > div > div > input:focus {
    border-color: #407E3C;
    box-shadow: 0 0 0 3px rgba(64,126,60,0.12);
}
.stSelectbox > div > div,
.stMultiSelect > div > div {
    border-radius: 7px;
    border-color: #DDE8DD;
}

/* ── st.metric boxes ─────────────── */
[data-testid="stMetric"] {
    background: #FFFFFF;
    border-radius: 10px;
    padding: 1rem 1.25rem 0.9rem;
    border: 1px solid #DDE8DD;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}
[data-testid="stMetricValue"] {
    font-size: 1.9rem !important;
    font-weight: 700 !important;
    color: #1A1A1A !important;
    line-height: 1.15 !important;
}
[data-testid="stMetricLabel"] {
    font-size: 0.72rem !important;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: #6B7B6B !important;
    font-weight: 600 !important;
}
[data-testid="stMetricDelta"] {
    font-size: 0.78rem !important;
}

/* ── Expanders ───────────────────── */
[data-testid="stExpander"] {
    border: 1px solid #DDE8DD !important;
    border-radius: 9px !important;
    overflow: hidden !important;
    margin-bottom: 0.5rem !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
}
[data-testid="stExpander"] > details > summary {
    background: #FAFCFA !important;
    padding: 0.7rem 1rem !important;
}
[data-testid="stExpander"] > details > summary:hover {
    background: #F0F7F0 !important;
}
[data-testid="stExpander"] > details[open] > summary {
    border-bottom: 1px solid #DDE8DD !important;
}

/* ── Tabs ────────────────────────── */
[data-testid="stTabs"] button[role="tab"] {
    border-radius: 7px 7px 0 0;
    font-weight: 500;
    color: #6B7B6B;
}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    color: #407E3C;
    border-bottom: 2px solid #407E3C;
}

/* ── Dataframe / tables ──────────── */
[data-testid="stDataFrame"] {
    border-radius: 9px !important;
    overflow: hidden !important;
    border: 1px solid #DDE8DD !important;
}

/* ── Misc ────────────────────────── */
hr { border-color: #DDE8DD; margin: 1.2rem 0; }
h1 { font-size: 1.55rem !important; font-weight: 700 !important; color: #1A2B1A !important; }
h2 { font-size: 1.15rem !important; font-weight: 600 !important; color: #1A2B1A !important; }
h3 { font-size: 1rem !important; font-weight: 600 !important; color: #2A3B2A !important; }

.stCaption, [data-testid="stCaptionContainer"] {
    color: #6B7B6B !important;
    font-size: 0.8rem !important;
}
</style>
"""

_LOGIN_CSS = """
<style>
/* Login page overrides */
.main .block-container {
    padding-top: 0 !important;
    max-width: 100% !important;
    padding-left: 0 !important;
    padding-right: 0 !important;
}
</style>
"""


def inject_css():
    """Apply global brand CSS. Call at the top of every page."""
    st.markdown(_GLOBAL_CSS, unsafe_allow_html=True)


def inject_login_css():
    """Additional CSS for the login page."""
    st.markdown(_LOGIN_CSS, unsafe_allow_html=True)


# ── HTML component helpers ────────────────────────────────────────────────────

def stat_card(title: str, value, subtitle: str = "", accent: str = "#407E3C", icon: str = "", trend: str = "") -> str:
    """Styled stat card — single-line HTML (no newlines) to avoid Streamlit Markdown parser issues."""
    t_color = "#22C55E" if str(trend).startswith("+") else "#EF4444" if str(trend).startswith("-") else "#6B7B6B"
    trend_html = f'<span style="color:{t_color};font-size:0.78rem;font-weight:600">{trend}</span>' if trend else ""
    sub_html = f'<div style="font-size:0.78rem;color:#6B7B6B;margin-top:4px">{subtitle}</div>' if subtitle else ""
    icon_html = f'<span style="font-size:1.4rem;opacity:0.8;line-height:1">{icon}</span>' if icon else ""
    return (
        f'<div style="background:#FFFFFF;border-radius:12px;padding:1.2rem 1.4rem 1rem;'
        f'border:1px solid #DDE8DD;box-shadow:0 2px 8px rgba(0,0,0,0.05);border-top:3px solid {accent}">'
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:0.5rem">'
        f'<span style="font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#6B7B6B">{title}</span>'
        f'{icon_html}</div>'
        f'<div style="display:flex;align-items:baseline;gap:8px">'
        f'<span style="font-size:2rem;font-weight:700;color:#1A1A1A;line-height:1">{value}</span>'
        f'{trend_html}</div>'
        f'{sub_html}</div>'
    )


def badge(text: str, color: str) -> str:
    return (
        f'<span style="background:{color}1A;color:{color};padding:3px 10px;'
        f'border-radius:20px;font-size:0.72rem;font-weight:700;'
        f'border:1px solid {color}33;white-space:nowrap">{text.upper()}</span>'
    )


def section_header(title: str, subtitle: str = "") -> str:
    sub = f'<span style="display:block;font-size:0.82rem;color:#6B7B6B;margin-top:1px">{subtitle}</span>' if subtitle else ""
    return f'<div style="margin-bottom:0.75rem"><span style="font-size:1rem;font-weight:700;color:#1A2B1A">{title}</span>{sub}</div>'


def device_mini_card(device: dict) -> str:
    """Compact device card — single-line HTML."""
    status = device.get("status", "unknown")
    color = STATUS_COLORS.get(status, "#8492A6")
    dot = "#22C55E" if device.get("is_online", False) else "#8492A6"
    metrics = device.get("latest_metrics") or {}
    cpu  = metrics.get("cpu_pct",  0) or 0
    ram  = metrics.get("ram_pct",  0) or 0
    disk = metrics.get("disk_pct", 0) or 0

    def bar(pct):
        c = "#22C55E" if pct < 75 else ("#F59E0B" if pct < 90 else "#EF4444")
        return f'<div style="background:#EEF2EE;border-radius:3px;height:4px"><div style="background:{c};width:{min(pct,100):.0f}%;height:4px;border-radius:3px"></div></div>'

    return (
        f'<div style="background:#FFF;border-radius:10px;padding:0.85rem 1rem;'
        f'border:1px solid #DDE8DD;box-shadow:0 1px 4px rgba(0,0,0,0.04);margin-bottom:0.4rem">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">'
        f'<div style="display:flex;align-items:center;gap:7px">'
        f'<div style="width:7px;height:7px;border-radius:50%;background:{dot};box-shadow:0 0 5px {dot}88;flex-shrink:0"></div>'
        f'<span style="font-weight:600;color:#1A1A1A;font-size:0.83rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:120px">{device.get("hostname","—")}</span>'
        f'</div>'
        f'<span style="background:{color}15;color:{color};padding:2px 7px;border-radius:20px;font-size:0.65rem;font-weight:700">{status.upper()}</span>'
        f'</div>'
        f'<div style="color:#6B7B6B;font-size:0.72rem;margin-bottom:8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{device.get("ip_address","—")}</div>'
        f'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:5px;font-size:0.7rem;color:#6B7B6B">'
        f'<div>CPU {cpu:.0f}%{bar(cpu)}</div>'
        f'<div>RAM {ram:.0f}%{bar(ram)}</div>'
        f'<div>DSK {disk:.0f}%{bar(disk)}</div>'
        f'</div></div>'
    )


def alert_row(alert: dict) -> str:
    """Alert row — single-line HTML."""
    from utils.formatters import fmt_datetime
    sev = alert.get("severity", "info")
    color = SEVERITY_COLORS.get(sev, "#8492A6")
    status = alert.get("status", "")
    s_color = "#22C55E" if status == "resolved" else "#EF4444"
    hostname = alert.get("device_hostname", "")
    host_part = f' · <b style="color:#1A1A1A">{hostname}</b>' if hostname else ""
    ts = fmt_datetime(alert.get("triggered_at", ""))
    msg = alert.get("message", "—")
    return (
        f'<div style="display:flex;align-items:flex-start;gap:10px;padding:0.65rem 0.85rem;'
        f'border-radius:8px;margin-bottom:0.35rem;background:#FAFCFA;border:1px solid #E8EEE8">'
        f'<div style="width:3px;min-height:36px;border-radius:3px;background:{color};flex-shrink:0;margin-top:2px"></div>'
        f'<div style="flex:1;min-width:0">'
        f'<div style="font-size:0.84rem;font-weight:500;color:#1A1A1A;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{msg}</div>'
        f'<div style="font-size:0.73rem;color:#6B7B6B;margin-top:2px">{ts}{host_part} · <span style="color:{s_color};font-weight:600">{status.upper()}</span></div>'
        f'</div>'
        f'<span style="background:{color}15;color:{color};padding:2px 8px;border-radius:20px;font-size:0.68rem;font-weight:700;white-space:nowrap;flex-shrink:0">{sev.upper()}</span>'
        f'</div>'
    )


def activity_row(item: dict) -> str:
    """Activity row — single-line HTML."""
    from utils.formatters import fmt_datetime
    action = item.get("action", "")
    resource = item.get("resource_type", "")
    ip = item.get("ip_address", "")
    color = {"CREATE": "#22C55E", "UPDATE": "#3B82F6", "DELETE": "#EF4444", "LOGIN": "#8B5CF6"}.get(action.upper(), "#6B7B6B")
    ts = fmt_datetime(item.get("created_at", ""))
    suffix = f" · {ip}" if ip else ""
    return (
        f'<div style="display:flex;align-items:center;gap:10px;padding:0.55rem 0;border-bottom:1px solid #EEF2EE">'
        f'<span style="background:{color}15;color:{color};padding:2px 8px;border-radius:5px;font-size:0.7rem;font-weight:700;min-width:56px;text-align:center;flex-shrink:0">{action}</span>'
        f'<span style="flex:1;font-size:0.83rem;color:#1A1A1A;font-weight:500;min-width:0">{resource}</span>'
        f'<span style="font-size:0.72rem;color:#6B7B6B;white-space:nowrap;flex-shrink:0">{ts}{suffix}</span>'
        f'</div>'
    )


def plotly_layout(fig, height: int = 300, bg: str = "#FFFFFF"):
    """Apply consistent brand styling to a Plotly figure."""
    fig.update_layout(
        height=height,
        margin=dict(t=16, b=16, l=16, r=16),
        paper_bgcolor=bg,
        plot_bgcolor=bg,
        font=dict(family="sans-serif", color="#1A1A1A", size=12),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=11),
        ),
        xaxis=dict(gridcolor="#EEF2EE", linecolor="#DDE8DD"),
        yaxis=dict(gridcolor="#EEF2EE", linecolor="#DDE8DD"),
    )
    return fig
