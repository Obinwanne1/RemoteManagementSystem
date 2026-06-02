import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from utils.auth import require_auth
from utils.formatters import fmt_datetime, fmt_uptime, pct_color, STATUS_COLORS

st.set_page_config(page_title="Devices — RMM", layout="wide")
st.title("💻 Devices")

client = require_auth()

# --- Filters ---
col1, col2, col3 = st.columns(3)
with col1:
    search = st.text_input("Search hostname", placeholder="e.g. DESKTOP-")
with col2:
    status_filter = st.selectbox("Status", ["All", "healthy", "warning", "critical", "offline"])
with col3:
    online_filter = st.selectbox("Online", ["All", "Online only", "Offline only"])

# --- Load Devices ---
filters = {}
if search:
    filters["q"] = search
if status_filter != "All":
    filters["status"] = status_filter
if online_filter == "Online only":
    filters["is_online"] = "true"
elif online_filter == "Offline only":
    filters["is_online"] = "false"

data, err = client.list_devices(per_page=200, **filters)
if err:
    st.error(f"API error: {err}")
    st.stop()

devices = data.get("items", [])
st.caption(f"{len(devices)} devices found")

if not devices:
    st.info("No devices found. Deploy the agent to register devices.")
    st.stop()

# --- Device Table ---
selected_device = st.session_state.get("selected_device_id")

for device in devices:
    status = device["status"]
    is_online = device["is_online"]
    color = STATUS_COLORS.get(status, "#ADB5BD")
    online_icon = "🟢" if is_online else "🔴"

    metrics = device.get("latest_metrics") or {}
    cpu = metrics.get("cpu_pct", 0) or 0
    ram = metrics.get("ram_pct", 0) or 0
    disk = metrics.get("disk_pct", 0) or 0

    with st.expander(
        f"{online_icon} **{device['display_name']}** — {device['os_name'] or 'Unknown OS'} "
        f"| CPU: {cpu:.0f}% | RAM: {ram:.0f}% | Disk: {disk:.0f}%",
        expanded=(device["id"] == selected_device)
    ):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"**Hostname:** {device['hostname']}")
            st.markdown(f"**IP:** {device['ip_address'] or '—'}")
            st.markdown(f"**OS:** {device['os_name'] or '—'} {device['os_version'] or ''}")
            st.markdown(f"**CPU:** {device['cpu_model'] or '—'} ({device['cpu_cores'] or '?'} cores)")
        with col2:
            st.markdown(f"**RAM:** {device['ram_gb'] or '?'} GB")
            st.markdown(f"**Platform:** {device['platform']}")
            st.markdown(f"**Agent:** v{device['agent_version'] or '?'}")
            st.markdown(f"**Last seen:** {fmt_datetime(device['last_seen'])}")
        with col3:
            # Gauge charts
            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=cpu,
                title={"text": "CPU %"},
                gauge={"axis": {"range": [0, 100]},
                       "bar": {"color": pct_color(cpu)}},
            ))
            fig.update_layout(height=150, margin=dict(t=30, b=10, l=10, r=10))
            st.plotly_chart(fig, use_container_width=True)

        # Action buttons
        btn_col1, btn_col2, btn_col3 = st.columns(3)
        with btn_col1:
            if st.button(f"📊 Metrics History", key=f"metrics_{device['id']}"):
                st.session_state["selected_device_id"] = device["id"]
                _show_metrics(client, device["id"])
        with btn_col2:
            if is_online:
                if st.button(f"🔄 Reboot", key=f"reboot_{device['id']}"):
                    _, err = client.reboot_device(device["id"])
                    if err:
                        st.error(err)
                    else:
                        st.success("Reboot queued")
        with btn_col3:
            if is_online:
                if st.button(f"⏹️ Shutdown", key=f"shutdown_{device['id']}"):
                    _, err = client.shutdown_device(device["id"])
                    if err:
                        st.error(err)
                    else:
                        st.success("Shutdown queued")


def _show_metrics(client, device_id):
    import plotly.express as px
    data, err = client.get_device_metrics(device_id, hours=24)
    if err or not data:
        st.warning("No metric history available")
        return
    df = pd.DataFrame(data)
    if df.empty:
        st.info("No metrics recorded yet")
        return
    df["collected_at"] = pd.to_datetime(df["collected_at"])
    fig = px.line(df, x="collected_at", y=["cpu_pct", "ram_pct", "disk_pct"],
                  labels={"value": "Usage %", "collected_at": "Time"},
                  color_discrete_map={"cpu_pct": "#407E3C", "ram_pct": "#E6A817", "disk_pct": "#D9534F"})
    fig.update_layout(height=300, margin=dict(t=20, b=20))
    st.plotly_chart(fig, use_container_width=True)
