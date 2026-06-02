import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from utils.auth import require_auth
from utils.formatters import fmt_datetime, STATUS_COLORS, SEVERITY_COLORS

st.set_page_config(page_title="Overview — RMM", layout="wide")
st.title("📊 Dashboard Overview")

client = require_auth()

# --- Summary Tiles ---
summary, err = client.get_summary()
if err:
    st.error(f"API error: {err}")
    st.stop()

d = summary["devices"]
a = summary["alerts"]
t = summary["tickets"]

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total Devices", d["total"])
col2.metric("🟢 Online", d["online"])
col3.metric("🔴 Offline", d["offline"])
col4.metric("🔔 Open Alerts", a["open"], delta=f"{a['critical']} critical" if a['critical'] else None)
col5.metric("🎫 Open Tickets", t["open"])

st.divider()

# --- Device Status Donut + Health Grid ---
left, right = st.columns([1, 2])

with left:
    st.subheader("Device Status")
    status_counts = {
        "Healthy": d["total"] - d["offline"] - d["critical"] - d["warning"],
        "Warning": d["warning"],
        "Critical": d["critical"],
        "Offline": d["offline"],
    }
    fig = go.Figure(go.Pie(
        labels=list(status_counts.keys()),
        values=list(status_counts.values()),
        hole=0.5,
        marker_colors=["#407E3C", "#FFC107", "#DC3545", "#6C757D"],
    ))
    fig.update_layout(height=280, margin=dict(t=10, b=10, l=10, r=10),
                      showlegend=True, legend=dict(orientation="h"))
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Device Health Map")
    health, herr = client.get_health_map()
    if herr:
        st.warning(f"Could not load health map: {herr}")
    elif health:
        # Display as colored grid
        cols_per_row = 6
        for i in range(0, len(health), cols_per_row):
            row_devices = health[i:i+cols_per_row]
            cols = st.columns(cols_per_row)
            for j, device in enumerate(row_devices):
                color = STATUS_COLORS.get(device["status"], "#ADB5BD")
                icon = "🟢" if device["is_online"] else "🔴"
                cols[j].markdown(
                    f'<div style="background:{color};color:white;padding:6px;border-radius:4px;'
                    f'text-align:center;font-size:0.75em;margin:2px" title="{device["hostname"]}">'
                    f'{icon} {device["hostname"][:12]}</div>',
                    unsafe_allow_html=True,
                )
    else:
        st.info("No devices found. Deploy the agent to register devices.")

st.divider()

# --- Recent Alerts + Activity Feed ---
col_a, col_b = st.columns(2)

with col_a:
    st.subheader("Recent Alerts")
    alerts, aerr = client.get_recent_alerts()
    if aerr:
        st.warning(f"Could not load alerts: {aerr}")
    elif alerts:
        for alert in alerts[:10]:
            severity = alert["severity"]
            color = SEVERITY_COLORS.get(severity, "#6C757D")
            st.markdown(
                f'<div style="border-left:3px solid {color};padding:6px 12px;margin:4px 0;background:#f8f9fa">'
                f'<b style="color:{color}">[{severity.upper()}]</b> {alert["message"]}'
                f'<br><small style="color:#666">{fmt_datetime(alert["triggered_at"])} • {alert["status"]}</small>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.success("No recent alerts.")

with col_b:
    st.subheader("Activity Feed")
    feed, ferr = client.get_activity_feed()
    if ferr:
        st.warning(f"Could not load feed: {ferr}")
    elif feed:
        for item in feed[:10]:
            st.markdown(
                f'<div style="padding:4px 0;border-bottom:1px solid #eee">'
                f'<b>{item["action"]}</b> {item.get("resource_type","")}'
                f'<br><small style="color:#666">{fmt_datetime(item["created_at"])}'
                f' • {item.get("ip_address","")}</small>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("No recent activity.")
