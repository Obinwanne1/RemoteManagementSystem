import streamlit as st
from utils.auth import require_auth
from utils.formatters import fmt_datetime

st.set_page_config(page_title="Billing — RMM", layout="wide")
st.title("💰 Billing")

client = require_auth()

tab1, tab2 = st.tabs(["Invoice List", "Generate Invoice"])

with tab1:
    invoices, err = client.list_invoices()
    if err:
        st.error(f"API error: {err}")
    elif not invoices:
        st.info("No invoices yet.")
    else:
        for inv in invoices:
            status_icon = {"draft": "📝", "sent": "📤", "paid": "✅", "overdue": "🔴"}.get(inv["status"], "?")
            with st.expander(
                f'{status_icon} **Invoice** | Customer: `{inv["customer_id"][:8]}` | '
                f'Total: **${inv["total"]:.2f}** | {inv["status"].upper()}'
            ):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Devices:** {inv['device_count']} × ${inv['per_device_rate']}/device")
                    st.markdown(f"**Subtotal:** ${inv['subtotal']:.2f}")
                    st.markdown(f"**Tax:** ${inv['tax']:.2f}")
                    st.markdown(f"**Total:** ${inv['total']:.2f}")
                with col2:
                    st.markdown(f"**Period:** {fmt_datetime(inv['period_start'])} → {fmt_datetime(inv['period_end'])}")
                    st.markdown(f"**Created:** {fmt_datetime(inv['created_at'])}")
                    st.markdown(f"**Sent:** {fmt_datetime(inv.get('sent_at'))}")
                    st.markdown(f"**Paid:** {fmt_datetime(inv.get('paid_at'))}")

with tab2:
    cust_data, _ = client.list_customers(per_page=100)
    customers = cust_data.get("items", []) if cust_data else []
    cust_map = {c["name"]: c["id"] for c in customers}

    with st.form("gen_invoice"):
        customer = st.selectbox("Customer *", list(cust_map.keys()) or ["— no customers —"])
        col1, col2 = st.columns(2)
        with col1:
            period_start = st.date_input("Period Start")
        with col2:
            period_end = st.date_input("Period End")
        per_device = st.number_input("Per Device Rate ($)", 0.0, 9999.0, 15.0, step=0.5)
        tax_rate = st.number_input("Tax Rate (%)", 0.0, 50.0, 0.0, step=0.5)
        submitted = st.form_submit_button("Generate Invoice")

    if submitted and cust_map:
        _, err = client.generate_invoice({
            "customer_id": cust_map[customer],
            "period_start": period_start.isoformat() + "T00:00:00",
            "period_end": period_end.isoformat() + "T23:59:59",
            "per_device_rate": per_device,
            "tax_rate": tax_rate / 100,
        })
        if err:
            st.error(f"Failed: {err}")
        else:
            st.success("Invoice generated!")
            st.rerun()
