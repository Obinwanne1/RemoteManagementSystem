"""Dashboard Overview — live metrics, charts, alerts, activity feed."""
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from utils.auth import require_auth
from utils.nav import render_sidebar
from utils.styles import (
    inject_css, stat_card, alert_row, activity_row,
    device_mini_card, plotly_layout, section_header, BRAND, STATUS_COLORS,
)
from utils.formatters import fmt_datetime

st.set_page_config(page_title="Overview — RMM", layout="wide")
inject_css()

client = require_auth()
render_sidebar()

# ── Summary ───────────────────────────────────────────────────────────────────
with st.spinner("Loading dashboard..."):
    summary, err = client.get_summary()
if err:
    st.warning(f"Could not load dashboard summary — {err}")
    if st.button("🔄 Retry"):
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
    if st.button("⟳ Refresh", key="dash_refresh", use_container_width=True):
        st.rerun()

st.divider()

# ── Stat cards ────────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
crit_d = d.get("critical", 0)
warn_d = d.get("warning", 0)

with c1:
    st.markdown(stat_card("Total Devices", d["total"], icon="💻"), unsafe_allow_html=True)
with c2:
    st.markdown(stat_card("Online", d["online"],
                           f"{d.get('offline',0)} offline",
                           BRAND["success"], "🟢"), unsafe_allow_html=True)
with c3:
    st.markdown(stat_card("Warning", warn_d,
                           "degraded performance" if warn_d else "none",
                           BRAND["warning"] if warn_d else BRAND["success"],
                           "⚠️" if warn_d else "✅"), unsafe_allow_html=True)
with c4:
    st.markdown(stat_card("Critical", crit_d,
                           "needs attention" if crit_d else "all clear",
                           BRAND["danger"] if crit_d else BRAND["success"],
                           "🔴" if crit_d else "✅"), unsafe_allow_html=True)
with c5:
    st.markdown(stat_card("Open Tickets", t["open"],
                           f"{a.get('critical',0)} critical alerts",
                           BRAND["info"], "🎫"), unsafe_allow_html=True)

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

    health, herr = client.get_health_map()
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
        COLS = 4
        for i in range(0, len(health), COLS):
            row_devs = health[i:i + COLS]
            cols = st.columns(COLS)
            for j, dev in enumerate(row_devs):
                with cols[j]:
                    st.markdown(device_mini_card(dev), unsafe_allow_html=True)

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

    alerts, aerr = client.get_recent_alerts()
    if aerr:
        st.warning(f"Could not load alerts: {aerr}")
    elif not alerts:
        st.markdown("""
        <div style="text-align:center;padding:1.5rem;color:#22C55E;font-size:0.9rem">
            ✅ No recent alerts — all systems healthy
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

    feed, ferr = client.get_activity_feed()
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
