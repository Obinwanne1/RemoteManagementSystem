import streamlit as st
from utils.auth import require_auth
from utils.formatters import fmt_datetime

st.set_page_config(page_title="Network Discovery — RMM", layout="wide")
st.title("🌐 Network Discovery")

client = require_auth()

cust_data, _ = client.list_customers(per_page=100)
customers = cust_data.get("items", []) if cust_data else []
cust_map = {c["name"]: c["id"] for c in customers}

col1, col2, col3 = st.columns(3)
with col1:
    customer = st.selectbox("Customer", list(cust_map.keys()) or ["— no customers —"])
with col2:
    scan_range = st.text_input("IP Range (CIDR)", placeholder="192.168.1.0/24")
with col3:
    if st.button("🔍 Start Scan", type="primary"):
        if scan_range and cust_map:
            result, err = client._post("/api/network/scan", {
                "customer_id": cust_map[customer],
                "scan_range": scan_range,
            })
            if err:
                st.error(err)
            else:
                st.success(f"Scan started: {result.get('scan_id')}")

st.divider()
st.subheader("Scan History")
scans_data, err = client._get("/api/network/scans")
if err:
    st.warning(f"Could not load scans: {err}")
elif scans_data:
    for scan in scans_data:
        st.markdown(
            f"**{scan['scan_range']}** | {scan['status']} | "
            f"{scan.get('host_count',0)} hosts | {fmt_datetime(scan['started_at'])}"
        )
