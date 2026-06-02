"""Tickets — Helpdesk ticket management."""
import streamlit as st

from utils.auth import require_auth
from utils.styles import inject_css, badge, BRAND, STATUS_COLORS, section_header
from utils.formatters import fmt_datetime, PRIORITY_COLORS, SEVERITY_COLORS

st.set_page_config(page_title="Tickets — RMM", layout="wide")
inject_css()

client = require_auth()

# ── Page header ───────────────────────────────────────────────────────────────
st.markdown(
    '<h1 style="margin:0">Tickets</h1>'
    '<p style="color:#6B7B6B;margin:2px 0 1rem;font-size:0.88rem">Helpdesk ticket management</p>',
    unsafe_allow_html=True,
)

# ── New Ticket collapsible form ───────────────────────────────────────────────
with st.expander("+ New Ticket", expanded=False):
    cust_data, _ = client.list_customers(per_page=100)
    customers = (cust_data.get("items", []) if cust_data else [])
    cust_options = {c["name"]: c["id"] for c in customers}
    cust_names = list(cust_options.keys()) if cust_options else ["— no customers —"]

    with st.form("create_ticket_form", clear_on_submit=True):
        st.markdown(
            '<div style="background:#FFFFFF;border-radius:12px;padding:1.2rem 1.5rem;'
            'border:1px solid #DDE8DD;box-shadow:0 2px 8px rgba(0,0,0,0.05);margin-bottom:1rem">'
            + section_header("Create New Ticket", "Fill in the details below")
            + '</div>',
            unsafe_allow_html=True,
        )
        fc1, fc2 = st.columns([2, 1])
        with fc1:
            new_title = st.text_input("Title *", placeholder="Brief description of the issue")
        with fc2:
            new_priority = st.selectbox("Priority", ["medium", "low", "high", "critical"])
        new_desc = st.text_area("Description", placeholder="Detailed description…", height=100)
        fc3, fc4 = st.columns([2, 1])
        with fc3:
            new_customer = st.selectbox("Customer *", cust_names)
        with fc4:
            st.write("")
            st.write("")
            submitted = st.form_submit_button("Create Ticket", use_container_width=True)

    if submitted:
        if not new_title or not cust_options:
            st.error("Title and a valid customer are required.")
        else:
            _, err = client.create_ticket({
                "title": new_title,
                "description": new_desc,
                "customer_id": cust_options[new_customer],
                "priority": new_priority,
            })
            if err:
                st.error(f"Failed to create ticket: {err}")
            else:
                st.success("Ticket created successfully!")
                st.rerun()

# ── Filter bar ────────────────────────────────────────────────────────────────
st.markdown(
    '<div style="background:#FFF;border-radius:10px;padding:0.9rem 1.1rem;'
    'border:1px solid #DDE8DD;margin-bottom:1rem">',
    unsafe_allow_html=True,
)
fb1, fb2, fb3 = st.columns([3, 1.5, 1.5])
with fb1:
    search_q = st.text_input("Search tickets", placeholder="Search by title…", label_visibility="collapsed")
with fb2:
    status_f = st.selectbox(
        "Status",
        ["All", "open", "in_progress", "resolved", "closed"],
        label_visibility="collapsed",
    )
with fb3:
    priority_f = st.selectbox(
        "Priority",
        ["All", "critical", "high", "medium", "low"],
        label_visibility="collapsed",
    )
st.markdown('</div>', unsafe_allow_html=True)

# ── Load tickets ──────────────────────────────────────────────────────────────
api_filters: dict = {}
if status_f != "All":
    api_filters["status"] = status_f
if priority_f != "All":
    api_filters["priority"] = priority_f

with st.spinner("Loading tickets..."):
    data, err = client.list_tickets(**api_filters)
if err:
    st.warning(f"Could not load tickets — {err}")
    st.stop()

tickets = data.get("items", []) if data else []

# Client-side search filter
if search_q:
    q = search_q.lower()
    tickets = [t for t in tickets if q in t.get("title", "").lower() or q in (t.get("description") or "").lower()]

# ── Count caption ─────────────────────────────────────────────────────────────
st.caption(f"Showing {len(tickets)} ticket{'s' if len(tickets) != 1 else ''}")

