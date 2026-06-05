"""Billing — Customer invoices and billing management."""
import streamlit as st
from datetime import date, timedelta

from utils.auth import require_auth
from utils.nav import render_sidebar
from utils.styles import inject_css, badge, BRAND, stat_card
from utils.formatters import fmt_datetime, fmt_bytes

st.set_page_config(page_title="Billing — RMM", layout="wide")
inject_css()

client = require_auth()
render_sidebar()

st.markdown('<h1 style="margin:0">Billing</h1><p style="color:#6B7B6B;margin:2px 0 1rem;font-size:0.88rem">Customer invoices and billing management</p>', unsafe_allow_html=True)

# ── Load customers ────────────────────────────────────────────────────────────
cust_data, cust_err = client.list_customers(per_page=100)
customers = cust_data.get("items", []) if cust_data else []
cust_map = {c["name"]: c["id"] for c in customers}
cust_names_all = ["All Customers"] + list(cust_map.keys())

# ── Customer filter ───────────────────────────────────────────────────────────
filter_col, spacer = st.columns([2, 4])
with filter_col:
    filter_cust = st.selectbox("Filter by Customer", cust_names_all)

filter_cust_id = cust_map.get(filter_cust) if filter_cust != "All Customers" else None

# ── Load invoices ─────────────────────────────────────────────────────────────
with st.spinner("Loading invoices..."):
    inv_data, inv_err = client.list_invoices(customer_id=filter_cust_id)
if inv_err:
    st.warning(f"Could not load invoices — {inv_err}")
    st.stop()

invoices = inv_data if isinstance(inv_data, list) else []

# ── Summary stats ─────────────────────────────────────────────────────────────
paid_total    = sum(float(inv.get("total") or 0) for inv in invoices if (inv.get("status") or "").lower() == "paid")
pending_total = sum(float(inv.get("total") or 0) for inv in invoices if (inv.get("status") or "").lower() in ("draft", "sent"))
overdue_total = sum(float(inv.get("total") or 0) for inv in invoices if (inv.get("status") or "").lower() == "overdue")

sc1, sc2, sc3, sc4 = st.columns(4)
sc1.metric("Total Invoices", len(invoices))
sc2.metric("Revenue (Paid)", f"${paid_total:,.2f}")
sc3.metric("Outstanding", f"${pending_total:,.2f}")
sc4.metric("Overdue", f"${overdue_total:,.2f}")

st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

# ── Invoice list ──────────────────────────────────────────────────────────────
STATUS_BADGE_COLORS = {
    "paid":    BRAND["success"],
    "sent":    "#3B82F6",
    "pending": BRAND["warning"],
    "overdue": BRAND["danger"],
    "draft":   BRAND["muted"],
}

if not invoices:
    st.markdown(
        '<div style="text-align:center;padding:3rem;background:#FFFFFF;border-radius:12px;'
        'border:1px solid #DDE8DD;color:#6B7B6B">'
        '<div style="font-size:2.5rem;margin-bottom:0.75rem">🧾</div>'
        '<div style="font-size:1rem;font-weight:600;color:#1A2B1A;margin-bottom:0.4rem">No invoices found</div>'
        '<div style="font-size:0.85rem">Generate an invoice below to get started.</div>'
        '</div>',
        unsafe_allow_html=True
    )
