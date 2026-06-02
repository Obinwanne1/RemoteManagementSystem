import streamlit as st
from utils.auth import require_auth, current_user
from utils.formatters import fmt_datetime

st.set_page_config(page_title="Admin — RMM", layout="wide")
st.title("👤 Admin")

client = require_auth()
user = current_user()

if user.get("role") != "admin":
    st.error("Admin access required")
    st.stop()

tab1, tab2 = st.tabs(["System Info", "Audit Log"])

with tab1:
    st.subheader("System")
    st.json({
        "current_user": user,
        "api_url": "http://localhost:5000",
        "dashboard_url": "http://localhost:8501",
    })

with tab2:
    st.subheader("Audit Log")
    feed, err = client.get_activity_feed()
    if err:
        st.error(f"API error: {err}")
    elif feed:
        for item in feed:
            st.markdown(
                f'**{item["action"]}** `{item.get("resource_type","")}:{item.get("resource_id","")}`'
                f' — {fmt_datetime(item["created_at"])} | IP: {item.get("ip_address","?")}',
                unsafe_allow_html=True,
            )
    else:
        st.info("No audit events yet.")
