"""Client Ticket Detail — view updates and reply to a ticket."""
import streamlit as st
from utils.auth import require_auth, logout
from utils.styles import inject_css, badge, BRAND
from utils.formatters import fmt_datetime, PRIORITY_COLORS

STATUS_BADGE_COLORS = {
    "open":        BRAND["danger"],
    "in_progress": BRAND["warning"],
    "resolved":    BRAND["success"],
    "closed":      BRAND["muted"],
}

st.set_page_config(page_title="Ticket Detail — Support Portal", layout="wide")
inject_css()

api = require_auth()
me = st.session_state.get("user", {})
role = me.get("role", "")

if role not in ("client",):
    st.switch_page("pages/02_Tickets.py")

# ── Back navigation ───────────────────────────────────────────────────────────
hdr_c, signout_c = st.columns([9, 1])
with hdr_c:
    if st.button("← Back to My Tickets", key="client_back_btn"):
        st.switch_page("pages/21_Client_Tickets.py")
with signout_c:
    if st.button("Sign Out", key="client_detail_signout"):
        logout()

ticket_id = st.session_state.get("_nav_ticket_id")
if not ticket_id:
    st.error("No ticket selected.")
    st.stop()

# ── Fetch ticket ──────────────────────────────────────────────────────────────
with st.spinner("Loading ticket…"):
    ticket, err = api.get_ticket(ticket_id)

if err or not ticket:
    st.error(f"Could not load ticket #{ticket_id}: {err or 'not found'}")
    st.stop()

priority_val = ticket.get("priority", "medium")
status_val   = ticket.get("status", "open")
p_color      = PRIORITY_COLORS.get(priority_val, "#6B7B6B")
s_color      = STATUS_BADGE_COLORS.get(status_val, "#6B7B6B")
created      = fmt_datetime(ticket.get("created_at", ""))

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(
    '<div style="border-bottom:2px solid #407E3C;padding-bottom:0.5rem;margin-bottom:1rem">'
    '<span style="font-size:1.4rem;font-weight:800;color:#407E3C">Support Portal</span>'
    "</div>",
    unsafe_allow_html=True,
)

st.markdown(
    f'<h2 style="margin:0 0 0.3rem">#{ticket_id} — {ticket.get("title", "Untitled")}</h2>',
    unsafe_allow_html=True,
)

st.markdown(
    f'<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:0.4rem">'
    + badge(priority_val, p_color)
    + badge(status_val.replace("_", " "), s_color)
    + "</div>"
    + f'<div style="font-size:0.82rem;color:#6B7B6B;margin-bottom:1rem">Submitted: {created}</div>',
    unsafe_allow_html=True,
)

# ── Description ───────────────────────────────────────────────────────────────
desc = ticket.get("description") or "No description provided."
st.markdown(
    '<div style="background:#F4F6F4;border-radius:8px;padding:0.85rem 1.1rem;'
    'border:1px solid #DDE8DD;border-left:4px solid #407E3C;'
    'margin-bottom:1.25rem;font-size:0.88rem;color:#1A1A1A">'
    '<div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;'
    'letter-spacing:0.06em;color:#6B7B6B;margin-bottom:0.4rem">Your Request</div>'
    + desc
    + "</div>",
    unsafe_allow_html=True,
)

# ── Comments (public only) ────────────────────────────────────────────────────
comments = ticket.get("comments", [])
public_comments = [c for c in comments if not c.get("is_internal")]

if public_comments:
    st.markdown(
        '<div style="font-size:0.75rem;font-weight:700;text-transform:uppercase;'
        'letter-spacing:0.07em;color:#6B7B6B;margin-bottom:0.5rem">Updates</div>',
        unsafe_allow_html=True,
    )
    for c in public_comments:
        c_time = fmt_datetime(c.get("created_at", ""))
        st.markdown(
            f'<div style="background:#F9FBF9;border-left:3px solid #407E3C;'
            f'padding:0.55rem 0.85rem;border-radius:0 6px 6px 0;margin-bottom:0.5rem">'
            f'<div style="font-size:0.72rem;color:#9CA3AF;margin-bottom:3px">{c_time}</div>'
            f'<div style="font-size:0.85rem;color:#1A1A1A">{c["body"]}</div>'
            f"</div>",
            unsafe_allow_html=True,
        )
else:
    st.markdown(
        '<div style="color:#9CA3AF;font-size:0.85rem;margin-bottom:1rem">'
        "No updates yet. Our team will respond shortly.</div>",
        unsafe_allow_html=True,
    )

# ── Reply form (open/in_progress only) ───────────────────────────────────────
if status_val in ("open", "in_progress"):
    st.markdown(
        '<div style="font-size:0.75rem;font-weight:700;text-transform:uppercase;'
        'letter-spacing:0.07em;color:#6B7B6B;margin:1rem 0 0.4rem">Reply</div>',
        unsafe_allow_html=True,
    )
    with st.form("client_detail_reply", clear_on_submit=True):
        reply_body = st.text_area(
            "Reply", height=80, label_visibility="collapsed",
            placeholder="Type your reply here…",
        )
        if st.form_submit_button("Send Reply", width='stretch'):
            if not reply_body.strip():
                st.warning("Reply cannot be empty.")
            else:
                _, cerr = api.add_comment(ticket_id, reply_body.strip(), is_internal=False)
                if cerr:
                    st.error(f"Could not send reply: {cerr}")
                else:
                    st.success("Reply sent.")
                    st.rerun()
else:
    st.markdown(
        f'<div style="background:#F3F4F6;border-radius:6px;padding:0.6rem 0.9rem;'
        f'font-size:0.83rem;color:#6B7B6B;margin-top:1rem">'
        f'This ticket is <b>{status_val}</b> — replies are disabled.</div>',
        unsafe_allow_html=True,
    )