else:
    # Column header row
    _HDR = "font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:#6B7B6B;padding:0.3rem 0"
    h0,h1,h2,h3,h4,h5,h6,h7 = st.columns([1.5, 1.8, 1.1, 1.1, 0.7, 0.8, 0.9, 2.5])
    for col, lbl in zip([h0,h1,h2,h3,h4,h5,h6,h7],
                        ["#","Customer","Period Start","Period End","Devices","Rate/Dev","Total","Actions"]):
        col.markdown(f"<div style='{_HDR}'>{lbl}</div>", unsafe_allow_html=True)
    st.divider()

    for i, inv in enumerate(invoices):
        inv_id     = inv["id"]
        inv_num    = inv.get("invoice_number") or inv_id[:8].upper()
        status_raw = (inv.get("status") or "draft").lower()
        status_color = STATUS_BADGE_COLORS.get(status_raw, BRAND["muted"])

        cust_id_str = str(inv.get("customer_id") or "")
        cust_label  = next((c["name"] for c in customers if str(c["id"]) == cust_id_str), "—")
        period_start = (inv.get("period_start") or "")[:10] or "—"
        period_end   = (inv.get("period_end") or "")[:10] or "—"
        dev_count    = inv.get("device_count") or "—"
        rate         = f"${float(inv.get('per_device_rate') or 0):.2f}"
        total        = f"${float(inv.get('total') or 0):,.2f}"

        c0,c1,c2,c3,c4,c5,c6,c7 = st.columns([1.5, 1.8, 1.1, 1.1, 0.7, 0.8, 0.9, 2.5])
        c0.markdown(f"<div style='font-size:0.78rem;font-family:monospace;color:#407E3C;font-weight:600'>{inv_num}</div>", unsafe_allow_html=True)
        c1.markdown(f"<div style='font-size:0.83rem;font-weight:600;color:#1A1A1A'>{cust_label}</div>", unsafe_allow_html=True)
        c2.markdown(f"<div style='font-size:0.8rem;color:#4A5A4A'>{period_start}</div>", unsafe_allow_html=True)
        c3.markdown(f"<div style='font-size:0.8rem;color:#4A5A4A'>{period_end}</div>", unsafe_allow_html=True)
        c4.markdown(f"<div style='font-size:0.83rem;color:#6B7B6B;text-align:right'>{dev_count}</div>", unsafe_allow_html=True)
        c5.markdown(f"<div style='font-size:0.8rem;color:#6B7B6B;font-family:monospace'>{rate}</div>", unsafe_allow_html=True)
        c6.markdown(f"<div style='font-size:0.83rem;font-weight:700;color:#1A1A1A;font-family:monospace'>{total}</div>", unsafe_allow_html=True)

        with c7:
            btn_cols = st.columns(4)

            # View — always available
            if btn_cols[0].button("View", key=f"view_{inv_id}_{i}", help="Open full invoice"):
                st.session_state["_view_invoice_id"] = inv_id
                st.session_state.pop("_del_inv_confirm", None)
                st.switch_page("pages/10_Invoice_Detail.py")

            # Status transitions
            if status_raw == "draft":
                if btn_cols[1].button("Send", key=f"send_{inv_id}_{i}", help="Mark as Sent"):
                    _, e = client.update_invoice_status(inv_id, "sent")
                    st.rerun() if not e else st.error(e)
            elif status_raw == "sent":
                if btn_cols[1].button("Paid", key=f"paid_{inv_id}_{i}", help="Mark as Paid", type="primary"):
                    _, e = client.update_invoice_status(inv_id, "paid")
                    st.rerun() if not e else st.error(e)
                if btn_cols[2].button("Ovrd", key=f"ovd_{inv_id}_{i}", help="Mark as Overdue"):
                    _, e = client.update_invoice_status(inv_id, "overdue")
                    st.rerun() if not e else st.error(e)
            elif status_raw == "overdue":
                if btn_cols[1].button("Paid", key=f"paid_{inv_id}_{i}", help="Mark as Paid", type="primary"):
                    _, e = client.update_invoice_status(inv_id, "paid")
                    st.rerun() if not e else st.error(e)
            else:
                btn_cols[1].markdown(badge("paid", STATUS_BADGE_COLORS["paid"]), unsafe_allow_html=True)

            # Delete
            if btn_cols[3].button("🗑", key=f"del_inv_{inv_id}_{i}", help="Delete invoice"):
                if st.session_state.get(f"_del_confirm_{inv_id}"):
                    _, e = client.delete_invoice(inv_id)
                    st.session_state.pop(f"_del_confirm_{inv_id}", None)
                    st.rerun() if not e else st.error(e)
                else:
                    st.session_state[f"_del_confirm_{inv_id}"] = True
                    st.rerun()

            if st.session_state.get(f"_del_confirm_{inv_id}"):
                st.warning(f"Delete {total} invoice? Click 🗑 again to confirm.")

        if i < len(invoices) - 1:
            st.markdown("<hr style='margin:0.2rem 0;border-color:#EEF2EE'>", unsafe_allow_html=True)

# ── Generate Invoice form ─────────────────────────────────────────────────────
st.markdown("<div style='height:1.25rem'></div>", unsafe_allow_html=True)
st.markdown(
    '<div style="font-size:1rem;font-weight:700;color:#1A2B1A;margin-bottom:0.75rem">Generate Invoice</div>',
    unsafe_allow_html=True
)

if not customers:
    st.info("No customers found. Add a customer first before generating invoices.")
else:
    with st.form("generate_invoice_form"):
        gi_c1, gi_c2, gi_c3, gi_c4 = st.columns([2, 1.5, 1.5, 1])
        with gi_c1:
            inv_cust = st.selectbox("Customer", list(cust_map.keys()), key="inv_cust_sel")
        with gi_c2:
            inv_start = st.date_input("Period Start", value=date.today().replace(day=1))
        with gi_c3:
            last_day = (date.today().replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            inv_end = st.date_input("Period End", value=last_day)
        with gi_c4:
            inv_rate = st.number_input("Rate / Device ($)", min_value=0.0, value=25.0, step=0.5, format="%.2f")

        gr_c1, gr_c2, gr_c3 = st.columns([1, 1.5, 3.5])
        with gr_c1:
            inv_tax = st.number_input("Tax Rate (%)", min_value=0.0, max_value=100.0, value=0.0, step=0.5, format="%.1f")
        with gr_c2:
            default_due = last_day + timedelta(days=30)
            inv_due = st.date_input("Due Date", value=default_due)
        with gr_c3:
            inv_notes = st.text_input("Notes (optional)", placeholder="e.g. Please reference invoice number when paying")

        gen_submitted = st.form_submit_button("Generate Invoice", use_container_width=False)

    if gen_submitted:
        if inv_end < inv_start:
            st.error("Period end must be after period start.")
        else:
            payload = {
                "customer_id":     cust_map[inv_cust],
                "period_start":    inv_start.isoformat(),
                "period_end":      inv_end.isoformat(),
                "due_date":        inv_due.isoformat(),
                "per_device_rate": inv_rate,
                "tax_rate":        inv_tax / 100.0,
                "notes":           inv_notes or None,
            }
            with st.spinner("Generating invoice..."):
                result, err = client.generate_invoice(payload)
            if err:
                st.error(f"Invoice generation failed: {err}")
            else:
                new_num = result.get("invoice_number", "")
                st.success(f"Invoice {new_num} generated for {inv_cust}.")
                st.rerun()
