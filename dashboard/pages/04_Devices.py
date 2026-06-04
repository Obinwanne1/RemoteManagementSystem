"""Devices — list, filter, metrics history, remote actions."""
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from utils.auth import require_auth
from utils.nav import render_sidebar
from utils.styles import inject_css, badge, plotly_layout, BRAND, STATUS_COLORS
from utils.formatters import fmt_datetime, fmt_uptime, pct_color

st.set_page_config(page_title="Devices — RMM", layout="wide")
inject_css()

client = require_auth()
render_sidebar()

st.markdown("""
<h1 style="margin:0">Devices</h1>
<p style="color:#6B7B6B;margin:2px 0 1rem;font-size:0.88rem">All registered endpoints</p>
""", unsafe_allow_html=True)

# ── Filters ───────────────────────────────────────────────────────────────────
st.markdown("""
<div style="background:#FFF;border-radius:10px;padding:0.9rem 1.1rem;
            border:1px solid #DDE8DD;box-shadow:0 1px 4px rgba(0,0,0,0.04);
            margin-bottom:1rem">
""", unsafe_allow_html=True)

fc1, fc2, fc3 = st.columns([2, 1.2, 1.2])
with fc1:
    search = st.text_input("🔍  Search hostname", placeholder="e.g. DESKTOP-", label_visibility="collapsed")
with fc2:
    status_filter = st.selectbox("Status", ["All statuses", "healthy", "warning", "critical", "offline"],
                                  label_visibility="collapsed")
with fc3:
    online_filter = st.selectbox("Online", ["All devices", "Online only", "Offline only"],
                                  label_visibility="collapsed")

st.markdown("</div>", unsafe_allow_html=True)

# ── Load ──────────────────────────────────────────────────────────────────────
params = {}
if search:
    params["q"] = search
if status_filter != "All statuses":
    params["status"] = status_filter
if online_filter == "Online only":
    params["is_online"] = "true"
elif online_filter == "Offline only":
    params["is_online"] = "false"

with st.spinner("Loading devices..."):
    data, err = client.list_devices(per_page=200, **params)
if err:
    st.warning(f"Could not load devices — {err}")
    st.stop()

devices = data.get("items", [])

