import streamlit as st
from utils.styles import inject_css, badge, BRAND, STATUS_COLORS
from utils.formatters import fmt_datetime
from utils.auth import require_auth, current_user

st.set_page_config(page_title="Customers — RMM", layout="wide")
inject_css()

client = require_auth()

TIER_COLORS = {
    "standard":   "#3B82F6",
    "premium":    "#F59E0B",
    "enterprise": "#407E3C",
}

CARD = (
    "background:#FFFFFF;border-radius:12px;padding:1.2rem 1.5rem;"
    "border:1px solid #DDE8DD;box-shadow:0 2px 8px rgba(0,0,0,0.05);margin-bottom:1rem"
)

# ── Page header ────────────────────────────────────────────────────────────────
st.markdown('<h1 style="margin:0">Customers</h1><p style="color:#6B7B6B;margin:2px 0 1rem;font-size:0.88rem">Managed organizations and accounts</p>', unsafe_allow_html=True)

# ── Search + Add button row ────────────────────────────────────────────────────
sc1, sc2 = st.columns([4, 1])
with sc1:
    search_q = st.text_input("search", placeholder="Search by name, email, or address…", label_visibility="collapsed")
with sc2:
    show_add = st.button("+ Add Customer", use_container_width=True)

st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

# ── Fetch customers ────────────────────────────────────────────────────────────
with st.spinner("Loading customers..."):
    data, err = client.list_customers(page=1, per_page=50, q=search_q or "")
if err:
    st.warning(f"Could not load customers — {err}")
    st.stop()

customers = data.get("items", []) if data else []
total = data.get("total", len(customers)) if data else 0

st.markdown(
    f'<div style="font-size:0.8rem;color:#6B7B6B;margin-bottom:0.75rem">Showing <b>{len(customers)}</b> of <b>{total}</b> customers</div>',
    unsafe_allow_html=True,
)

# ── Customer cards ─────────────────────────────────────────────────────────────
if not customers:
    st.markdown(
        '<div style="' + CARD + ';text-align:center;padding:3rem 1.5rem">'
        '<div style="font-size:2.5rem;margin-bottom:0.75rem">&#127970;</div>'
        '<div style="font-size:1rem;font-weight:600;color:#1A1A1A;margin-bottom:0.25rem">No customers found</div>'
        '<div style="font-size:0.85rem;color:#6B7B6B">Add your first customer using the button above.</div>'
        '</div>',
        unsafe_allow_html=True,
    )
