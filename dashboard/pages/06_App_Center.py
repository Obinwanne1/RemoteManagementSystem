import streamlit as st
from utils.auth import require_auth

st.set_page_config(page_title="App Center — RMM", layout="wide")
st.title("📦 App Center")

client = require_auth()
st.info("App Center — software catalog and remote install — Phase 9")

# Show device software inventories
dev_data, _ = client.list_devices(per_page=200)
devices = dev_data.get("items", []) if dev_data else []

if devices:
    device_names = [d["display_name"] for d in devices]
    selected = st.selectbox("View installed software for", device_names)
    device = next((d for d in devices if d["display_name"] == selected), None)
    if device:
        sw_data, _ = client.get_device_software(device["id"])
        sw = sw_data or []
        search = st.text_input("Filter", placeholder="Search packages...")
        filtered = [s for s in sw if not search or search.lower() in s["name"].lower()]
        st.caption(f"{len(filtered)} packages")
        for s in filtered[:200]:
            st.markdown(f"**{s['name']}** v{s.get('version','?')} — {s.get('publisher','?')}")
