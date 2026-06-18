"""Client Ticket Portal — clients submit and track their own tickets."""
import streamlit as st
from utils.auth import require_auth, logout
from utils.styles import inject_css, badge, BRAND
from utils.formatters import fmt_datetime, PRIORITY_COLORS

st.set_page_config(page_title="My Tickets — Support Portal", layout="wide")
inject_css()

api = require_auth()
me = st.session_state.get("user", {})
role = me.get("role", "")
my_name = me.get("full_name") or me.get("email", "Client")

# ── Access control ────────────────────────────────────────────────────────────
# Staff who land here get sent back to the staff dashboard
if role not in ("client",):
    st.switch_page("pages/02_Tickets.py")

# ── Minimal header (no RMM sidebar) ──────────────────────────────────────────
st.markdown(
    '<div style="display:flex;align-items:center;justify-content:space-between;'
    'padding:0.75rem 0;border-bottom:2px solid #407E3C;margin-bottom:1.5rem">'
    '<div>'
    '<span style="font-size:1.4rem;font-weight:800;color:#407E3C">Support Portal</span>'
    '<span style="font-size:0.8rem;color:#6B7B6B;margin-left:0.75rem">Submit and track your tickets</span>'
    '</div>'
    '<div style="display:flex;align-items:center;gap:0.5rem">'
    f'<span style="font-size:0.82rem;color:#6B7B6B">Logged in as <b style="color:#1A1A1A">{my_name}</b></span>'
    '</div>'
    '</div>',
    unsafe_allow_html=True,
)

# Sign-out button in top-right area
if st.button("Sign Out", key="client_signout"):
    logout()

STATUS_BADGE_COLORS = {
    "open":        BRAND["danger"],
    "in_progress": BRAND["warning"],
    "resolved":    BRAND["success"],
    "closed":      BRAND["muted"],
}

# ── New Ticket form ───────────────────────────────────────────────────────────
with st.expander("+ Submit New Ticket", expanded=False):
    with st.form("client_new_ticket", clear_on_submit=True):
        nt_title = st.text_input("Subject *", placeholder="Brief description of your issue")
        nt_priority = st.selectbox("Priority", ["low", "medium", "high", "critical"])
        nt_desc = st.text_area("Details", placeholder="Please describe your issue in full…", height=120)
        nt_submit = st.form_submit_button("Submit Ticket", use_container_width=True)
    if nt_submit:
        if not nt_title.strip():
            st.error("Subject is required.")
        else:
            _, terr = api.create_ticket({
                "title": nt_title.strip(),
                "description": nt_desc.strip() or None,
                "priority": nt_priority,
                # customer_id and department_id are auto-set by the API for client role
            })
            if terr:
                st.error(f"Could not submit ticket: {terr}")
            else:
                st.success("Ticket submitted. Our team will review it shortly.")
                st.rerun()

# ── Filter bar ────────────────────────────────────────────────────────────────
st.markdown(
    '<div style="background:#FFF;border-radius:10px;padding:0.9rem 1.1rem;'
    'border:1px solid #DDE8DD;margin-bottom:1rem">',
    unsafe_allow_html=True,
)
ff1, ff2 = st.columns([3, 1.5])
with ff1:
    search_q = st.text_input("Search", placeholder="Search tickets…", label_visibility="collapsed")
with ff2:
    status_f = st.selectbox("Status", ["All", "open", "in_progress", "resolved", "closed"],
                            label_visibility="collapsed")
st.markdown("</div>", unsafe_allow_html=True)

# ── Load tickets ──────────────────────────────────────────────────────────────
with st.spinner("Loading your tickets…"):
    data, err = api.list_tickets()

if err:
    st.warning(f"Could not load tickets — {err}")
    st.stop()

tickets = data.get("items", []) if data else []

if search_q:
    q = search_q.lower()
    tickets = [t for t in tickets if q in t.get("title", "").lower()
               or q in (t.get("description") or "").lower()]
if status_f != "All":
    tickets = [t for t in tickets if t.get("status") == status_f]

