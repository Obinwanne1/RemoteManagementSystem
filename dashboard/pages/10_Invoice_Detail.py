"""Invoice Detail — Professional A4 invoice view with PDF download and email delivery."""
import base64
import streamlit as st
from datetime import datetime

from utils.auth import require_auth
from utils.nav import render_sidebar
from utils.styles import inject_css, badge, BRAND

st.set_page_config(page_title="Invoice — RMM", layout="wide")
inject_css()

client = require_auth()
render_sidebar()

# ── Resolve invoice ID ────────────────────────────────────────────────────────
inv_id = st.session_state.get("_view_invoice_id")
if not inv_id:
    st.warning("No invoice selected. Return to Billing.")
    if st.button("← Back to Billing"):
        st.switch_page("pages/09_Billing.py")
    st.stop()

# ── Load data ─────────────────────────────────────────────────────────────────
with st.spinner("Loading invoice..."):
    inv_data, inv_err = client.get_invoice(inv_id)
    org_data, _ = client.get_org_settings()

if inv_err:
    st.error(f"Could not load invoice — {inv_err}")
    if st.button("← Back to Billing"):
        st.switch_page("pages/09_Billing.py")
    st.stop()

inv = inv_data
org = org_data or {}

# Load customer name for display
cust_data, _ = client.list_customers(per_page=200)
customers = (cust_data or {}).get("items", [])
cust_map_by_id = {c["id"]: c for c in customers}
customer = cust_map_by_id.get(str(inv.get("customer_id", ""))) or {}

# ── Status helpers ────────────────────────────────────────────────────────────
STATUS_COLORS = {
    "paid":    "#22C55E",
    "sent":    "#3B82F6",
    "overdue": "#EF4444",
    "draft":   "#9CA3AF",
}
status_raw = (inv.get("status") or "draft").lower()
status_color = STATUS_COLORS.get(status_raw, "#9CA3AF")

# ── Action bar ────────────────────────────────────────────────────────────────
back_col, spacer, action_cols = st.columns([1.5, 3, 4])

with back_col:
    if st.button("← Billing", use_container_width=True):
        st.switch_page("pages/09_Billing.py")

