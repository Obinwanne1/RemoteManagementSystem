"""Dashboard Overview — live metrics, charts, alerts, activity feed."""
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from utils.auth import require_auth
from utils.nav import render_sidebar
from utils.cached_calls import (
    cached_summary, cached_health_map, cached_recent_alerts,
    cached_activity_feed, cached_recent_events,
)
from utils.styles import (
    inject_css, stat_card, alert_row, activity_row,
    plotly_layout, section_header, BRAND, STATUS_COLORS,
)
from utils.formatters import fmt_datetime

st.set_page_config(page_title="Overview — RMM", layout="wide")
inject_css()

client = require_auth()
render_sidebar()

_tok = st.session_state.get("access_token", "")

# ── Summary ───────────────────────────────────────────────────────────────────
with st.spinner("Loading dashboard..."):
    summary, err = cached_summary(_tok)
if err:
    st.warning(f"Could not load dashboard summary — {err}")
    if st.button("Retry", icon=":material/refresh:"):
        st.cache_data.clear()
        st.rerun()
    st.stop()

d = summary["devices"]
a = summary["alerts"]
t = summary["tickets"]

_title_col, _refresh_col = st.columns([8, 1])
with _title_col:
    st.markdown("""
    <div style="margin-bottom:0.25rem">
        <h1 style="margin:0">Dashboard Overview</h1>
        <p style="color:#6B7B6B;margin:2px 0 0;font-size:0.88rem">
            Live system health · click ⟳ to refresh
        </p>
    </div>
    """, unsafe_allow_html=True)
with _refresh_col:
    st.markdown("<div style='padding-top:0.6rem'></div>", unsafe_allow_html=True)
    if st.button("Refresh", key="dash_refresh", type="primary", use_container_width=True, icon=":material/refresh:"):
        st.rerun()

st.divider()

# ── Stat cards ────────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
crit_d = d.get("critical", 0)
warn_d = d.get("warning", 0)

with c1:
    st.markdown(stat_card("Total Devices", d["total"], icon="<i class='fa-solid fa-desktop'></i>"), unsafe_allow_html=True)
with c2:
    st.markdown(stat_card("Online", d["online"],
                           f"{d.get('offline',0)} offline",
                           BRAND["success"], "<i class='fa-solid fa-circle' style='color:#22C55E'></i>"), unsafe_allow_html=True)
with c3:
    st.markdown(stat_card("Warning", warn_d,
                           "degraded performance" if warn_d else "none",
                           BRAND["warning"] if warn_d else BRAND["success"],
                           "<i class='fa-solid fa-triangle-exclamation'></i>" if warn_d else "<i class='fa-solid fa-circle-check'></i>"), unsafe_allow_html=True)
with c4:
    st.markdown(stat_card("Critical Devices", crit_d,
                           "needs attention" if crit_d else "all clear",
                           BRAND["danger"] if crit_d else BRAND["success"],
                           "<i class='fa-solid fa-circle-xmark'></i>" if crit_d else "<i class='fa-solid fa-circle-check'></i>"), unsafe_allow_html=True)
with c5:
    open_a = a.get("open", 0)
    st.markdown(stat_card("Open Alerts", open_a,
                           f"{a.get('critical',0)} critical" if open_a else "none active",
                           BRAND["warning"] if open_a else BRAND["success"],
                           "<i class='fa-solid fa-bell'></i>"), unsafe_allow_html=True)

st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

# ── Ticket health strip ───────────────────────────────────────────────────────
t_unassigned  = t.get("unassigned", 0)
t_sla         = t.get("sla_breached", 0)
t_critical    = t.get("critical", 0)
_tc1, _tc2, _tc3, _tc4 = st.columns(4)
with _tc1:
    st.markdown(stat_card("Open Tickets", t["open"], "active workload",
                           BRAND["info"], "<i class='fa-solid fa-ticket'></i>"), unsafe_allow_html=True)
with _tc2:
    st.markdown(stat_card("Unassigned", t_unassigned,
                           "needs owner" if t_unassigned else "all assigned",
                           BRAND["warning"] if t_unassigned else BRAND["success"],
                           "<i class='fa-solid fa-user-slash'></i>" if t_unassigned else "<i class='fa-solid fa-user-check'></i>"), unsafe_allow_html=True)
with _tc3:
    st.markdown(stat_card("SLA Breached", t_sla,
                           "past due" if t_sla else "all on time",
                           BRAND["danger"] if t_sla else BRAND["success"],
                           "<i class='fa-solid fa-clock'></i>"), unsafe_allow_html=True)
with _tc4:
    st.markdown(stat_card("Critical Tickets", t_critical,
                           "urgent priority" if t_critical else "none critical",
                           BRAND["danger"] if t_critical else BRAND["success"],
                           "<i class='fa-solid fa-fire'></i>"), unsafe_allow_html=True)

st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)