else:
    for cust in customers:
        cid = cust.get("id", "")
        name = cust.get("name", "Unnamed")
        tier = (cust.get("tier") or "standard").lower()
        tier_color = TIER_COLORS.get(tier, "#3B82F6")
        device_count = cust.get("device_count", 0) or 0
        online_count = cust.get("online_count", 0) or 0

        tier_badge_html = badge(tier, tier_color)
        expander_label = f"{name}  ·  {tier.capitalize()}  ·  {device_count} device{'s' if device_count != 1 else ''}"

        with st.expander(expander_label, expanded=False):
            # ── Tier + online summary row ──
            st.markdown(
                '<div style="display:flex;align-items:center;gap:8px;margin-bottom:0.9rem">'
                + tier_badge_html
                + f'<span style="font-size:0.78rem;color:#6B7B6B">{online_count} online / {device_count} total</span>'
                + '</div>',
                unsafe_allow_html=True,
            )

            left_col, right_col = st.columns(2)

            with left_col:
                st.markdown(
                    f'<div style="{CARD}">'
                    f'<div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#6B7B6B;margin-bottom:0.6rem">Contact Details</div>'
                    f'<div style="display:flex;gap:6px;margin-bottom:0.4rem"><span style="font-size:0.82rem;color:#6B7B6B;min-width:52px">Email</span><span style="font-size:0.82rem;color:#1A1A1A;font-weight:500">{cust.get("email") or "—"}</span></div>'
                    f'<div style="display:flex;gap:6px;margin-bottom:0.4rem"><span style="font-size:0.82rem;color:#6B7B6B;min-width:52px">Phone</span><span style="font-size:0.82rem;color:#1A1A1A;font-weight:500">{cust.get("phone") or "—"}</span></div>'
                    f'<div style="display:flex;gap:6px;margin-bottom:0.4rem"><span style="font-size:0.82rem;color:#6B7B6B;min-width:52px">Address</span><span style="font-size:0.82rem;color:#1A1A1A;font-weight:500">{cust.get("address") or "—"}</span></div>'
                    f'<div style="display:flex;gap:6px"><span style="font-size:0.82rem;color:#6B7B6B;min-width:52px">Notes</span><span style="font-size:0.82rem;color:#1A1A1A">{cust.get("notes") or "—"}</span></div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            with right_col:
                st.markdown(
                    f'<div style="{CARD}">'
                    f'<div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#6B7B6B;margin-bottom:0.6rem">Account Info</div>'
                    + tier_badge_html
                    + f'<div style="margin-top:0.6rem;display:flex;gap:6px;margin-bottom:0.4rem"><span style="font-size:0.82rem;color:#6B7B6B;min-width:80px">Created</span><span style="font-size:0.82rem;color:#1A1A1A;font-weight:500">{fmt_datetime(cust.get("created_at",""))}</span></div>'
                    f'<div style="display:flex;gap:6px;margin-bottom:0.4rem"><span style="font-size:0.82rem;color:#6B7B6B;min-width:80px">Devices</span><span style="font-size:0.82rem;color:#1A1A1A;font-weight:500">{device_count}</span></div>'
                    f'<div style="display:flex;gap:6px"><span style="font-size:0.82rem;color:#6B7B6B;min-width:80px">Online</span><span style="font-size:0.82rem;color:#22C55E;font-weight:600">{online_count}</span></div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            # ── Inline edit form ──
            st.markdown(
                '<div style="font-size:0.78rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#6B7B6B;margin:0.75rem 0 0.4rem">Edit Customer</div>',
                unsafe_allow_html=True,
            )
            with st.form(key=f"edit_form_{cid}"):
                e1, e2 = st.columns(2)
                with e1:
                    new_name = st.text_input("Name", value=name, key=f"name_{cid}")
                    new_email = st.text_input("Email", value=cust.get("email") or "", key=f"email_{cid}")
                    new_phone = st.text_input("Phone", value=cust.get("phone") or "", key=f"phone_{cid}")
                with e2:
                    tier_opts = ["standard", "premium", "enterprise"]
                    cur_idx = tier_opts.index(tier) if tier in tier_opts else 0
                    new_tier = st.selectbox("Tier", tier_opts, index=cur_idx, key=f"tier_{cid}")
                    new_notes = st.text_area("Notes", value=cust.get("notes") or "", height=100, key=f"notes_{cid}")
                save_clicked = st.form_submit_button("Save Changes")

            if save_clicked:
                if not new_name.strip():
                    st.error("Name is required.")
                else:
                    _, uerr = client.update_customer(cid, {
                        "name": new_name.strip(),
                        "email": new_email.strip(),
                        "phone": new_phone.strip(),
                        "tier": new_tier,
                        "notes": new_notes.strip(),
                    })
                    if uerr:
                        st.error(f"Update failed: {uerr}")
                    else:
                        st.success("Customer updated.")
                        st.rerun()

# ── Add Customer (collapsible at bottom) ──────────────────────────────────────
st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

with st.expander("+ Add New Customer", expanded=show_add):
    st.markdown(
        '<div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#6B7B6B;margin-bottom:0.75rem">New Customer Details</div>',
        unsafe_allow_html=True,
    )
    with st.form("add_customer_form"):
        ac1, ac2 = st.columns(2)
        with ac1:
            add_name = st.text_input("Company Name *")
            add_email = st.text_input("Email")
            add_phone = st.text_input("Phone")
            add_address = st.text_input("Address")
        with ac2:
            add_tier = st.selectbox("Tier", ["standard", "premium", "enterprise"])
            add_notes = st.text_area("Notes", height=120)
        submitted = st.form_submit_button("Create Customer", use_container_width=True)

    if submitted:
        if not add_name.strip():
            st.error("Company name is required.")
        else:
            result, cerr = client.create_customer({
                "name": add_name.strip(),
                "email": add_email.strip(),
                "phone": add_phone.strip(),
                "tier": add_tier,
                "address": add_address.strip(),
                "notes": add_notes.strip(),
            })
            if cerr:
                st.error(f"Failed to create customer: {cerr}")
            else:
                st.success(f"Customer '{add_name.strip()}' created.")
                st.rerun()
