import streamlit as st
from utils.auth import require_auth
from utils.formatters import fmt_datetime

st.set_page_config(page_title="Reports — RMM", layout="wide")
st.title("📈 Reports")

client = require_auth()

tab1, tab2 = st.tabs(["Generate Report", "Report History"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        report_type = st.selectbox("Report Type", [
            "patch_summary", "device_health", "ticket_summary",
            "software_inventory", "billing"
        ])
        format_ = st.selectbox("Format", ["pdf", "xlsx", "csv"])
    with col2:
        cust_data, _ = client.list_customers(per_page=100)
        customers = cust_data.get("items", []) if cust_data else []
        cust_map = {"All Customers": None, **{c["name"]: c["id"] for c in customers}}
        customer = st.selectbox("Customer Scope", list(cust_map.keys()))

    if st.button("📊 Generate Report", type="primary"):
        result, err = client.generate_report({
            "template_type": report_type,
            "format": format_,
            "customer_id": cust_map[customer],
        })
        if err:
            st.error(err)
        else:
            st.success(f"Report queued: {result.get('report_id')}")

with tab2:
    reports, err = client.list_reports()
    if err:
        st.error(f"API error: {err}")
    elif reports:
        for r in reports:
            st.markdown(
                f"**{r['name']}** | {r['template_type']} | {r['format'].upper()} | "
                f"{fmt_datetime(r['generated_at'])}"
            )
    else:
        st.info("No reports generated yet.")
