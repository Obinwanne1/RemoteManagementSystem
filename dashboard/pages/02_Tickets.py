"""Tickets — Helpdesk ticket management."""
import streamlit as st
from datetime import datetime, timezone

from utils.auth import require_auth
from utils.nav import render_sidebar
from utils.styles import inject_css, badge, BRAND, STATUS_COLORS, section_header
from utils.formatters import fmt_datetime, PRIORITY_COLORS, SEVERITY_COLORS


def _sla_badge(ticket: dict) -> str:
    """Return HTML SLA badge. Red if breached, orange if <2h left, grey if resolved."""
    status = ticket.get("status", "open")
    if status in ("resolved", "closed"):
        return ""
    if ticket.get("sla_breached"):
        return '<span style="background:#DC2626;color:#fff;font-size:0.72rem;font-weight:700;padding:2px 8px;border-radius:999px">SLA BREACHED</span>'
    due = ticket.get("due_date")
    if not due:
        return ""
    try:
        due_dt = datetime.fromisoformat(due.replace("Z", "+00:00"))
        diff = due_dt - datetime.now(timezone.utc)
        hours_left = diff.total_seconds() / 3600
        if hours_left < 0:
            return '<span style="background:#DC2626;color:#fff;font-size:0.72rem;font-weight:700;padding:2px 8px;border-radius:999px">SLA BREACHED</span>'
        elif hours_left < 2:
            return f'<span style="background:#F59E0B;color:#fff;font-size:0.72rem;font-weight:700;padding:2px 8px;border-radius:999px">Due {int(hours_left*60)}m</span>'
        elif hours_left < 24:
            return f'<span style="background:#D97706;color:#fff;font-size:0.72rem;font-weight:600;padding:2px 8px;border-radius:999px">Due {int(hours_left)}h</span>'
        else:
            days = int(hours_left / 24)
            return f'<span style="background:#6B7B6B;color:#fff;font-size:0.72rem;font-weight:600;padding:2px 8px;border-radius:999px">Due {days}d</span>'
    except Exception:
        return ""

st.set_page_config(page_title="Tickets — RMM", layout="wide")
inject_css()

client = require_auth()
render_sidebar()

me = st.session_state.get("user", {})
my_id = me.get("id")
my_role = me.get("role", "technician")
is_admin = my_role in ("admin", "superadmin")

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

# ── View tabs ─────────────────────────────────────────────────────────────────
tab_all, tab_mine, tab_unassigned = st.tabs(["All Tickets", "My Tickets", "Unassigned"])