# ── Row 2: Donut + Device Health Map ─────────────────────────────────────────
left, right = st.columns([1, 2.2])

with left:
    st.markdown("""
    <div style="background:#FFF;border-radius:12px;padding:1.25rem 1.25rem 0.75rem;
                border:1px solid #DDE8DD;box-shadow:0 2px 8px rgba(0,0,0,0.05)">
        <div style="font-size:0.85rem;font-weight:700;color:#1A2B1A;margin-bottom:0.25rem">
            Device Status
        </div>
    """, unsafe_allow_html=True)

    healthy = max(0, d["total"] - d.get("offline", 0) - crit_d - warn_d)
    labels  = ["Healthy", "Warning", "Critical", "Offline"]
    values  = [healthy, warn_d, crit_d, d.get("offline", 0)]
    colors  = ["#22C55E", "#F59E0B", "#EF4444", "#8492A6"]

    # Remove zero-value slices
    pairs   = [(l, v, c) for l, v, c in zip(labels, values, colors) if v > 0]
    if pairs:
        l2, v2, c2 = zip(*pairs)
        fig = go.Figure(go.Pie(
            labels=list(l2), values=list(v2),
            hole=0.62,
            marker=dict(colors=list(c2), line=dict(color="#FFF", width=2)),
            textfont=dict(size=11),
            hovertemplate="%{label}: %{value}<extra></extra>",
        ))
        fig.add_annotation(
            text=f"<b>{d['total']}</b><br><span style='font-size:9px'>devices</span>",
            x=0.5, y=0.5, showarrow=False, font=dict(size=14, color="#1A1A1A"),
        )
        plotly_layout(fig, height=260)
        fig.update_layout(
            showlegend=True,
            legend=dict(orientation="h", yanchor="top", y=-0.05, xanchor="center", x=0.5, font=dict(size=10)),
            margin=dict(t=8, b=30, l=8, r=8),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No devices yet.")

    st.markdown("</div>", unsafe_allow_html=True)

with right:
    st.markdown("""
    <div style="background:#FFF;border-radius:12px;padding:1.25rem;
                border:1px solid #DDE8DD;box-shadow:0 2px 8px rgba(0,0,0,0.05)">
        <div style="font-size:0.85rem;font-weight:700;color:#1A2B1A;margin-bottom:0.75rem">
            Device Health Map
        </div>
    """, unsafe_allow_html=True)

    health, herr = cached_health_map(_tok)
    if herr:
        st.warning(f"Health map unavailable: {herr}")
    elif not health:
        st.markdown("""
        <div style="text-align:center;padding:2rem;color:#6B7B6B;font-size:0.88rem">
            No devices registered yet.<br>
            <span style="font-size:0.8rem">Deploy the agent to see devices here.</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        # Inject CSS — card buttons scoped to main content area only (not sidebar)
        st.markdown("""<style>
        section[data-testid="stMain"] button[kind="secondary"] {
            background:#FFF !important;border:1px solid #DDE8DD !important;
            border-radius:10px !important;padding:0.75rem 1rem !important;
            text-align:left !important;box-shadow:0 1px 4px rgba(0,0,0,0.04) !important;
            height:auto !important;min-height:88px !important;width:100% !important;
            color:#1A1A1A !important;line-height:1.5 !important;
            transition:border-color 0.15s,box-shadow 0.15s !important;
        }
        section[data-testid="stMain"] button[kind="secondary"]:hover {
            border-color:#407E3C !important;
            box-shadow:0 4px 16px rgba(64,126,60,0.18) !important;
            background:#F8FBF8 !important;
        }
        section[data-testid="stMain"] button[kind="secondary"] p {
            font-size:0.82rem !important;color:#1A1A1A !important;
        }
        </style>""", unsafe_allow_html=True)

        _SCOL = {
            "healthy": "#22C55E", "warning": "#F59E0B",
            "critical": "#EF4444", "offline": "#8492A6", "unknown": "#8492A6",
        }
        COLS = 4
        for i in range(0, len(health), COLS):
            row_devs = health[i:i + COLS]
            cols = st.columns(COLS)
            for j, dev in enumerate(row_devs):
                with cols[j]:
                    online = dev.get("is_online", False)
                    status = dev.get("status", "unknown")
                    hostname = dev.get("hostname", "—")
                    dot = "●" if online else "○"
                    label = f"{dot} **{hostname}**\n{status.upper()}"
                    if st.button(label, key=f"hm_{dev.get('id',f'{i}{j}')}",
                                 use_container_width=True,
                                 help="Click to view device in Devices page"):
                        st.session_state["_nav_device"] = str(dev.get("id", ""))
                        st.switch_page("pages/04_Devices.py")

    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)

# ── Row 3: Alerts + Activity ──────────────────────────────────────────────────
col_a, col_b = st.columns(2)

with col_a:
    st.markdown("""
    <div style="background:#FFF;border-radius:12px;padding:1.25rem 1.25rem 0.75rem;
                border:1px solid #DDE8DD;box-shadow:0 2px 8px rgba(0,0,0,0.05)">
        <div style="font-size:0.85rem;font-weight:700;color:#1A2B1A;margin-bottom:0.75rem">
            Recent Alerts
        </div>
    """, unsafe_allow_html=True)

    alerts, aerr = cached_recent_alerts(_tok)
    if aerr:
        st.warning(f"Could not load alerts: {aerr}")
    elif not alerts:
        st.markdown("""
        <div style="text-align:center;padding:1.5rem;color:#22C55E;font-size:0.9rem">
            <i class="fa-solid fa-circle-check" style="color:#22C55E"></i>&nbsp;No recent alerts — all systems healthy
        </div>
        """, unsafe_allow_html=True)
    else:
        html = "".join(alert_row(a) for a in alerts[:10])
        st.markdown(html, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

with col_b:
    st.markdown("""
    <div style="background:#FFF;border-radius:12px;padding:1.25rem 1.25rem 0.75rem;
                border:1px solid #DDE8DD;box-shadow:0 2px 8px rgba(0,0,0,0.05)">
        <div style="font-size:0.85rem;font-weight:700;color:#1A2B1A;margin-bottom:0.75rem">
            Activity Feed
        </div>
    """, unsafe_allow_html=True)

    feed, ferr = cached_activity_feed(_tok)
    if ferr:
        st.warning(f"Could not load activity: {ferr}")
    elif not feed:
        st.markdown("""
        <div style="text-align:center;padding:1.5rem;color:#6B7B6B;font-size:0.88rem">
            No recent activity logged.
        </div>
        """, unsafe_allow_html=True)
    else:
        html = "".join(activity_row(item) for item in feed[:12])
        st.markdown(html, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

# ── Live Events feed ──────────────────────────────────────────────────────────
st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
st.markdown(
    '<div style="background:#FFF;border-radius:12px;padding:1.25rem;'
    'border:1px solid #DDE8DD;box-shadow:0 2px 8px rgba(0,0,0,0.05)">'
    '<div style="font-size:0.85rem;font-weight:700;color:#1A2B1A;margin-bottom:0.75rem">'
    '⚡ Live Events <span style="font-size:0.7rem;font-weight:400;color:#6B7B6B;margin-left:6px">'
    '— last 20 system events (auto-refreshes every 30s)</span></div>',
    unsafe_allow_html=True,
)

_ev_data, _ev_err = cached_recent_events(_tok, limit=20)
_events = _ev_data if isinstance(_ev_data, list) else []

_EVENT_ICONS = {
    "device_online":  ("🟢", "#22C55E"),
    "device_offline": ("🔴", "#EF4444"),
    "device_status":  ("🟡", "#F59E0B"),
    "new_alert":      ("🚨", "#EF4444"),
    "new_ticket":     ("🎫", "#3B82F6"),
}

if _ev_err or not _events:
    st.markdown(
        '<div style="text-align:center;padding:1.5rem;color:#6B7B6B;font-size:0.85rem">'
        + ("No recent events. Redis may be unavailable." if _ev_err else "No events yet — events appear here in real time.")
        + "</div>",
        unsafe_allow_html=True,
    )
else:
    ev_html = []
    for ev in _events:
        ev_type = ev.get("type", "")
        ev_data = ev.get("data", {})
        ev_ts = (ev.get("ts") or "")[:19].replace("T", " ")
        icon, color = _EVENT_ICONS.get(ev_type, ("ℹ️", "#6B7B6B"))

        if ev_type == "device_online":
            msg = f"{ev_data.get('hostname','?')} came online"
        elif ev_type == "device_offline":
            msg = f"{ev_data.get('hostname','?')} went offline"
        elif ev_type == "device_status":
            msg = f"{ev_data.get('hostname','?')} status → {ev_data.get('status','?')}"
        elif ev_type == "new_alert":
            msg = f"Alert: {ev_data.get('rule','?')} on {ev_data.get('device','?')} [{ev_data.get('severity','?')}]"
        elif ev_type == "new_ticket":
            msg = f"Ticket: {ev_data.get('title','?')} [{ev_data.get('priority','?')}]"
        else:
            msg = ev_type

        ev_html.append(
            f'<div style="display:flex;align-items:center;gap:10px;padding:0.35rem 0;'
            f'border-bottom:1px solid #F0F4F0">'
            f'<span style="font-size:1rem">{icon}</span>'
            f'<span style="flex:1;font-size:0.82rem;color:#1A1A1A">{msg}</span>'
            f'<span style="font-size:0.72rem;color:#8492A6;white-space:nowrap">{ev_ts} UTC</span>'
            f'</div>'
        )
    st.markdown("".join(ev_html), unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)

# ── Auto-refresh every 30s ────────────────────────────────────────────────────
import time as _time
_time.sleep(30)
st.rerun()
