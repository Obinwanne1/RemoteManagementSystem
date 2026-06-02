import streamlit as st
from utils.auth import require_auth
from utils.formatters import fmt_datetime, PRIORITY_COLORS

st.set_page_config(page_title="Tickets — RMM", layout="wide")
st.title("🎫 Tickets")

client = require_auth()

tab1, tab2 = st.tabs(["Ticket List", "Create Ticket"])

with tab1:
    col1, col2, col3 = st.columns(3)
    with col1:
        status_f = st.selectbox("Status", ["All", "open", "in_progress", "resolved", "closed"])
    with col2:
        priority_f = st.selectbox("Priority", ["All", "critical", "high", "medium", "low"])
    with col3:
        st.write("")

    filters = {}
    if status_f != "All":
        filters["status"] = status_f
    if priority_f != "All":
        filters["priority"] = priority_f

    data, err = client.list_tickets(**filters)
    if err:
        st.error(f"API error: {err}")
    else:
        tickets = data.get("items", [])
        st.caption(f"{len(tickets)} tickets")
        for t in tickets:
            color = PRIORITY_COLORS.get(t["priority"], "#6C757D")
            with st.expander(
                f'[{t["priority"].upper()}] **{t["title"]}** — {t["status"]}',
                expanded=False
            ):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Description:** {t.get('description') or '—'}")
                    st.markdown(f"**Created:** {fmt_datetime(t['created_at'])}")
                with col2:
                    new_status = st.selectbox("Update Status",
                        ["open", "in_progress", "resolved", "closed"],
                        index=["open", "in_progress", "resolved", "closed"].index(t["status"]),
                        key=f"status_{t['id']}")
                    if st.button("Update", key=f"update_{t['id']}"):
                        _, err = client.update_ticket(t["id"], {"status": new_status})
                        if err:
                            st.error(err)
                        else:
                            st.success("Updated")
                            st.rerun()

with tab2:
    st.subheader("Create New Ticket")
    # Load customers for dropdown
    cust_data, _ = client.list_customers(per_page=100)
    customers = cust_data.get("items", []) if cust_data else []
    cust_options = {c["name"]: c["id"] for c in customers}

    with st.form("create_ticket"):
        title = st.text_input("Title *")
        description = st.text_area("Description")
        customer_name = st.selectbox("Customer *", list(cust_options.keys()) or ["— no customers —"])
        priority = st.selectbox("Priority", ["medium", "low", "high", "critical"])
        submitted = st.form_submit_button("Create Ticket")

    if submitted:
        if not title or not cust_options:
            st.error("Title and customer required")
        else:
            _, err = client.create_ticket({
                "title": title,
                "description": description,
                "customer_id": cust_options[customer_name],
                "priority": priority,
            })
            if err:
                st.error(f"Failed: {err}")
            else:
                st.success("Ticket created!")
                st.rerun()