def _render_tickets(tickets_list: list, tab_key: str) -> None:
    """Render the filter bar + ticket list for a given tab."""

    # ── Filter bar ────────────────────────────────────────────────────────────
    st.markdown(
        '<div style="background:#FFF;border-radius:10px;padding:0.9rem 1.1rem;'
        'border:1px solid #DDE8DD;margin-bottom:1rem">',
        unsafe_allow_html=True,
    )
    fb1, fb2, fb3 = st.columns([3, 1.5, 1.5])
    with fb1:
        search_q = st.text_input(
            "Search tickets", placeholder="Search by title…",
            label_visibility="collapsed", key=f"search_{tab_key}",
        )
    with fb2:
        priority_f = st.selectbox(
            "Priority", ["All", "critical", "high", "medium", "low"],
            label_visibility="collapsed", key=f"priority_{tab_key}",
        )
    with fb3:
        status_f = st.selectbox(
            "Status", ["All", "open", "in_progress", "resolved", "closed"],
            label_visibility="collapsed", key=f"status_{tab_key}",
        )
    st.markdown('</div>', unsafe_allow_html=True)

    # Client-side filters
    tickets = tickets_list
    if search_q:
        q = search_q.lower()
        tickets = [t for t in tickets if q in t.get("title", "").lower() or q in (t.get("description") or "").lower()]
    if priority_f != "All":
        tickets = [t for t in tickets if t.get("priority") == priority_f]
    if status_f != "All":
        tickets = [t for t in tickets if t.get("status") == status_f]

    # ── Count caption + CSV export ────────────────────────────────────────────
    cap_col, export_col = st.columns([6, 1])
    with cap_col:
        st.caption(f"Showing {len(tickets)} ticket{'s' if len(tickets) != 1 else ''}")
    with export_col:
        if tickets:
            import pandas as pd
            _df = pd.DataFrame([{
                "ID": t.get("id", ""), "Title": t.get("title", ""),
                "Status": t.get("status", ""), "Priority": t.get("priority", ""),
                "Customer": t.get("customer_name", ""), "Assignee": t.get("assignee_name", ""),
                "Created": t.get("created_at", ""), "Updated": t.get("updated_at", ""),
            } for t in tickets])
            st.download_button(
                "Export CSV", data=_df.to_csv(index=False).encode("utf-8"),
                file_name="tickets.csv", mime="text/csv",
                use_container_width=True, key=f"export_{tab_key}",
            )

    # ── Ticket list ───────────────────────────────────────────────────────────
    if not tickets:
        st.markdown(
            '<div style="background:#FFFFFF;border-radius:12px;padding:2.5rem 1.5rem;'
            'border:1px solid #DDE8DD;box-shadow:0 2px 8px rgba(0,0,0,0.05);'
            'margin-bottom:1rem;text-align:center">'
            '<div style="font-size:2rem;margin-bottom:0.5rem"><i class="fa-solid fa-ticket" style="color:#6B7B6B"></i></div>'
            '<div style="font-size:1rem;font-weight:600;color:#1A1A1A;margin-bottom:0.25rem">No tickets found</div>'
            '<div style="font-size:0.85rem;color:#6B7B6B">Try adjusting your filters or create a new ticket above.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    STATUS_BADGE_COLORS = {
        "open":        BRAND["danger"],
        "in_progress": BRAND["warning"],
        "resolved":    BRAND["success"],
        "closed":      BRAND["muted"],
    }

    # Load user list once per render (for assignment dropdowns)
    users_data, _ = client.list_users()
    all_users = [u for u in (users_data.get("users", []) if isinstance(users_data, dict) else []) if u.get("is_active", True)]

    for t in tickets:
        priority_val = t.get("priority", "medium")
        status_val   = t.get("status", "open")
        p_color = PRIORITY_COLORS.get(priority_val, "#6B7B6B")
        s_color = STATUS_BADGE_COLORS.get(status_val, "#6B7B6B")
        customer_name = (
            t.get("customer_name")
            or (t.get("customer", {}).get("name", "—") if isinstance(t.get("customer"), dict) else "—")
        )
        created = fmt_datetime(t.get("created_at", ""))
        tid = t["id"]

        with st.expander(t.get("title", "Untitled"), expanded=False):
            # Header row
            st.markdown(
                '<div style="display:flex;align-items:center;gap:10px;margin-bottom:0.75rem">'
                + badge(priority_val, p_color)
                + badge(status_val, s_color)
                + _sla_badge(t)
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

            col_status, col_assign, col_comment = st.columns([1, 1, 2])

            # ── Status ────────────────────────────────────────────────────────
            with col_status:
                st.markdown(section_header("Update Status"), unsafe_allow_html=True)
                statuses = ["open", "in_progress", "resolved", "closed"]
                cur_idx = statuses.index(status_val) if status_val in statuses else 0
                new_status = st.selectbox(
                    "Status", statuses, index=cur_idx,
                    key=f"status_sel_{tab_key}_{tid}", label_visibility="collapsed",
                )
                if st.button("Update Status", key=f"update_btn_{tab_key}_{tid}"):
                    _, uerr = client.update_ticket(tid, {"status": new_status})
                    if uerr:
                        st.error(f"Update failed: {uerr}")
                    else:
                        st.success("Status updated.")
                        st.rerun()

            # ── Assignment ────────────────────────────────────────────────────
            with col_assign:
                st.markdown(section_header("Assignment"), unsafe_allow_html=True)
                cur_assignee = t.get("assignee_id")
                assigned_to_me = (cur_assignee == my_id)

                if is_admin:
                    # Admin: full dropdown + Assign to Me shortcut
                    user_opts = {"— Unassigned —": None}
                    user_opts.update({
                        u.get("full_name") or u.get("email", u["id"]): u["id"]
                        for u in all_users
                    })
                    cur_label = next((k for k, v in user_opts.items() if v == cur_assignee), "— Unassigned —")
                    cur_idx2 = list(user_opts.keys()).index(cur_label) if cur_label in user_opts else 0
                    new_assignee_label = st.selectbox(
                        "Assignee", list(user_opts.keys()), index=cur_idx2,
                        key=f"assignee_sel_{tab_key}_{tid}", label_visibility="collapsed",
                    )
                    a_col1, a_col2 = st.columns(2)
                    with a_col1:
                        if st.button("Assign", key=f"assign_btn_{tab_key}_{tid}", use_container_width=True):
                            new_uid = user_opts[new_assignee_label]
                            _, aerr = client.update_ticket(tid, {"assignee_id": new_uid})
                            if aerr:
                                st.error(f"Assign failed: {aerr}")
                            else:
                                st.success("Assigned.")
                                st.rerun()
                    with a_col2:
                        if st.button("Assign to Me", key=f"assignme_admin_{tab_key}_{tid}", use_container_width=True):
                            _, aerr = client.update_ticket(tid, {"assignee_id": my_id})
                            if aerr:
                                st.error(f"Assign failed: {aerr}")
                            else:
                                st.success("Assigned to you.")
                                st.rerun()

                else:
                    # Technician / viewer: self-assign + forward
                    if assigned_to_me:
                        st.markdown(
                            '<div style="background:#E8F5E8;border:1px solid #407E3C;border-radius:6px;'
                            'padding:0.4rem 0.75rem;font-size:0.82rem;color:#407E3C;font-weight:600;'
                            'margin-bottom:0.5rem">✓ Assigned to you</div>',
                            unsafe_allow_html=True,
                        )
                    else:
                        if st.button("Assign to Me", key=f"assignme_{tab_key}_{tid}", use_container_width=True):
                            _, aerr = client.update_ticket(tid, {"assignee_id": my_id})
                            if aerr:
                                st.error(f"Assign failed: {aerr}")
                            else:
                                st.success("Assigned to you.")
                                st.rerun()

                    # Forward section (always visible for non-admins)
                    st.markdown(
                        '<div style="font-size:0.78rem;color:#6B7B6B;margin-top:0.6rem;margin-bottom:0.2rem">'
                        'Forward to</div>',
                        unsafe_allow_html=True,
                    )
                    others = [u for u in all_users if u.get("id") != my_id]
                    if others:
                        fwd_opts = {u.get("full_name") or u.get("email", u["id"]): u["id"] for u in others}
                        fwd_label = st.selectbox(
                            "Forward to", list(fwd_opts.keys()),
                            key=f"fwd_sel_{tab_key}_{tid}", label_visibility="collapsed",
                        )
                        if st.button("Forward", key=f"fwd_btn_{tab_key}_{tid}", use_container_width=True):
                            _, ferr = client.update_ticket(tid, {"assignee_id": fwd_opts[fwd_label]})
                            if ferr:
                                st.error(f"Forward failed: {ferr}")
                            else:
                                st.success(f"Forwarded to {fwd_label}.")
                                st.rerun()
                    else:
                        st.caption("No other users to forward to.")

            # ── Comments ──────────────────────────────────────────────────────
            with col_comment:
                st.markdown(section_header("Add Comment"), unsafe_allow_html=True)
                with st.form(key=f"comment_form_{tab_key}_{tid}", clear_on_submit=True):
                    comment_body = st.text_area(
                        "Comment", placeholder="Type your comment here…",
                        height=80, label_visibility="collapsed",
                        key=f"comment_text_{tab_key}_{tid}",
                    )
                    cmt_col1, cmt_col2 = st.columns([1, 1])
                    with cmt_col1:
                        is_internal = st.checkbox("Internal note", key=f"internal_{tab_key}_{tid}")
                    with cmt_col2:
                        cmt_submitted = st.form_submit_button("Post Comment", use_container_width=True)

                if cmt_submitted:
                    if not comment_body.strip():
                        st.warning("Comment cannot be empty.")
                    else:
                        _, cerr = client.add_comment(tid, comment_body, is_internal=is_internal)
                        if cerr:
                            st.error(f"Failed to post comment: {cerr}")
                        else:
                            st.success("Comment posted.")
                            st.rerun()


# ── Load and render per tab ───────────────────────────────────────────────────
with tab_all:
    with st.spinner("Loading tickets..."):
        data, err = client.list_tickets()
    if err:
        st.warning(f"Could not load tickets — {err}")
    else:
        _render_tickets(data.get("items", []) if data else [], "all")

with tab_mine:
    with st.spinner("Loading your tickets..."):
        data_mine, err_mine = client.list_tickets(assignee_id=my_id)
    if err_mine:
        st.warning(f"Could not load tickets — {err_mine}")
    else:
        _render_tickets(data_mine.get("items", []) if data_mine else [], "mine")

with tab_unassigned:
    with st.spinner("Loading unassigned tickets..."):
        data_all, err_all = client.list_tickets()
    if err_all:
        st.warning(f"Could not load tickets — {err_all}")
    else:
        all_items = data_all.get("items", []) if data_all else []
        unassigned = [t for t in all_items if not t.get("assignee_id")]
        _render_tickets(unassigned, "unassigned")
