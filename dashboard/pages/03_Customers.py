import streamlit as st
from utils.auth import require_auth
from utils.formatters import fmt_datetime

st.set_page_config(page_title="Customers — RMM", layout="wide")
st.title("🏢 Customers")

client = require_auth()

tab1, tab2 = st.tabs(["Customer List", "Add Customer"])

with tab1:
    q = st.text_input("Search", placeholder="Search by name...")
    data, err = client.list_customers(q=q, per_page=100)
    if err:
        st.error(f"API error: {err}")
    else:
        customers = data.get("items", [])
        st.caption(f"{len(customers)} customers")
        for c in customers:
            with st.expander(f"**{c['name']}** — {c['tier'].upper()} | "
                             f"{c.get('device_count', 0)} devices ({c.get('online_count', 0)} online)"):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Email:** {c['email'] or '—'}")
                    st.markdown(f"**Phone:** {c['phone'] or '—'}")
                    st.markdown(f"**Address:** {c['address'] or '—'}")
                with col2:
                    st.markdown(f"**Tier:** {c['tier']}")
                    st.markdown(f"**Created:** {fmt_datetime(c['created_at'])}")
                    st.markdown(f"**Notes:** {c['notes'] or '—'}")

with tab2:
    st.subheader("Add New Customer")
    with st.form("add_customer"):
        name = st.text_input("Company Name *")
        email = st.text_input("Email")
        phone = st.text_input("Phone")
        address = st.text_area("Address")
        tier = st.selectbox("Tier", ["standard", "premium", "enterprise"])
        notes = st.text_area("Notes")
        submitted = st.form_submit_button("Create Customer")

    if submitted:
        if not name:
            st.error("Company name required")
        else:
            result, err = client.create_customer({
                "name": name, "email": email, "phone": phone,
                "address": address, "tier": tier, "notes": notes,
            })
            if err:
                st.error(f"Failed: {err}")
            else:
                st.success(f"Customer '{result['name']}' created!")
                st.rerun()
