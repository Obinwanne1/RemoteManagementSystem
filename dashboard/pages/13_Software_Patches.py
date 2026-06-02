import streamlit as st
from utils.auth import require_auth

st.set_page_config(page_title="Software Patches — RMM", layout="wide")
st.title("📦 Software Patch Management")

client = require_auth()
st.info("Software patch management (winget/chocolatey integration) — Phase 6")

# Show device software inventory
dev_data, _ = client.list_devices(per_page=200)
devices = dev_data.get("items", []) if dev_data else []

selected_device = st.selectbox("Select Device", [d["display_name"] for d in devices])
if selected_device:
    device = next((d for d in devices if d["display_name"] == selected_device), None)
    if device:
        sw_data, err = client.get_device_software(device["id"])
        if err:
            st.error(err)
        else:
            sw = sw_data or []
            st.caption(f"{len(sw)} packages installed")
            search = st.text_input("Filter software")
            filtered = [s for s in sw if not search or search.lower() in s["name"].lower()]
            for s in filtered[:100]:
                st.markdown(f"**{s['name']}** v{s.get('version','?')} — {s.get('publisher','?')}")