if not devices:
    st.markdown("""
    <div style="text-align:center;padding:3rem;background:#FFF;border-radius:12px;
                border:1px solid #DDE8DD;color:#6B7B6B">
        <div style="font-size:2.5rem;margin-bottom:0.75rem">💻</div>
        <div style="font-size:1rem;font-weight:600;color:#1A2B1A;margin-bottom:0.4rem">No devices found</div>
        <div style="font-size:0.85rem">Deploy the agent to register endpoints.</div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# Caption
st.markdown(f"""
<div style="font-size:0.8rem;color:#6B7B6B;margin-bottom:0.6rem;padding:0 0.25rem">
    Showing {len(devices)} device{"s" if len(devices) != 1 else ""}
</div>
""", unsafe_allow_html=True)

# ── Column header ─────────────────────────────────────────────────────────────
st.markdown("""
<div style="display:grid;grid-template-columns:2fr 1.2fr 1fr 1fr 1fr 1fr 0.8fr;
            gap:8px;padding:0.4rem 1rem;background:#F4F6F4;border-radius:7px 7px 0 0;
            border:1px solid #DDE8DD;border-bottom:none;
            font-size:0.72rem;font-weight:700;text-transform:uppercase;
            letter-spacing:0.07em;color:#6B7B6B;margin-bottom:0">
    <div>Device</div>
    <div>OS</div>
    <div style="text-align:center">CPU</div>
    <div style="text-align:center">RAM</div>
    <div style="text-align:center">Disk</div>
    <div>Last Seen</div>
    <div>Status</div>
</div>
""", unsafe_allow_html=True)

# ── Device rows ───────────────────────────────────────────────────────────────
def _pct_bar(pct: float, color: str) -> str:
    return (
        f'<div style="background:#EEF2EE;border-radius:3px;height:4px;margin-top:3px">'
        f'<div style="background:{color};width:{min(pct,100):.0f}%;height:4px;border-radius:3px"></div></div>'
    )

selected = st.session_state.get("selected_device_id")

for device in devices:
    status   = device.get("status", "unknown")
    s_color  = STATUS_COLORS.get(status, "#8492A6")
    is_online = device.get("is_online", False)
    dot_color = "#22C55E" if is_online else "#8492A6"
    metrics  = device.get("latest_metrics") or {}
    cpu  = metrics.get("cpu_pct",  0) or 0
    ram  = metrics.get("ram_pct",  0) or 0
    disk = metrics.get("disk_pct", 0) or 0
    cpu_c  = pct_color(cpu)
    ram_c  = pct_color(ram)
    disk_c = pct_color(disk)

    label_html = (
        f'<div style="display:flex;align-items:center;gap:8px">'
        f'  <div style="width:8px;height:8px;border-radius:50%;background:{dot_color};'
        f'              box-shadow:0 0 5px {dot_color}88;flex-shrink:0"></div>'
        f'  <b>{device.get("hostname","—")}</b>'
        f'  <span style="color:#6B7B6B;font-size:0.8rem;font-weight:400">'
        f'    {device.get("ip_address","")}</span>'
        f'</div>'
    )

    with st.expander(
        f'{"🟢" if is_online else "⚫"}  {device.get("hostname","—")}   '
        f'CPU {cpu:.0f}%  ·  RAM {ram:.0f}%  ·  Disk {disk:.0f}%  '
        f'·  {status.upper()}',
        expanded=(device.get("id") == selected),
    ):
        # Detail columns
        d1, d2, d3 = st.columns(3)

        with d1:
            st.markdown(f"""
<div style="background:#FAFCFA;border-radius:8px;padding:0.85rem 1rem;border:1px solid #E8EEE8">
    <div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;
                letter-spacing:0.07em;color:#6B7B6B;margin-bottom:0.6rem">System</div>
    <table style="width:100%;border-collapse:collapse;font-size:0.83rem">
        <tr><td style="color:#6B7B6B;padding:2px 0;width:40%">Hostname</td>
            <td style="color:#1A1A1A;font-weight:500">{device.get('hostname','—')}</td></tr>
        <tr><td style="color:#6B7B6B;padding:2px 0">IP</td>
            <td style="color:#1A1A1A">{device.get('ip_address','—')}</td></tr>
        <tr><td style="color:#6B7B6B;padding:2px 0">OS</td>
            <td style="color:#1A1A1A">{(device.get('os_name') or '—')} {device.get('os_version','')}</td></tr>
        <tr><td style="color:#6B7B6B;padding:2px 0">Platform</td>
            <td style="color:#1A1A1A">{device.get('platform','—')}</td></tr>
    </table>
</div>""", unsafe_allow_html=True)

        with d2:
            st.markdown(f"""
<div style="background:#FAFCFA;border-radius:8px;padding:0.85rem 1rem;border:1px solid #E8EEE8">
    <div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;
                letter-spacing:0.07em;color:#6B7B6B;margin-bottom:0.6rem">Hardware</div>
    <table style="width:100%;border-collapse:collapse;font-size:0.83rem">
        <tr><td style="color:#6B7B6B;padding:2px 0;width:40%">CPU</td>
            <td style="color:#1A1A1A;font-weight:500">{(device.get('cpu_model') or '—')[:28]}</td></tr>
        <tr><td style="color:#6B7B6B;padding:2px 0">Cores</td>
            <td style="color:#1A1A1A">{device.get('cpu_cores','?')}</td></tr>
        <tr><td style="color:#6B7B6B;padding:2px 0">RAM</td>
            <td style="color:#1A1A1A">{device.get('ram_gb','?')} GB</td></tr>
        <tr><td style="color:#6B7B6B;padding:2px 0">Agent</td>
            <td style="color:#1A1A1A">v{device.get('agent_version','?')}</td></tr>
        <tr><td style="color:#6B7B6B;padding:2px 0">Last seen</td>
            <td style="color:#1A1A1A">{fmt_datetime(device.get('last_seen'))}</td></tr>
    </table>
</div>""", unsafe_allow_html=True)

        with d3:
            # Gauge trio
            fig = go.Figure()
            for val, label, clr in [
                (cpu,  "CPU",  cpu_c),
                (ram,  "RAM",  ram_c),
                (disk, "Disk", disk_c),
            ]:
                fig.add_trace(go.Indicator(
                    mode="gauge+number",
                    value=val,
                    number={"suffix": "%", "font": {"size": 14}},
                    title={"text": label, "font": {"size": 11}},
                    gauge={
                        "axis": {"range": [0, 100], "tickwidth": 1,
                                 "tickcolor": "#DDE8DD", "tickfont": {"size": 9}},
                        "bar":  {"color": clr, "thickness": 0.22},
                        "bgcolor": "#F4F6F4",
                        "borderwidth": 0,
                        "steps": [
                            {"range": [0,  75], "color": "#F4F6F4"},
                            {"range": [75, 90], "color": "#FEF3C7"},
                            {"range": [90,100], "color": "#FEE2E2"},
                        ],
                    },
                    domain={"column": ["cpu", "ram", "disk"].index(label.lower()),
                            "row": 0},
                ))
            fig.update_layout(
                grid={"rows": 1, "columns": 3, "pattern": "independent"},
                height=140, margin=dict(t=20, b=8, l=8, r=8),
                paper_bgcolor="#FFF",
            )
            st.plotly_chart(fig, use_container_width=True)

        # ── Assign to Customer ────────────────────────────────────────────────
        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
        cust_data, _ = client.list_customers(per_page=200)
        customers = (cust_data or {}).get("items", [])
        cust_options = {c["id"]: c["name"] for c in customers}
        cust_ids   = [""] + list(cust_options.keys())
        cust_labels = ["— Unassigned —"] + list(cust_options.values())
        current_cid = device.get("customer_id") or ""
        current_idx = cust_ids.index(current_cid) if current_cid in cust_ids else 0

        ca1, ca2 = st.columns([3, 1])
        with ca1:
            chosen_idx = st.selectbox(
                "Assign to Customer",
                range(len(cust_ids)),
                format_func=lambda x: cust_labels[x],
                index=current_idx,
                key=f"cust_{device['id']}",
            )
        with ca2:
            st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
            if st.button("Save", key=f"save_cust_{device['id']}"):
                new_cid = cust_ids[chosen_idx] or None
                _, err = client.update_device(device["id"], {"customer_id": new_cid})
                if err:
                    st.error(f"Failed: {err}")
                else:
                    st.success(f"Assigned to {cust_labels[chosen_idx]}")
                    st.rerun()

        # Actions
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        ab1, ab2, ab3, ab4 = st.columns([1.5, 1, 1, 3])
        with ab1:
            show_hist = st.button("📊 Metrics History", key=f"hist_{device['id']}")
        with ab2:
            if is_online and st.button("🔄 Reboot", key=f"reboot_{device['id']}"):
                _, e = client.reboot_device(device["id"])
                st.error(e) if e else st.success("Reboot queued")
        with ab3:
            if is_online and st.button("⏹ Shutdown", key=f"shut_{device['id']}"):
                _, e = client.shutdown_device(device["id"])
                st.error(e) if e else st.success("Shutdown queued")

        if show_hist:
            st.session_state["selected_device_id"] = device["id"]
            mdata, merr = client.get_device_metrics(device["id"], hours=24)
            if merr or not mdata:
                st.warning("No metric history available.")
            else:
                df = pd.DataFrame(mdata)
                if df.empty:
                    st.info("No metrics recorded yet.")
                else:
                    df["collected_at"] = pd.to_datetime(df["collected_at"])
                    fig2 = px.line(
                        df, x="collected_at",
                        y=["cpu_pct", "ram_pct", "disk_pct"],
                        labels={"value": "Usage %", "collected_at": "Time",
                                "variable": "Metric"},
                        color_discrete_map={
                            "cpu_pct":  "#407E3C",
                            "ram_pct":  "#F59E0B",
                            "disk_pct": "#EF4444",
                        },
                    )
                    fig2.update_traces(line=dict(width=2))
                    plotly_layout(fig2, height=280)
                    fig2.update_layout(
                        paper_bgcolor="#FFF",
                        title=dict(text="24-hour usage history",
                                   font=dict(size=12, color="#6B7B6B")),
                    )
                    st.plotly_chart(fig2, use_container_width=True)