st.caption(f"{len(tickets)} ticket{'s' if len(tickets) != 1 else ''}")

if not tickets:
    st.markdown(
        '<div style="background:#FFFFFF;border-radius:12px;padding:2.5rem 1.5rem;'
        'border:1px solid #DDE8DD;text-align:center;margin-top:1rem">'
        '<div style="font-size:2rem;margin-bottom:0.5rem">🎫</div>'
        '<div style="font-size:1rem;font-weight:600;color:#1A1A1A;margin-bottom:0.25rem">No tickets yet</div>'
        '<div style="font-size:0.85rem;color:#6B7B6B">Use "Submit New Ticket" above to report an issue.</div>'
        '</div>',
        unsafe_allow_html=True,
    )
else:
    for t in tickets:
        tid = t["id"]
        priority_val = t.get("priority", "medium")
        status_val = t.get("status", "open")
        p_color = PRIORITY_COLORS.get(priority_val, "#6B7B6B")
        s_color = STATUS_BADGE_COLORS.get(status_val, "#6B7B6B")
        created = fmt_datetime(t.get("created_at", ""))
        assignee = t.get("assignee_name") or "Unassigned"

        with st.expander(t.get("title", "Untitled"), expanded=False):
            st.markdown(
                '<div style="display:flex;align-items:center;gap:10px;margin-bottom:0.75rem">'
                + badge(priority_val, p_color)
                + badge(status_val, s_color)
                + f'<span style="font-size:0.8rem;color:#6B7B6B">Submitted: {created}</span>'
                + f'<span style="font-size:0.8rem;color:#6B7B6B">Assigned to: <b style="color:#1A1A1A">{assignee}</b></span>'
                + '</div>',
                unsafe_allow_html=True,
            )

            desc = t.get("description") or "No description provided."
            st.markdown(
                '<div style="background:#F4F6F4;border-radius:8px;padding:0.75rem 1rem;'
                'border:1px solid #DDE8DD;margin-bottom:0.75rem;font-size:0.88rem;color:#1A1A1A">'
                + desc + '</div>',
                unsafe_allow_html=True,
            )

            # Comments — load on expand (via get_ticket)
            detail, derr = api.get_ticket(tid)
            if not derr and detail:
                comments = detail.get("comments", [])
                # Show only non-internal comments to clients
                public_comments = [c for c in comments if not c.get("is_internal")]
                if public_comments:
                    st.markdown(
                        '<div style="font-size:0.75rem;font-weight:700;text-transform:uppercase;'
                        'letter-spacing:0.07em;color:#6B7B6B;margin-bottom:0.4rem">Updates</div>',
                        unsafe_allow_html=True,
                    )
                    for c in public_comments:
                        c_time = fmt_datetime(c.get("created_at", ""))
                        st.markdown(
                            f'<div style="background:#F9FBF9;border-left:3px solid #407E3C;'
                            f'padding:0.5rem 0.75rem;border-radius:0 6px 6px 0;'
                            f'margin-bottom:0.4rem;font-size:0.83rem;color:#1A1A1A">'
                            f'{c["body"]}'
                            f'<div style="font-size:0.72rem;color:#6B7B6B;margin-top:3px">{c_time}</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

            # Client reply form (only for open/in_progress tickets)
            if status_val in ("open", "in_progress"):
                with st.form(f"client_reply_{tid}", clear_on_submit=True):
                    reply_body = st.text_area("Add a reply", height=70,
                                              label_visibility="collapsed",
                                              placeholder="Type your reply here…",
                                              key=f"client_reply_text_{tid}")
                    if st.form_submit_button("Send Reply", use_container_width=True):
                        if not reply_body.strip():
                            st.warning("Reply cannot be empty.")
                        else:
                            _, cerr = api.add_comment(tid, reply_body.strip(), is_internal=False)
                            if cerr:
                                st.error(f"Could not send reply: {cerr}")
                            else:
                                st.success("Reply sent.")
                                st.rerun()
