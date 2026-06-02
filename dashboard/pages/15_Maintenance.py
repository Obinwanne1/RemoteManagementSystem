import streamlit as st
from utils.auth import require_auth
from utils.formatters import fmt_datetime

st.set_page_config(page_title="Maintenance — RMM", layout="wide")
st.title("🔨 Maintenance")

client = require_auth()

st.info("Maintenance actions dispatch via automation profiles (Phase 5) or direct task queue.")

dev_data, _ = client.list_devices(per_page=200)
devices = dev_data.get("items", []) if dev_data else []
online_devices = [d for d in devices if d["is_online"]]

if not online_devices:
    st.warning("No online devices.")
else:
    selected = st.selectbox("Target Device", [d["display_name"] for d in online_devices])
    device = next((d for d in online_devices if d["display_name"] == selected), None)

    if device:
        st.markdown(f"**Device:** {device['hostname']} | **IP:** {device.get('ip_address','?')}")
        st.markdown(f"**Last seen:** {fmt_datetime(device.get('last_seen'))}")
        st.divider()

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🔄 Reboot Device"):
                _, err = client.reboot_device(device["id"])
                st.success("Reboot queued") if not err else st.error(err)
            if st.button("🗑️ Delete Temp Files"):
                st.info("Delete temp queued — Phase 5")
        with col2:
            if st.button("⏹️ Shutdown Device"):
                _, err = client.shutdown_device(device["id"])
                st.success("Shutdown queued") if not err else st.error(err)
            if st.button("🌐 Clear Browser History"):
                st.info("Clear history queued — Phase 5")
        with col3:
            if st.button("📸 Create Restore Point"):
                st.info("Restore point queued — Phase 5")
