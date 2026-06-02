import streamlit as st
import plotly.graph_objects as go
from utils.auth import require_auth

st.set_page_config(page_title="Disk Management — RMM", layout="wide")
st.title("💾 Disk Management")

client = require_auth()

dev_data, _ = client.list_devices(per_page=200)
devices = dev_data.get("items", []) if dev_data else []

for device in devices:
    metrics = device.get("latest_metrics") or {}
    disks = metrics.get("disks") or []
    if not disks:
        continue
    with st.expander(f"**{device['display_name']}** — {len(disks)} disk(s)"):
        cols = st.columns(len(disks))
        for i, disk in enumerate(disks):
            with cols[i]:
                fig = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=disk.get("percent", 0),
                    title={"text": disk.get("mountpoint", disk.get("device"))},
                    gauge={
                        "axis": {"range": [0, 100]},
                        "bar": {"color": "#DC3545" if disk.get("percent", 0) > 90 else "#407E3C"},
                    },
                    number={"suffix": "%"},
                ))
                fig.update_layout(height=200, margin=dict(t=40, b=10, l=10, r=10))
                st.plotly_chart(fig, use_container_width=True)
                st.caption(
                    f"Used: {disk.get('used_gb',0):.1f} GB / {disk.get('total_gb',0):.1f} GB"
                )

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔧 Defragment", key=f"defrag_{device['id']}",
                         disabled=not device["is_online"]):
                st.info("Defrag queued — Phase 5 execution")
        with col2:
            if st.button("✅ Check Disk", key=f"chkdsk_{device['id']}",
                         disabled=not device["is_online"]):
                st.info("Checkdisk queued — Phase 5 execution")
