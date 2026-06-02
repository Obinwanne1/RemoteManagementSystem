"""Billing — Customer invoices and billing management."""
import streamlit as st
from datetime import date, timedelta

from utils.auth import require_auth
from utils.styles import inject_css, badge, BRAND, stat_card
from utils.formatters import fmt_datetime, fmt_bytes

st.set_page_config(page_title="Billing — RMM", layout="wide")
inject_css()

client = require_auth()

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
inv_data, inv_err = client.list_invoices(customer_id=filter_cust_id)
if inv_err:
    st.error(f"Could not load invoices: {inv_err}")
    st.stop()

invoices = inv_data if isinstance(inv_data, list) else []

# ── Summary stat ──────────────────────────────────────────────────────────────
paid_total = sum(float(inv.get("total") or 0) for inv in invoices if (inv.get("status") or "").lower() == "paid")
pending_total = sum(float(inv.get("total") or 0) for inv in invoices if (inv.get("status") or "").lower() == "pending")
overdue_total = sum(float(inv.get("total") or 0) for inv in invoices if (inv.get("status") or "").lower() == "overdue")

sc1, sc2, sc3, sc4 = st.columns(4)
sc1.metric("Total Invoices", len(invoices))
sc2.metric("Revenue (Paid)", f"${paid_total:,.2f}")
sc3.metric("Pending", f"${pending_total:,.2f}")
sc4.metric("Overdue", f"${overdue_total:,.2f}")

st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

# ── Invoice list ──────────────────────────────────────────────────────────────
STATUS_BADGE_COLORS = {
    "paid":    BRAND["success"],
    "pending": BRAND["warning"],
    "overdue": BRAND["danger"],
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
    # Table header
    st.markdown(
        '<div style="display:grid;grid-template-columns:2fr 1.5fr 1.5fr 0.8fr 0.8fr 1fr 0.9fr;gap:8px;'
        'padding:0.45rem 1rem;background:#F4F6F4;border-radius:8px 8px 0 0;'
        'border:1px solid #DDE8DD;border-bottom:none;'
        'font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:#6B7B6B">'
        '<div>Customer</div><div>Period Start</div><div>Period End</div>'
        '<div style="text-align:right">Devices</div><div style="text-align:right">Rate/Dev</div>'
        '<div style="text-align:right">Total</div><div>Status</div></div>',
        unsafe_allow_html=True
    )

    rows_html = '<div style="border:1px solid #DDE8DD;border-radius:0 0 8px 8px;overflow:hidden">'
    for i, inv in enumerate(invoices):
        bg = "#FFFFFF" if i % 2 == 0 else "#FAFCFA"
        status_raw = (inv.get("status") or "unknown").lower()
        status_color = STATUS_BADGE_COLORS.get(status_raw, BRAND["muted"])
        status_b = badge(status_raw, status_color)

        # Resolve customer name
        cust_id_str = str(inv.get("customer_id") or "")
        cust_label = next((c["name"] for c in customers if str(c["id"]) == cust_id_str), cust_id_str or "—")

        period_start = fmt_datetime(inv.get("period_start") or "")[:10] if inv.get("period_start") else "—"
        period_end   = fmt_datetime(inv.get("period_end") or "")[:10] if inv.get("period_end") else "—"
        dev_count    = inv.get("device_count") or "—"
        rate         = f"${float(inv.get('per_device_rate') or 0):.2f}" if inv.get("per_device_rate") is not None else "—"
        total        = f"${float(inv.get('total') or 0):,.2f}" if inv.get("total") is not None else "—"

        rows_html += (
            f'<div style="display:grid;grid-template-columns:2fr 1.5fr 1.5fr 0.8fr 0.8fr 1fr 0.9fr;gap:8px;'
            f'padding:0.5rem 1rem;background:{bg};border-bottom:1px solid #EEF2EE;'
            f'font-size:0.83rem;align-items:center">'
            f'<div style="font-weight:600;color:#1A1A1A;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{cust_label}</div>'
            f'<div style="color:#4A5A4A;font-size:0.8rem">{period_start}</div>'
            f'<div style="color:#4A5A4A;font-size:0.8rem">{period_end}</div>'
            f'<div style="color:#6B7B6B;text-align:right">{dev_count}</div>'
            f'<div style="color:#6B7B6B;text-align:right;font-family:monospace;font-size:0.8rem">{rate}</div>'
            f'<div style="font-weight:700;color:#1A1A1A;text-align:right;font-family:monospace">{total}</div>'
            f'<div>{status_b}</div>'
            f'</div>'
        )
    rows_html += '</div>'
    st.markdown(rows_html, unsafe_allow_html=True)

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

        gen_submitted = st.form_submit_button("Generate Invoice", use_container_width=False)

    if gen_submitted:
        if inv_end < inv_start:
            st.error("Period end must be after period start.")
        else:
            payload = {
                "customer_id":    cust_map[inv_cust],
                "period_start":   inv_start.isoformat(),
                "period_end":     inv_end.isoformat(),
                "per_device_rate": inv_rate,
            }
            with st.spinner("Generating invoice..."):
                result, err = client.generate_invoice(payload)
            if err:
                st.error(f"Invoice generation failed: {err}")
            else:
                st.success(f"Invoice generated for {inv_cust}. Refresh to see it in the list above.")
                st.rerun()