with action_cols:
    a1, a2, a3, a4, a5 = st.columns(5)

    # Download PDF
    with a1:
        pdf_bytes, pdf_err = client.get_invoice_pdf_bytes(inv_id)
        inv_num = inv.get("invoice_number") or inv_id[:8]
        if pdf_err:
            st.button("⬇ PDF", disabled=True, help=f"PDF unavailable: {pdf_err}",
                      use_container_width=True)
        else:
            st.download_button(
                "⬇ PDF",
                data=pdf_bytes,
                file_name=f"invoice-{inv_num}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

    # Send email
    with a2:
        cust_email = customer.get("email") or ""
        email_label = f"✉ Email" if cust_email else "✉ No Email"
        if st.button(email_label, use_container_width=True,
                     disabled=not cust_email,
                     help=f"Send to {cust_email}" if cust_email else "Customer has no email"):
            with st.spinner("Sending..."):
                _, send_err = client.send_invoice_email(inv_id)
            if send_err:
                st.error(f"Email failed: {send_err}")
            else:
                st.success(f"Invoice emailed to {cust_email}")

    # Status transitions
    with a3:
        if status_raw == "draft":
            if st.button("Mark Sent", use_container_width=True):
                _, e = client.update_invoice_status(inv_id, "sent")
                st.rerun() if not e else st.error(e)
        elif status_raw in ("sent", "overdue"):
            if st.button("Mark Paid", use_container_width=True, type="primary"):
                _, e = client.update_invoice_status(inv_id, "paid")
                st.rerun() if not e else st.error(e)

    with a4:
        if status_raw == "sent":
            if st.button("Overdue", use_container_width=True):
                _, e = client.update_invoice_status(inv_id, "overdue")
                st.rerun() if not e else st.error(e)

    # Delete
    with a5:
        if st.button("🗑 Delete", use_container_width=True):
            if st.session_state.get("_del_inv_confirm"):
                _, e = client.delete_invoice(inv_id)
                if not e:
                    st.session_state.pop("_view_invoice_id", None)
                    st.session_state.pop("_del_inv_confirm", None)
                    st.switch_page("pages/09_Billing.py")
                else:
                    st.error(e)
            else:
                st.session_state["_del_inv_confirm"] = True
                st.rerun()

if st.session_state.get("_del_inv_confirm"):
    st.warning("Click 🗑 Delete again to confirm permanent deletion.")

st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

# ── Invoice document ──────────────────────────────────────────────────────────
def _fmt_date(s):
    if not s:
        return "—"
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.strftime("%d %B %Y")
    except Exception:
        return s[:10]

def _fmt_money(v):
    try:
        return f"${float(v):,.2f}"
    except Exception:
        return "—"

company_name    = org.get("company_name") or ""
company_address = org.get("company_address") or ""
company_email   = org.get("company_email") or ""
company_phone   = org.get("company_phone") or ""
payment_terms   = org.get("payment_terms") or "Net 30"
bank_details    = org.get("bank_details") or ""
footer_notes    = org.get("footer_notes") or "Thank you for your business!"
logo_data       = org.get("logo_data") or ""

cust_name    = customer.get("name") or "—"
cust_email   = customer.get("email") or ""
cust_phone   = customer.get("phone") or ""
cust_address = customer.get("address") or ""

inv_num       = inv.get("invoice_number") or inv_id[:8].upper()
issue_date    = _fmt_date(inv.get("created_at"))
due_date      = _fmt_date(inv.get("due_date"))
period_start  = _fmt_date(inv.get("period_start"))
period_end    = _fmt_date(inv.get("period_end"))
subtotal      = float(inv.get("subtotal") or 0)
tax           = float(inv.get("tax") or 0)
tax_rate_pct  = float(inv.get("tax_rate") or 0) * 100
total         = float(inv.get("total") or 0)
line_items    = inv.get("line_items") or []
notes         = inv.get("notes") or ""

# Build logo img tag
logo_html = ""
if logo_data:
    logo_html = f'<img src="{logo_data}" style="max-height:56px;max-width:180px;object-fit:contain;margin-bottom:8px;display:block">'

# Build company block
company_html = ""
if company_name:
    company_html += f'<div style="font-size:1.05rem;font-weight:700;color:#1A2B1A;line-height:1.3">{company_name}</div>'
addr_parts = [p for p in [company_address, company_email, company_phone] if p]
if addr_parts:
    for part in addr_parts:
        company_html += f'<div style="font-size:0.8rem;color:#6B7B6B;line-height:1.5">{part}</div>'

# Build customer block
bill_to_html = f'<div style="font-size:1rem;font-weight:700;color:#1A2B1A;margin-bottom:4px">{cust_name}</div>'
bill_detail_parts = [p for p in [cust_address, cust_email, cust_phone] if p]
for part in bill_detail_parts:
    bill_to_html += f'<div style="font-size:0.82rem;color:#4A5A4A;line-height:1.5">{part}</div>'

# Build line items rows
line_rows_html = ""
if line_items:
    for i, item in enumerate(line_items):
        bg = "#FAFCFA" if i % 2 == 0 else "#FFFFFF"
        desc = item.get("description", "Service")
        qty  = item.get("quantity") or inv.get("device_count") or 1
        rate = item.get("rate") or inv.get("per_device_rate") or 0
        amount = item.get("amount") or 0
        line_rows_html += f'''
        <tr style="background:{bg}">
          <td style="padding:10px 14px;font-size:0.85rem;color:#1A1A1A">{desc}</td>
          <td style="padding:10px 14px;font-size:0.85rem;color:#4A5A4A;text-align:center">{qty}</td>
          <td style="padding:10px 14px;font-size:0.85rem;color:#4A5A4A;text-align:right;font-family:monospace">{_fmt_money(rate)}</td>
          <td style="padding:10px 14px;font-size:0.85rem;color:#1A1A1A;font-weight:600;text-align:right;font-family:monospace">{_fmt_money(amount)}</td>
        </tr>'''
else:
    line_rows_html = f'''
    <tr style="background:#FAFCFA">
      <td style="padding:10px 14px;font-size:0.85rem;color:#1A1A1A">Managed Devices — Service Period</td>
      <td style="padding:10px 14px;font-size:0.85rem;text-align:center">{inv.get("device_count") or "—"}</td>
      <td style="padding:10px 14px;font-size:0.85rem;text-align:right;font-family:monospace">{_fmt_money(inv.get("per_device_rate") or 0)}</td>
      <td style="padding:10px 14px;font-size:0.85rem;font-weight:600;text-align:right;font-family:monospace">{_fmt_money(subtotal)}</td>
    </tr>'''

# Bank details block
bank_html = ""
if bank_details:
    bank_lines = bank_details.replace("\n", "<br>")
    bank_html = f'''
    <div style="margin-bottom:16px">
      <div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:#6B7B6B;margin-bottom:6px">Payment Details</div>
      <div style="font-size:0.82rem;color:#4A5A4A;line-height:1.6">{bank_lines}</div>
    </div>'''

notes_html = ""
if notes:
    notes_lines = notes.replace("\n", "<br>")
    notes_html = f'''
    <div style="margin-bottom:16px">
      <div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:#6B7B6B;margin-bottom:6px">Notes</div>
      <div style="font-size:0.82rem;color:#4A5A4A;line-height:1.6">{notes_lines}</div>
    </div>'''

status_badge_html = f'<span style="background:{status_color}22;color:{status_color};border:1px solid {status_color}44;padding:3px 10px;border-radius:5px;font-size:0.72rem;font-weight:700;letter-spacing:0.05em">{status_raw.upper()}</span>'

invoice_html = f"""
<div style="max-width:820px;margin:0 auto;background:#FFFFFF;border-radius:14px;
     border:1px solid #DDE8DD;box-shadow:0 4px 24px rgba(0,0,0,0.07);
     padding:40px 48px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">

  <!-- HEADER -->
  <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:32px">
    <div>
      {logo_html}
      {company_html}
    </div>
    <div style="text-align:right">
      <div style="font-size:2rem;font-weight:800;color:#407E3C;letter-spacing:-0.02em;line-height:1">INVOICE</div>
      <div style="font-size:1rem;font-weight:600;color:#1A2B1A;margin-top:4px">#{inv_num}</div>
      <div style="margin-top:12px">{status_badge_html}</div>
      <div style="margin-top:14px;display:grid;grid-template-columns:auto auto;gap:2px 16px;text-align:right">
        <div style="font-size:0.7rem;text-transform:uppercase;letter-spacing:0.07em;color:#9CA3AF">Issue Date</div>
        <div style="font-size:0.82rem;font-weight:600;color:#1A1A1A">{issue_date}</div>
        <div style="font-size:0.7rem;text-transform:uppercase;letter-spacing:0.07em;color:#9CA3AF">Due Date</div>
        <div style="font-size:0.82rem;font-weight:600;color:#EF4444">{due_date}</div>
      </div>
    </div>
  </div>

  <!-- DIVIDER -->
  <div style="border-top:2px solid #407E3C;margin-bottom:28px"></div>

  <!-- BILL TO + PERIOD -->
  <div style="display:flex;justify-content:space-between;margin-bottom:32px">
    <div>
      <div style="font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:#9CA3AF;margin-bottom:8px">Bill To</div>
      {bill_to_html}
    </div>
    <div style="text-align:right">
      <div style="font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:#9CA3AF;margin-bottom:8px">Service Period</div>
      <div style="font-size:0.9rem;font-weight:600;color:#1A1A1A">{period_start} – {period_end}</div>
      <div style="margin-top:10px">
        <div style="font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:#9CA3AF;margin-bottom:4px">Payment Terms</div>
        <div style="font-size:0.82rem;color:#4A5A4A">{payment_terms}</div>
      </div>
    </div>
  </div>

  <!-- LINE ITEMS TABLE -->
  <table style="width:100%;border-collapse:collapse;margin-bottom:20px">
    <thead>
      <tr style="background:#407E3C">
        <th style="padding:10px 14px;text-align:left;font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:#FFFFFF">Description</th>
        <th style="padding:10px 14px;text-align:center;font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:#FFFFFF;width:60px">Qty</th>
        <th style="padding:10px 14px;text-align:right;font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:#FFFFFF;width:110px">Unit Rate</th>
        <th style="padding:10px 14px;text-align:right;font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:#FFFFFF;width:110px">Amount</th>
      </tr>
    </thead>
    <tbody>
      {line_rows_html}
    </tbody>
  </table>

  <!-- TOTALS -->
  <div style="display:flex;justify-content:flex-end;margin-bottom:32px">
    <div style="min-width:260px">
      <div style="display:flex;justify-content:space-between;padding:7px 0;border-bottom:1px solid #EEF2EE">
        <span style="font-size:0.85rem;color:#6B7B6B">Subtotal</span>
        <span style="font-size:0.85rem;color:#1A1A1A;font-family:monospace">{_fmt_money(subtotal)}</span>
      </div>
      <div style="display:flex;justify-content:space-between;padding:7px 0;border-bottom:1px solid #EEF2EE">
        <span style="font-size:0.85rem;color:#6B7B6B">Tax ({tax_rate_pct:.1f}%)</span>
        <span style="font-size:0.85rem;color:#1A1A1A;font-family:monospace">{_fmt_money(tax)}</span>
      </div>
      <div style="display:flex;justify-content:space-between;padding:12px 14px;background:#407E3C;border-radius:8px;margin-top:8px">
        <span style="font-size:0.95rem;font-weight:700;color:#FFFFFF">Total Due</span>
        <span style="font-size:0.95rem;font-weight:800;color:#FFFFFF;font-family:monospace">{_fmt_money(total)}</span>
      </div>
    </div>
  </div>

  <!-- FOOTER -->
  <div style="border-top:1px solid #DDE8DD;padding-top:24px">
    <div style="display:flex;justify-content:space-between;align-items:flex-start">
      <div style="flex:1">
        {bank_html}
        {notes_html}
      </div>
      <div style="text-align:right;flex-shrink:0;margin-left:32px">
        <div style="font-size:0.9rem;font-style:italic;color:#407E3C;margin-bottom:6px">{footer_notes}</div>
        {'<div style="font-size:0.78rem;color:#9CA3AF">' + company_email + '</div>' if company_email else ''}
      </div>
    </div>
  </div>

</div>
"""

import streamlit.components.v1 as components
components.html(invoice_html, height=950, scrolling=True)