# ── Ticket list ───────────────────────────────────────────────────────────────
if not tickets:
    st.markdown(
        '<div style="background:#FFFFFF;border-radius:12px;padding:2.5rem 1.5rem;'
        'border:1px solid #DDE8DD;box-shadow:0 2px 8px rgba(0,0,0,0.05);'
        'margin-bottom:1rem;text-align:center">'
        '<div style="font-size:2.5rem;margin-bottom:0.5rem">🎫</div>'
        '<div style="font-size:1rem;font-weight:600;color:#1A1A1A;margin-bottom:0.25rem">No tickets found</div>'
        '<div style="font-size:0.85rem;color:#6B7B6B">Try adjusting your filters or create a new ticket above.</div>'
        '</div>',
        unsafe_allow_html=True,
    )
else:
    STATUS_BADGE_COLORS = {
        "open":        BRAND["danger"],
        "in_progress": BRAND["warning"],
        "resolved":    BRAND["success"],
        "closed":      BRAND["muted"],
    }

    for t in tickets:
        priority_val = t.get("priority", "medium")
        status_val   = t.get("status", "open")
        p_color = PRIORITY_COLORS.get(priority_val, "#6B7B6B")
        s_color = STATUS_BADGE_COLORS.get(status_val, "#6B7B6B")
        customer_name = t.get("customer_name") or t.get("customer", {}).get("name", "—") if isinstance(t.get("customer"), dict) else t.get("customer_name", "—")
        created = fmt_datetime(t.get("created_at", ""))

        label_html = (
            badge(priority_val, p_color)
            + "&nbsp;&nbsp;"
            + f'<b style="color:#1A1A1A">{t.get("title", "Untitled")}</b>'
            + f'&nbsp;<span style="color:#6B7B6B;font-size:0.82rem">· {customer_name} · {created}</span>'
            + "&nbsp;&nbsp;"
            + badge(status_val, s_color)
        )

        with st.expander(t.get("title", "Untitled"), expanded=False):
            # Header row inside expander
            st.markdown(
                '<div style="display:flex;align-items:center;gap:10px;margin-bottom:0.75rem">'
                + badge(priority_val, p_color)
                + badge(status_val, s_color)
                + f'<span style="color:#6B7B6B;font-size:0.82rem">Customer: <b style="color:#1A1A1A">{customer_name}</b></span>'
                + f'<span style="color:#6B7B6B;font-size:0.82rem">Created: {created}</span>'
                + '</div>',
                unsafe_allow_html=True,
            )

            # Description
            desc_text = t.get("description") or "No description provided."
            st.markdown(
                '<div style="background:#F4F6F4;border-radius:8px;padding:0.75rem 1rem;'
                'border:1px solid #DDE8DD;margin-bottom:0.75rem;font-size:0.88rem;color:#1A1A1A">'
                + desc_text
                + '</div>',
                unsafe_allow_html=True,
            )

            col_status, col_comment = st.columns([1, 2])

            with col_status:
                st.markdown(section_header("Update Status"), unsafe_allow_html=True)
                statuses = ["open", "in_progress", "resolved", "closed"]
                cur_idx = statuses.index(status_val) if status_val in statuses else 0
                new_status = st.selectbox(
                    "Status",
                    statuses,
                    index=cur_idx,
                    key=f"status_sel_{t['id']}",
                    label_visibility="collapsed",
                )
                if st.button("Update Status", key=f"update_btn_{t['id']}"):
                    _, uerr = client.update_ticket(t["id"], {"status": new_status})
                    if uerr:
                        st.error(f"Update failed: {uerr}")
                    else:
                        st.success("Status updated.")
                        st.rerun()

            with col_comment:
                st.markdown(section_header("Add Comment"), unsafe_allow_html=True)
                with st.form(key=f"comment_form_{t['id']}", clear_on_submit=True):
                    comment_body = st.text_area(
                        "Comment",
                        placeholder="Type your comment here…",
                        height=80,
                        label_visibility="collapsed",
                        key=f"comment_text_{t['id']}",
                    )
                    cmt_col1, cmt_col2 = st.columns([1, 1])
                    with cmt_col1:
                        is_internal = st.checkbox("Internal note", key=f"internal_{t['id']}")
                    with cmt_col2:
                        cmt_submitted = st.form_submit_button("Post Comment", use_container_width=True)

                if cmt_submitted:
                    if not comment_body.strip():
                        st.warning("Comment cannot be empty.")
                    else:
                        _, cerr = client.add_comment(t["id"], comment_body, is_internal=is_internal)
                        if cerr:
                            st.error(f"Failed to post comment: {cerr}")
                        else:
                            st.success("Comment posted.")
                            st.rerun()
